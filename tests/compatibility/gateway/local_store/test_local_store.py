"""RO-119: local_store keeps the load_accounts/save_account contract while
caching, locking and writing atomically."""

import json
import os
import threading

import pytest

import legacy_store
import local_store


def _ops():
    """A login-like sequence of saves, including int keys and nested data."""
    return [
        ("default", {"name": "Raven", "char_type": 20001}),
        ("portrait:42", "file-1234"),
        ("inventory:42", {"items": [{"itemID": 1, "number": 3}], "gold": 10}),
        (7, {"int_key": True, "nested": {"1": [1, 2, {"x": None}]}}),
        ("default", {"name": "Raven", "char_type": 20002}),
        ("signin", {"level": 3, "day": "2026-11-26"}),
        ("unicode", {"name": "ស្វាគមន៍ ✓"}),
        ("supply_push", {"id": 9778}),
        ("float", 1.5),
        ("tuple", (1, 2)),
        ("intkeys", {1: "a", 2: "b"}),
    ]


@pytest.mark.parametrize("initial", [None, b"{}", b'{"old": {"a": 1}}',
                                     b'\xef\xbb\xbf{"bom": 1}', b"not json", b""])
def test_parity_with_legacy(tmp_path, initial):
    old = tmp_path / "old" / "saved_accounts.json"
    new = tmp_path / "new" / "saved_accounts.json"
    old.parent.mkdir()
    new.parent.mkdir()
    if initial is not None:
        old.write_bytes(initial)
        new.write_bytes(initial)

    assert local_store.load(new) == legacy_store.load_accounts(str(old))
    for key, data in _ops():
        legacy_store.save_account(str(old), key, data)
        local_store.save(new, key, data)
        assert new.read_bytes() == old.read_bytes()
        assert local_store.load(new) == legacy_store.load_accounts(str(old))
        assert local_store.get(new, str(key)) == legacy_store.load_accounts(str(old)).get(str(key))
    assert local_store.get(new, "absent", 5) == 5


def test_update_writes_once_with_same_bytes(tmp_path):
    old = tmp_path / "old.json"
    new = tmp_path / "new.json"
    for key, data in _ops():
        legacy_store.save_account(str(old), key, data)
    local_store.update(new, dict((str(k), v) for k, v in _ops()))
    assert new.read_bytes() == old.read_bytes()


def test_missing_file_and_missing_dir(tmp_path):
    path = tmp_path / "nope" / "saved_accounts.json"
    assert local_store.load(path) == {}
    local_store.save(path, "k", 1)          # directory missing: logged, not raised
    assert not path.exists()
    assert local_store.load(path) == {}


def test_returned_values_are_independent_copies(tmp_path):
    path = tmp_path / "a.json"
    local_store.save(path, "default", {"name": "A", "list": [1, {"x": 1}]})
    first = local_store.load(path)
    first["default"]["name"] = "mutated"
    first["default"]["list"][1]["x"] = 99
    first["new"] = 1
    got = local_store.get(path, "default")
    got["list"].append(5)
    assert local_store.load(path) == {"default": {"name": "A", "list": [1, {"x": 1}]}}

    data = {"deep": {"v": 1}}
    local_store.save(path, "k", data)
    data["deep"]["v"] = 2                   # caller's object must not alias the cache
    assert local_store.get(path, "k") == {"deep": {"v": 1}}


def test_external_modification_invalidates_cache(tmp_path):
    path = tmp_path / "a.json"
    local_store.save(path, "a", 1)
    assert local_store.load(path) == {"a": 1}

    path.write_text(json.dumps({"a": 1, "b": 2}), encoding="utf-8")   # size changes
    assert local_store.load(path) == {"a": 1, "b": 2}

    st = os.stat(path)
    path.write_text(json.dumps({"a": 1, "b": 3}), encoding="utf-8")   # same size
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 10_000_000))
    assert local_store.load(path) == {"a": 1, "b": 3}

    # a save after an external edit keeps the external keys
    local_store.save(path, "c", 4)
    assert json.loads(path.read_text("utf-8")) == {"a": 1, "b": 3, "c": 4}

    path.unlink()
    assert local_store.load(path) == {}


def test_path_aliases_share_one_store(tmp_path):
    path = tmp_path / "a.json"
    alias = str(tmp_path / "x" / ".." / "a.json")
    assert local_store.store_for(path) is local_store.store_for(alias)


def test_crash_mid_write_leaves_old_file(tmp_path, monkeypatch):
    path = tmp_path / "saved_accounts.json"
    local_store.save(path, "default", {"name": "A"})
    before = path.read_bytes()

    def boom(src, dst):
        raise OSError("simulated crash before rename")
    monkeypatch.setattr(local_store.os, "replace", boom)
    local_store.save(path, "default", {"name": "B"})
    monkeypatch.undo()

    assert path.read_bytes() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["saved_accounts.json"]  # temp removed
    assert local_store.load(path) == {"default": {"name": "A"}}


def test_crash_during_serialisation_leaves_old_file(tmp_path):
    # The old code truncated the file here; the new code keeps it.
    path = tmp_path / "saved_accounts.json"
    local_store.save(path, "a", 1)
    before = path.read_bytes()
    local_store.save(path, "bad", {"x": object()})
    assert path.read_bytes() == before
    assert local_store.load(path) == {"a": 1}


def test_replace_retries_permission_error(tmp_path, monkeypatch):
    path = tmp_path / "a.json"
    real = os.replace
    calls = {"n": 0}

    def flaky(src, dst):
        calls["n"] += 1
        if calls["n"] < 3:
            raise PermissionError("held by another process")
        return real(src, dst)
    monkeypatch.setattr(local_store, "_REPLACE_DELAY", 0.0)
    monkeypatch.setattr(local_store.os, "replace", flaky)
    local_store.save(path, "a", 1)
    monkeypatch.undo()
    assert calls["n"] == 3
    assert json.loads(path.read_text("utf-8")) == {"a": 1}


def test_concurrent_writers_lose_nothing(tmp_path):
    path = tmp_path / "saved_accounts.json"
    threads, per_thread = 16, 50
    errors = []
    start = threading.Barrier(threads)

    def worker(t):
        try:
            start.wait()
            for i in range(per_thread):
                local_store.save(path, f"t{t}:k{i}", {"t": t, "i": i})
        except Exception as e:  # pragma: no cover - reported below
            errors.append(e)

    pool = [threading.Thread(target=worker, args=(t,)) for t in range(threads)]
    for th in pool:
        th.start()
    for th in pool:
        th.join()
    assert not errors
    on_disk = json.loads(path.read_text("utf-8"))
    assert len(on_disk) == threads * per_thread
    assert on_disk == {f"t{t}:k{i}": {"t": t, "i": i}
                       for t in range(threads) for i in range(per_thread)}
    local_store.invalidate()
    assert local_store.load(path) == on_disk


def test_corrupt_file_is_backed_up_once_before_save(tmp_path):
    path = tmp_path / "saved_accounts.json"
    corrupt = b'{"default": {"name": "A"'   # truncated write from the old code
    path.write_bytes(corrupt)

    assert local_store.load(path) == {}
    assert list(tmp_path.glob("saved_accounts.json.bad-*")) == []   # loading alone does not copy

    local_store.save(path, "k", 1)
    bad = list(tmp_path.glob("saved_accounts.json.bad-*"))
    assert len(bad) == 1 and bad[0].read_bytes() == corrupt
    assert json.loads(path.read_text("utf-8")) == {"k": 1}

    local_store.save(path, "k2", 2)          # file is valid now: no second copy
    assert len(list(tmp_path.glob("saved_accounts.json.bad-*"))) == 1


def test_corrupt_file_log_has_no_contents(tmp_path, capsys):
    path = tmp_path / "saved_accounts.json"
    path.write_bytes(b'{"secret_token": "abc123" BROKEN')
    assert local_store.load(path) == {}
    local_store.save(path, "k", 1)
    out = capsys.readouterr().out
    assert "abc123" not in out and "secret_token" not in out
    assert "load_accounts error" in out


def test_bom_file_read(tmp_path):
    path = tmp_path / "saved_accounts.json"
    path.write_bytes(b'\xef\xbb\xbf' + json.dumps({"default": {"name": "Bom"}}).encode("utf-8"))
    assert local_store.load(path) == {"default": {"name": "Bom"}}
    assert local_store.get(path, "default") == {"name": "Bom"}


def test_non_object_file_matches_legacy(tmp_path):
    path = tmp_path / "list.json"
    path.write_text("[1, 2]", encoding="utf-8")
    assert local_store.load(path) == legacy_store.load_accounts(str(path)) == [1, 2]
    assert local_store.get(path, "x", "d") == "d"
    with pytest.raises(TypeError):
        legacy_store.save_account(str(path), "x", 1)
    with pytest.raises(TypeError):
        local_store.save(path, "x", 1)
    assert path.read_text("utf-8") == "[1, 2]"


def test_copies_without_marshal_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(local_store, "_snapshot", lambda value: None)
    test_returned_values_are_independent_copies(tmp_path)
    (tmp_path / "p").mkdir()
    test_parity_with_legacy(tmp_path / "p", b'{"old": {"a": [1, 2]}}')
