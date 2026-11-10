"""FastAPI application entrypoint."""

import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import register_routes
from app.core.config import settings
from app.core.exceptions import AppError
from app.core.logging import configure_logging
from app.game.engine import game_engine
from app.game.tick_manager import TickManager
from app.infrastructure.database import close_db, init_db
from app.infrastructure.redis import get_cache
from app.infrastructure.storage import ASSETS
from app.networking.connection_manager import connection_manager
from app.observability.metrics import observe_world
from app.services.persistence_service import persistence_service
from tools.function_tracker import function_tracker


async def _tick(dt: float) -> None:
    with function_tracker.track(
        function_id="game.tick",
        feature="gameplay",
        function_name="tick",
        hot=True,
    ) as execution:
        execution.mark("GAME_STATE_UPDATE")
        snapshots = await game_engine.step(dt)
        await connection_manager.publish_states(snapshots)
        for result in await game_engine.take_results():
            await persistence_service.save_player_progress(
                result.player_id,
                {"kills": result.kills, "win": result.win},
            )
    observe_world(game_engine.world)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    if settings.app_env == "development":
        await init_db()
    tick = TickManager(settings.game_tick_rate, _tick)
    app.state.tick_manager = tick
    app.state.engine = game_engine
    task = asyncio.create_task(tick.run())
    try:
        yield
    finally:
        tick.stop()
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        await get_cache().close()
        await close_db()


app = FastAPI(title=settings.app_name, version="2.0.0", lifespan=lifespan)
register_routes(app)

from app.observability.http import install_http_instrumentation

install_http_instrumentation(app)
play_dir = ASSETS / "play"
if play_dir.is_dir():
    app.mount("/play", StaticFiles(directory=play_dir, html=True), name="play")


@app.exception_handler(AppError)
async def handle_app_error(_request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
