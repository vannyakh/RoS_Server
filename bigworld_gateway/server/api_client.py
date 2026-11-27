"""Persistent HTTP client for the gateway -> RoS_Server API bridge (/api/v1/gateway).

account_link._call opens a new TCP connection for every request, and it runs on the
gateway's UDP packet path. ApiClient keeps a small pool of keep-alive connections instead.

Return contract of ApiClient.call (identical to account_link._call):
  * no key configured        -> None, and no request is sent
  * 2xx                      -> parsed JSON body, or {} for an empty body (204)
  * non-2xx                  -> {"_error": status} plus "detail" when the body is JSON with one
  * network error / timeout  -> None
  * 2xx with a non-JSON body -> None

Retries: a request that fails on a reused keep-alive connection before any response
arrives (the server closed it while it sat idle) is sent once more on a fresh connection,
for GET, PUT and DELETE only. POST is never retried: a purchase or compound must not be
applied twice.

Standard library only. The key is sent as X-Gateway-Key and never written to a log line.
"""

import copy
import http.client
import json
import ssl
import threading
import time
import urllib.parse

DEFAULT_URL = "http://127.0.0.1:8000"
DEFAULT_TIMEOUT = 2.0
POOL_SIZE = 4
IDLE_TTL = 2.5  # discard idle keep-alive sockets before uvicorn's 5s timeout drops them
RETRY_METHODS = frozenset({"GET", "PUT", "DELETE"})
# The server dropped an idle keep-alive connection before answering.
_STALE = (http.client.RemoteDisconnected, BrokenPipeError, ConnectionResetError, ConnectionAbortedError)


class ApiClient:
    def __init__(self, base_url=DEFAULT_URL, key="", timeout=DEFAULT_TIMEOUT, connect_timeout=None,
                 pool_size=POOL_SIZE, tag="[ACC-LINK]", log=print):
        parts = urllib.parse.urlsplit((base_url or DEFAULT_URL).rstrip("/"))
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise ValueError("ROS_API_URL must be an http:// or https:// URL")
        self.scheme = parts.scheme
        self.host = parts.hostname
        self.port = parts.port or (443 if parts.scheme == "https" else 80)
        self.prefix = parts.path.rstrip("/")
        self.key = key or ""
        self.timeout = float(timeout)
        self.connect_timeout = float(connect_timeout) if connect_timeout else self.timeout
        self.pool_size = max(1, int(pool_size))
        self.tag = tag
        self._log = log
        self._idle = []  # idle keep-alive connections, newest last
        self._lock = threading.Lock()
        self._cache = {}  # path -> (monotonic fetch time, result)
        self._cache_lock = threading.Lock()
        self._closed = False

    def __repr__(self):  # never shows the key
        return f"ApiClient({self.scheme}://{self.host}:{self.port}{self.prefix}, timeout={self.timeout})"

    # -- connections -------------------------------------------------------------

    def _new_connection(self):
        if self.scheme == "https":
            conn = http.client.HTTPSConnection(self.host, self.port, timeout=self.connect_timeout,
                                               context=ssl.create_default_context())
        else:
            conn = http.client.HTTPConnection(self.host, self.port, timeout=self.connect_timeout)
        return conn

    def _acquire(self):
        """(connection, reused). Never blocks: an empty pool makes a new connection."""
        now = time.monotonic()
        expired = []
        chosen = None
        with self._lock:
            while self._idle:
                conn, ts = self._idle.pop()
                if now - ts < IDLE_TTL:
                    chosen = conn
                    break
                expired.append(conn)
        for conn in expired:
            conn.close()
        if chosen is not None:
            return chosen, True
        return self._new_connection(), False

    def _release(self, conn):
        now = time.monotonic()
        with self._lock:
            if not self._closed and len(self._idle) < self.pool_size:
                self._idle.append((conn, now))
                return
        conn.close()

    def _connect(self, conn):
        conn.connect()  # bounded by connect_timeout
        conn.sock.settimeout(self.timeout)  # then every read/write is bounded by timeout

    def close(self):
        with self._lock:
            self._closed = True
            idle, self._idle = self._idle, []
        for conn, _ in idle:
            conn.close()

    def idle_connections(self):
        with self._lock:
            return len(self._idle)

    # -- requests ----------------------------------------------------------------

    def call(self, method, path, body, retry_stale=False):
        if not self.key:
            return None
        method = method.upper()
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json", "X-Gateway-Key": self.key}
        target = self.prefix + path
        attempts = 2 if (method in RETRY_METHODS or retry_stale) else 1
        for attempt in range(attempts):
            conn, reused = self._acquire()
            try:
                if conn.sock is None:
                    self._connect(conn)
                conn.request(method, target, body=data, headers=headers)
                resp = conn.getresponse()
                raw = resp.read()
            except _STALE as e:
                conn.close()
                if reused and attempt + 1 < attempts:
                    continue  # idle connection was closed by the server; once more on a new one
                self._log(f"{self.tag} {method} {path} failed ({type(e).__name__}: {e}); using local accounts")
                return None
            except (OSError, http.client.HTTPException, ValueError) as e:
                conn.close()
                self._log(f"{self.tag} {method} {path} failed ({type(e).__name__}: {e}); using local accounts")
                return None
            if resp.will_close:
                conn.close()
            else:
                self._release(conn)
            return self._result(method, path, resp.status, raw)
        return None  # not reached

    def _result(self, method, path, status, raw):
        if 200 <= status < 300:
            try:
                return json.loads(raw) if raw else {}  # 204 No Content -> {}
            except ValueError as e:
                self._log(f"{self.tag} {method} {path} failed ({type(e).__name__}: {e}); using local accounts")
                return None
        self._log(f"{self.tag} {method} {path} -> HTTP {status} {raw[:200]!r}")
        error = {"_error": status}
        try:
            error["detail"] = json.loads(raw).get("detail")
        except (ValueError, AttributeError):
            pass
        return error

    # -- read cache --------------------------------------------------------------

    def get_cached(self, path, ttl, cache_failures=True):
        """GET path, reusing the result for ttl seconds. With cache_failures (the default) a
        None or {"_error": ...} result is cached too, so a dead server costs one timeout per
        ttl instead of one per request. Returns a copy; callers may change it."""
        now = time.monotonic()
        with self._cache_lock:
            hit = self._cache.get(path)
            if hit is not None and now - hit[0] < ttl:
                return copy.deepcopy(hit[1])
        result = self.call("GET", path, None)
        ok = isinstance(result, dict) and "_error" not in result or isinstance(result, list)
        if ok or cache_failures:
            with self._cache_lock:
                self._cache[path] = (time.monotonic(), copy.deepcopy(result))
        return result

    def invalidate(self, prefix=None):
        with self._cache_lock:
            if prefix is None:
                self._cache.clear()
            else:
                for path in [p for p in self._cache if p.startswith(prefix)]:
                    del self._cache[path]


# -- shared client built from gateway settings -------------------------------------

_shared = None
_shared_settings = None
_shared_lock = threading.Lock()


def from_settings(setting_fn):
    """Shared ApiClient for the current settings, read through setting_fn (account_link._setting):
    ROS_API_URL, GATEWAY_API_KEY, ROS_API_TIMEOUT, ROS_API_CONNECT_TIMEOUT (default: the timeout).
    A change in any of them builds a new client and closes the old one's idle connections."""
    global _shared, _shared_settings
    settings = (
        setting_fn("ROS_API_URL", DEFAULT_URL),
        setting_fn("GATEWAY_API_KEY"),
        setting_fn("ROS_API_TIMEOUT", str(DEFAULT_TIMEOUT)),
        setting_fn("ROS_API_CONNECT_TIMEOUT", ""),
    )
    with _shared_lock:
        if _shared is not None and settings == _shared_settings:
            return _shared
        url, key, timeout, connect_timeout = settings
        old, _shared = _shared, ApiClient(url, key, float(timeout or DEFAULT_TIMEOUT),
                                          float(connect_timeout) if connect_timeout else None)
        _shared_settings = settings
    if old is not None:
        old.close()
    return _shared
