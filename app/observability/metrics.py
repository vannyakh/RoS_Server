"""Prometheus metrics. Labels stay bounded: no player, session, or request ids."""

from time import perf_counter

from prometheus_client import Counter, Gauge, Histogram
from sqlalchemy import event

HTTP_REQUESTS = Counter(
    "ros_http_requests_total",
    "HTTP requests by method, route template, and status.",
    ["method", "path", "status"],
)
HTTP_DURATION = Histogram(
    "ros_http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ["method", "path"],
)
ACTIVE_SESSIONS = Gauge("ros_active_sessions", "Connected non-bot players in memory.")
ACTIVE_LOBBIES = Gauge("ros_active_lobbies", "Players waiting in the in-memory queue.")
ACTIVE_MATCHES = Gauge("ros_active_matches", "In-memory matches.")
TICK_DURATION = Histogram("ros_game_tick_duration_seconds", "Game tick callback duration.")
TICK_OVERRUNS = Counter("ros_game_tick_overruns_total", "Ticks that exceeded the interval.")
DB_DURATION = Histogram("ros_database_query_duration_seconds", "Database cursor execution time.")
DB_POOL = Gauge("ros_database_pool_connections", "Checked-out database connections.")
FUNCTION_EXECUTIONS = Counter(
    "ros_function_executions_total",
    "Tracked function executions.",
    ["feature", "function_id", "status"],
)
FUNCTION_DURATION = Histogram(
    "ros_function_duration_seconds",
    "Tracked function duration.",
    ["feature", "function_id"],
)


def observe_request(method: str, path: str, status: int, elapsed: float) -> None:
    HTTP_REQUESTS.labels(method=method, path=path, status=str(status)).inc()
    HTTP_DURATION.labels(method=method, path=path).observe(elapsed)


def observe_tick(elapsed: float, overrun: bool) -> None:
    TICK_DURATION.observe(elapsed)
    if overrun:
        TICK_OVERRUNS.inc()


def observe_world(world) -> None:
    humans = [player for player in world.players.values() if not player.is_bot]
    ACTIVE_SESSIONS.set(sum(player.connected for player in humans))
    ACTIVE_LOBBIES.set(sum(player.status == "queued" for player in humans))
    ACTIVE_MATCHES.set(len(world.matches))


def observe_function(feature: str, function_id: str, status: str, elapsed: float) -> None:
    FUNCTION_EXECUTIONS.labels(feature=feature, function_id=function_id, status=status).inc()
    FUNCTION_DURATION.labels(feature=feature, function_id=function_id).observe(elapsed)


def install_query_metrics(engine) -> None:
    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def _start(conn, cursor, statement, parameters, context, executemany) -> None:
        context._ros_query_started = perf_counter()

    @event.listens_for(engine.sync_engine, "after_cursor_execute")
    def _finish(conn, cursor, statement, parameters, context, executemany) -> None:
        started = getattr(context, "_ros_query_started", None)
        if started is not None:
            DB_DURATION.observe(perf_counter() - started)
        checked_out = getattr(engine.pool, "checkedout", None)
        DB_POOL.set(checked_out() if checked_out else 0)
