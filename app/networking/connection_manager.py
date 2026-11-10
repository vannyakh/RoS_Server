"""Active WebSocket sessions."""

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, WebSocket] = {}

    async def connect(self, player_id: str, websocket: WebSocket) -> None:
        previous = self._connections.get(player_id)
        self._connections[player_id] = websocket
        if previous is not None and previous is not websocket:
            await previous.close(code=4000)

    def disconnect(self, player_id: str, websocket: WebSocket) -> None:
        if self._connections.get(player_id) is websocket:
            del self._connections[player_id]

    async def publish_states(self, snapshots: list[dict]) -> None:
        for snapshot in snapshots:
            websocket = self._connections.get(snapshot["player_id"])
            if websocket is None:
                continue
            try:
                await websocket.send_json(
                    {
                        "version": 1,
                        "type": "state",
                        "sequence": snapshot["tick"],
                        "payload": snapshot,
                    }
                )
            except Exception:
                self.disconnect(snapshot["player_id"], websocket)


connection_manager = ConnectionManager()
