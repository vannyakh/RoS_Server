"""Mount the HTTP and WebSocket routes."""

from fastapi import FastAPI

from app.api.v1 import auth, health, items, lobby, matches, players
from app.networking.websocket import router as websocket_router


def register_routes(app: FastAPI) -> None:
    app.include_router(health.router)
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(players.router, prefix="/api/v1")
    app.include_router(lobby.router, prefix="/api/v1")
    app.include_router(matches.router, prefix="/api/v1")
    app.include_router(items.router, prefix="/api/v1")
    app.include_router(websocket_router)
