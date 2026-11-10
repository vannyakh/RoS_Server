"""Short load profile for this server's HTTP and WebSocket API.

The password is a local fixture. Do not point --host at a database you need to keep.
"""

import json
import time
from uuid import uuid4

from locust import HttpUser, between, task
import websocket

FIXTURE_PASSWORD = "LoadTestPassword123!"


class PlayerUser(HttpUser):
    wait_time = between(0.1, 0.3)

    def on_start(self) -> None:
        username = "ld" + uuid4().hex[:8]
        registered = self.client.post(
            "/api/v1/auth/register",
            json={"username": username, "password": FIXTURE_PASSWORD},
            name="/api/v1/auth/register",
        )
        if registered.status_code != 201:
            raise RuntimeError("register failed")
        logged_in = self.client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": FIXTURE_PASSWORD},
            name="/api/v1/auth/login",
        )
        if logged_in.status_code != 200:
            raise RuntimeError("login failed")
        self.token = logged_in.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

    @task(3)
    def profile(self) -> None:
        self.client.get("/api/v1/players/me", headers=self.headers, name="/api/v1/players/me")

    @task(2)
    def lobby(self) -> None:
        self.client.get("/api/v1/lobby", headers=self.headers, name="/api/v1/lobby")

    @task(2)
    def matches(self) -> None:
        self.client.get("/api/v1/matches", name="/api/v1/matches")

    @task(1)
    def websocket_auth(self) -> None:
        host = self.host.replace("http://", "ws://").replace("https://", "wss://")
        connection = websocket.create_connection(host + "/api/v1/ws", timeout=3)
        try:
            connection.send(
                json.dumps(
                    {"version": 1, "type": "auth", "sequence": 1, "payload": {"token": self.token}}
                )
            )
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                raw = connection.recv()
                if "auth.ok" in raw:
                    return
                if "Invalid or expired token" in raw:
                    raise RuntimeError("websocket auth rejected")
            raise RuntimeError("websocket auth did not return auth.ok")
        except websocket.WebSocketTimeoutException as exc:
            raise RuntimeError("websocket auth timed out before auth.ok") from exc
        finally:
            connection.close()
