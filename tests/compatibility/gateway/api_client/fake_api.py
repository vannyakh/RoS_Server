"""Local HTTP/1.1 keep-alive server that stands in for RoS_Server /api/v1/gateway."""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FakeApi:
    def __init__(self):
        self.lock = threading.Lock()
        self.connections = 0
        self.requests = []  # (method, path, headers dict, body bytes)
        self.drop_after_response = False  # next response leaves keep-alive on, then closes
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]
        self.url = f"http://127.0.0.1:{self.port}"
        self.thread = threading.Thread(target=self.server.serve_forever, args=(0.05,), daemon=True)
        self.thread.start()

    def count(self, method=None):
        with self.lock:
            return sum(1 for r in self.requests if method is None or r[0] == method)

    def stop(self):
        self.server.shutdown()
        self.server.server_close()

    def _handler(self):
        api = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def setup(self):
                super().setup()
                with api.lock:
                    api.connections += 1

            def log_message(self, *args):
                pass

            def _send(self, status, payload, content_type="application/json"):
                raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
                self.send_response(status)
                if raw or status != 204:
                    self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                if raw:
                    self.wfile.write(raw)
                with api.lock:
                    drop, api.drop_after_response = api.drop_after_response, False
                if drop:
                    self.wfile.flush()
                    self.close_connection = True  # client was told nothing: a stale keep-alive

            def _handle(self):
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length) if length else b""
                with api.lock:
                    api.requests.append((self.command, self.path, dict(self.headers), body))
                path = self.path
                if path.startswith("/slow"):
                    time.sleep(1.0)
                    return self._send(200, {"slow": True})
                if path == "/conflict":
                    return self._send(409, {"detail": "insufficient_gold"})
                if path == "/text-error":
                    return self._send(500, b"Internal Server Error", "text/plain")
                if path == "/not-json":
                    return self._send(200, b"<html>", "text/html")
                if path == "/empty":
                    return self._send(204, b"")
                if path.startswith("/listings"):
                    return self._send(200, {"listings": [{"prop_id": 1, "price": 10}], "n": api.count("GET")})
                echo = json.loads(body) if body else None
                return self._send(200, {"method": self.command, "path": path, "echo": echo})

            do_GET = do_POST = do_PUT = do_DELETE = _handle

        return Handler
