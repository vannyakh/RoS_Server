"""Mount the HTTP and WebSocket routes."""

from fastapi import FastAPI

from app.api.v1 import original_catalog
from app.api.v1 import admin_access, assets, store, admin_maps, admin_support, auth, cosmetics, gateway, health, inventory, items, lobby, match_records, maps, matches, players
from app.networking.admin_socket import router as admin_socket_router
from app.networking.websocket import router as websocket_router


def register_routes(app: FastAPI) -> None:
    app.include_router(health.router)
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(players.router, prefix="/api/v1")
    app.include_router(lobby.router, prefix="/api/v1")
    app.include_router(matches.router, prefix="/api/v1")
    app.include_router(match_records.router, prefix="/api/v1")
    app.include_router(items.router, prefix="/api/v1")
    app.include_router(inventory.router, prefix="/api/v1")
    app.include_router(cosmetics.router, prefix="/api/v1")
    app.include_router(maps.router, prefix="/api/v1")
    app.include_router(admin_maps.router, prefix="/api/v1")
    app.include_router(admin_access.router, prefix="/api/v1")
    app.include_router(admin_support.router, prefix="/api/v1")
    app.include_router(gateway.router, prefix="/api/v1")
    app.include_router(assets.public, prefix="/api/v1")
    app.include_router(assets.admin, prefix="/api/v1")
    app.include_router(store.router, prefix="/api/v1")
    app.include_router(original_catalog.router, prefix="/api/v1")
    app.include_router(websocket_router)
    app.include_router(admin_socket_router)
