from app.observability.errors import ERROR_EVENTS, capture_exception
from app.observability.metrics import HTTP_REQUESTS


async def test_metrics_endpoint_exposes_bounded_names(client):
    health = await client.get("/health")
    assert health.status_code == 200
    assert health.headers["x-request-id"]
    metrics = await client.get("/metrics")
    assert metrics.status_code == 200
    body = metrics.text
    for name in (
        "ros_http_requests_total",
        "ros_http_request_duration_seconds",
        "ros_game_tick_duration_seconds",
        "ros_database_query_duration_seconds",
        "ros_function_executions_total",
    ):
        assert name in body
    assert "player_id" not in body
    assert HTTP_REQUESTS.collect()


def test_sentry_compatible_event_keeps_the_exception_type():
    before = len(ERROR_EVENTS)
    event = capture_exception(RuntimeError("boom"), request_id="req-1")
    assert event["exception"]["type"] == "RuntimeError"
    assert event["tags"]["request_id"] == "req-1"
    assert len(ERROR_EVENTS) == before + 1
