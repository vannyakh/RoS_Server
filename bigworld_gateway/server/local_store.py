"""Cached, locked, atomic JSON key/value store for the gateway's local files.

Drop-in for ``ros_server.load_accounts`` / ``save_account`` (RO-119). The old
code opened and parsed ``saved_accounts.json`` on every call and rewrote it in
place, so a crash or a second writer could truncate it or lose keys.

Contract (matches the old functions for every readable file):

* ``load(path)`` returns what ``json.load`` of the file returns (read as
  utf-8-sig, so a BOM is accepted), or ``{}`` when the file is missing or does
  not parse. Every call returns a fresh deep copy: callers may mutate it freely
  and nothing leaks into the cache or into other callers.
* ``save(path, key, data)`` sets ``accs[str(key)] = data`` and writes the file
  with ``json.dump(accs, f, indent=2)`` through a text-mode utf-8 handle, so the
  bytes on disk are the same as before (including CRLF on Windows). Write
  errors are logged, not raised, as before.
* ``update(path, mapping)`` sets several keys in one write.

What changes:

* Parsed content is cached per path and reused while the file's
  (mtime_ns, size, inode) signature is unchanged. Any change on disk (an editor,
  another process, a test rewriting the file) or the file vanishing is seen on
  the next call.
* One re-entrant lock per path serialises read-modify-write inside the process,
  so concurrent ``save`` calls never drop each other's keys. There is no
  cross-process lock (the old code had none either).
* Writes go to a temp file in the same directory, are flushed and fsynced, then
  moved over the target with ``os.replace`` (retried briefly on Windows
  ``PermissionError``). A crash leaves either the old or the new file, never a
  partial one.
* A file that exists but does not parse is copied to ``<file>.bad-<timestamp>``
  once before a save overwrites it. File contents are never logged.

Paths are passed per call (tests monkeypatch ``ros_server.ACCOUNTS_FILE``), and
``LocalStore`` instances are cached per normalised absolute path.
"""

from __future__ import annotations

import json
import marshal
import os
import shutil
import tempfile
import threading
import time

__all__ = ["LocalStore", "store_for", "load", "get", "save", "update", "invalidate"]

_MISSING = object()
_REPLACE_RETRIES = 10
_REPLACE_DELAY = 0.02  # seconds, doubled each try up to _REPLACE_MAX_DELAY
_REPLACE_MAX_DELAY = 0.2


def _log(msg: str) -> None:
    print(f"[ACC] {msg}")


def _copy(value):
    """Deep copy for JSON-shaped data (dict/list/scalars); faster than copy.deepcopy."""
    if isinstance(value, dict):
        return {k: _copy(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_copy(v) for v in value]
    return value


def _snapshot(value):
    """marshal bytes of parsed JSON; marshal.loads is a C-speed deep copy that keeps
    dict order. JSON only yields dict/list/str/int/float/bool/None, all marshalable."""
    try:
        return marshal.dumps(value)
    except ValueError:
        return None


def _signature(path: str):
    try:
        st = os.stat(path)
    except FileNotFoundError:
        return None
    return (st.st_mtime_ns, st.st_size, st.st_ino)


class LocalStore:
    """One JSON object file. Use ``store_for(path)`` rather than constructing directly."""

    def __init__(self, path: str):
        self.path = path
        self.lock = threading.RLock()
        self._sig = _MISSING          # signature of the file the cache reflects
        self._data = {}               # parsed content (never handed out directly)
        self._blob = None             # marshal snapshot of _data for fast deep copies
        self._corrupt = False         # file exists but did not parse
        self._backed_up_sig = None    # corrupt signature already copied to .bad-*

    # -- reading -------------------------------------------------------------

    def _refresh(self) -> None:
        """Re-read the file if its signature changed. Caller holds the lock."""
        sig = _signature(self.path)
        if sig == self._sig:
            return
        if sig is None:
            self._data, self._corrupt = {}, False
            self._blob = _snapshot(self._data)
        else:
            try:
                with open(self.path, "r", encoding="utf-8-sig") as f:
                    self._data = json.load(f)
                self._corrupt = False
            except Exception as e:  # same fallback as the old load_accounts
                _log(f"load_accounts error: {type(e).__name__}: {_short(e)}")
                self._data, self._corrupt = {}, True
            self._blob = _snapshot(self._data)
            # The file may have changed while we read it; re-stat so a write that
            # raced the read is picked up next time instead of being masked.
            if _signature(self.path) != sig:
                sig = _MISSING
        self._sig = sig

    def load(self):
        with self.lock:
            self._refresh()
            return self._full_copy()

    def _full_copy(self):
        if self._blob is not None:
            return marshal.loads(self._blob)
        return _copy(self._data)

    def get(self, key, default=None):
        """``load().get(key, default)`` without copying the other keys."""
        with self.lock:
            self._refresh()
            if not isinstance(self._data, dict):
                return default
            value = self._data.get(key, _MISSING)
            return default if value is _MISSING else _copy(value)

    # -- writing -------------------------------------------------------------

    def save(self, key, data) -> None:
        self.update({key: data})

    def update(self, mapping) -> None:
        with self.lock:
            self._refresh()
            accs = self._full_copy()
            for key, data in dict(mapping).items():
                accs[str(key)] = data  # TypeError for a non-object file, as before
            try:
                text = json.dumps(accs, indent=2)  # same output as json.dump(..., indent=2)
            except Exception as e:
                _log(f"save_account error: {type(e).__name__}: {_short(e)}")
                return
            try:
                self._backup_corrupt()
                self._atomic_write(text)
            except Exception as e:
                _log(f"save_account error: {type(e).__name__}: {_short(e)}")
                self._sig = _MISSING  # unknown state: re-read next time
                return
            # Cache what a re-read would return (int keys become str, tuples lists).
            self._data = json.loads(text)
            self._blob = _snapshot(self._data)
            self._corrupt = False
            self._sig = _signature(self.path)

    def _backup_corrupt(self) -> None:
        if not self._corrupt or self._sig in (None, _MISSING) or self._backed_up_sig == self._sig:
            return
        stamp = time.strftime("%Y%m%dT%H%M%S") + f"-{time.time_ns() % 1_000_000_000:09d}"
        bad = f"{self.path}.bad-{stamp}"
        shutil.copy2(self.path, bad)
        self._backed_up_sig = self._sig
        _log(f"unreadable {os.path.basename(self.path)} kept as {os.path.basename(bad)}")

    def _atomic_write(self, text: str) -> None:
        directory = os.path.dirname(self.path) or "."
        fd, tmp = tempfile.mkstemp(
            prefix=os.path.basename(self.path) + ".", suffix=".tmp", dir=directory)
        try:
            # Text mode with the platform newline, exactly like the old open(..., "w").
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text)
                f.flush()
                os.fsync(f.fileno())
            _replace(tmp, self.path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def invalidate(self) -> None:
        with self.lock:
            self._sig = _MISSING


def _replace(src: str, dst: str) -> None:
    delay = _REPLACE_DELAY
    for attempt in range(_REPLACE_RETRIES):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            # Windows: target briefly held open by an editor, indexer or AV scanner.
            if attempt == _REPLACE_RETRIES - 1:
                raise
            time.sleep(delay)
            delay = min(delay * 2, _REPLACE_MAX_DELAY)


def _short(e: Exception) -> str:
    # json errors carry only a position; OS errors a path. Never file contents.
    return str(e)[:200]


_stores: dict[str, LocalStore] = {}
_stores_lock = threading.Lock()


def _norm(path) -> str:
    return os.path.normcase(os.path.abspath(os.fspath(path)))


def store_for(path) -> LocalStore:
    key = _norm(path)
    store = _stores.get(key)
    if store is None:
        with _stores_lock:
            store = _stores.get(key)
            if store is None:
                store = _stores[key] = LocalStore(os.path.abspath(os.fspath(path)))
    return store


def load(path):
    return store_for(path).load()


def get(path, key, default=None):
    return store_for(path).get(key, default)


def save(path, key, data) -> None:
    store_for(path).save(key, data)


def update(path, mapping) -> None:
    store_for(path).update(mapping)


def invalidate(path=None) -> None:
    """Drop cached content for one path, or for every path when ``path`` is None."""
    if path is not None:
        store_for(path).invalidate()
        return
    with _stores_lock:
        stores = list(_stores.values())
    for store in stores:
        store.invalidate()
