"""Sentry-compatible exception events. Nothing is sent unless SENTRY_DSN is set."""

import os
from datetime import datetime, timezone
from uuid import uuid4

ERROR_EVENTS: list[dict] = []


def capture_exception(exc: BaseException, request_id: str | None = None) -> dict:
    event = {
        "event_id": uuid4().hex,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": "error",
        "exception": {"type": type(exc).__name__, "value": str(exc)[:300]},
        "tags": {"request_id": request_id or ""},
    }
    ERROR_EVENTS.append(event)
    dsn = os.environ.get("SENTRY_DSN", "").strip()
    if dsn:
        import sentry_sdk

        sentry_sdk.capture_exception(exc)
    return event
