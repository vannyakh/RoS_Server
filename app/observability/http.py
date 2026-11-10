"""HTTP instrumentation: correlation id, trace, function record, and metrics."""

from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.observability.errors import capture_exception
from app.observability.metrics import observe_request
from app.observability.tracing import tracer
from tools.function_tracker import function_tracker


def install_http_instrumentation(app: FastAPI) -> None:
    @app.middleware("http")
    async def _instrument(request, call_next):
        request_id = request.headers.get("x-request-id") or uuid4().hex
        started = perf_counter()
        try:
            with tracer.start_as_current_span("http.request") as span:
                span.set_attribute("request_id", request_id)
                with function_tracker.track(
                    function_id="http.request",
                    feature="http",
                    function_name=request.url.path,
                    request_id=request_id,
                ) as execution:
                    execution.mark("REQUEST_RECEIVED")
                    try:
                        response = await call_next(request)
                    except Exception as exc:
                        execution.mark("SERVICE_EXECUTION")
                        capture_exception(exc, request_id)
                        raise
                    if response.status_code == 422:
                        execution.mark("VALIDATION")
                    elif response.status_code in {401, 403}:
                        execution.mark("AUTHORIZATION")
                    else:
                        execution.mark("SERVICE_EXECUTION")
                    execution.mark("RESPONSE_SENT")
        except Exception:
            observe_request(request.method, "unmatched", 500, perf_counter() - started)
            raise
        route = request.scope.get("route")
        path = getattr(route, "path", "unmatched")
        observe_request(request.method, path, response.status_code, perf_counter() - started)
        response.headers["x-request-id"] = request_id
        return response

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
