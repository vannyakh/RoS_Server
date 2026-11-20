"""Operator live feed. Holds the open admin sockets and who is online.

A player is online while they hold this server's game socket, or while the original-client
gateway keeps reporting their session (POST /api/v1/gateway/accounts/{uid}/presence). A
gateway report lasts GATEWAY_TTL seconds, so a gateway that stops reporting cannot leave a
player online.

Publishing never waits on a socket: each operator socket has its own bounded queue, drained
by that socket's sender task. A slow or full queue drops the operator, not the publisher.
"""

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, field

QUEUE_LIMIT = 256
GATEWAY_TTL = 75.0


@dataclass(eq=False)
class AdminSubscriber:
    operator_id: str
    permissions: set[str]
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=QUEUE_LIMIT))
    dropped: bool = False
    close_code: int = 1000
    # Live map: None = not watching, "*" = every match, otherwise one match id.
    watching: str | None = None
    watch_static: bool = False
    watch_tick: int = 0


class AdminHub:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._subscribers: set[AdminSubscriber] = set()
        self._socket: set[str] = set()
        self._gateway: dict[str, float] = {}  # account id -> expiry on self._clock

    def subscribe(self, operator_id: str, permissions: set[str]) -> AdminSubscriber:
        subscriber = AdminSubscriber(operator_id=operator_id, permissions=set(permissions))
        self._subscribers.add(subscriber)
        return subscriber

    def unsubscribe(self, subscriber: AdminSubscriber) -> None:
        self._subscribers.discard(subscriber)

    def _fresh_gateway(self) -> set[str]:
        now = self._clock()
        return {account_id for account_id, expires in self._gateway.items() if expires > now}

    def _online_set(self) -> set[str]:
        return self._socket | self._fresh_gateway()

    @property
    def online_players(self) -> int:
        return len(self._online_set())

    def online_ids(self, limit: int = 1000) -> list[str]:
        return sorted(self._online_set())[:limit]

    def is_online(self, account_id: str) -> bool:
        if account_id in self._socket:
            return True
        expires = self._gateway.get(account_id)
        return expires is not None and expires > self._clock()

    def _changed(self, account_id: str, was: bool, source: str) -> None:
        now = self.is_online(account_id)
        if now == was:
            return
        self.publish(
            "players.read",
            "player.presence",
            {"account_id": account_id, "online": now, "online_players": self.online_players, "source": source},
        )

    def presence(self, account_id: str, online: bool) -> None:
        """Game socket on this server opened or closed."""
        was = self.is_online(account_id)
        if online:
            self._socket.add(account_id)
        else:
            self._socket.discard(account_id)
        self._changed(account_id, was, "socket")

    def gateway_presence(self, account_id: str, online: bool) -> None:
        """Original-client session report: online renews the lease, offline ends it."""
        was = self.is_online(account_id)
        if online:
            self._gateway[account_id] = self._clock() + GATEWAY_TTL
        else:
            self._gateway.pop(account_id, None)
        self._changed(account_id, was, "gateway")

    def sweep(self) -> None:
        """Drop expired gateway leases and announce the players that went offline."""
        now = self._clock()
        expired = [account_id for account_id, expires in self._gateway.items() if expires <= now]
        for account_id in expired:
            del self._gateway[account_id]
            if account_id not in self._socket:
                self.publish(
                    "players.read",
                    "player.presence",
                    {"account_id": account_id, "online": False, "online_players": self.online_players, "source": "gateway"},
                )

    def player_changed(self, account_id: str, change: str, operator: str) -> None:
        self.publish("players.read", "player.changed", {"account_id": account_id, "change": change, "operator": operator})

    def publish(self, permission: str, message_type: str, payload: dict) -> None:
        message = {"version": 1, "type": message_type, "payload": payload}
        for subscriber in list(self._subscribers):
            if permission not in subscriber.permissions:
                continue
            try:
                subscriber.queue.put_nowait(message)
            except asyncio.QueueFull:
                subscriber.dropped = True
                self._subscribers.discard(subscriber)

    def reset(self) -> None:
        """Test helper: forget every subscriber and presence entry."""
        self._subscribers.clear()
        self._socket.clear()
        self._gateway.clear()


admin_hub = AdminHub()
