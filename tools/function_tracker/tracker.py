"""Structured function-execution records. High-frequency stages are sampled."""

import json
import logging
import random
import re
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from app.observability.metrics import observe_function

logger = logging.getLogger("ros.function")

STAGES = (
    "REQUEST_RECEIVED",
    "VALIDATION",
    "AUTHORIZATION",
    "SERVICE_EXECUTION",
    "DATABASE_OPERATION",
    "GAME_STATE_UPDATE",
    "RESPONSE_SENT",
)
_SECRET = re.compile(r"(?i)bearer\s+\S+|password\s*[:=]\s*\S+")


def redact(value: str) -> str:
    return _SECRET.sub("[redacted]", value)


@dataclass
class Execution:
    function_id: str
    feature: str
    function_name: str
    execution_id: str
    request_id: str
    session_id: str | None
    player_id: str | None
    match_id: str | None
    trace_id: str
    started_at: datetime
    completed_at: datetime | None = None
    duration_ms: float | None = None
    status: str = "started"
    error_code: str | None = None
    error_message: str | None = None
    stages: list[str] = field(default_factory=list)
    sampled_out: bool = False

    def mark(self, stage: str) -> None:
        if stage not in STAGES:
            raise ValueError(f"Unknown stage {stage}")
        if not self.sampled_out:
            self.stages.append(stage)


class FunctionTracker:
    def __init__(self, hot_sample_rate: float = 0.0) -> None:
        self.hot_sample_rate = hot_sample_rate
        self.records: list[dict] = []
        self._random = random.Random(1)

    @contextmanager
    def track(
        self,
        *,
        function_id: str,
        feature: str,
        function_name: str,
        request_id: str | None = None,
        session_id: str | None = None,
        player_id: str | None = None,
        match_id: str | None = None,
        hot: bool = False,
    ):
        execution = Execution(
            function_id=function_id,
            feature=feature,
            function_name=function_name,
            execution_id=uuid4().hex,
            request_id=request_id or uuid4().hex,
            session_id=session_id,
            player_id=player_id,
            match_id=match_id,
            trace_id=uuid4().hex,
            started_at=datetime.now(timezone.utc),
            sampled_out=hot and self._random.random() > self.hot_sample_rate,
        )
        try:
            yield execution
        except Exception as exc:
            self.finish(execution, "error", type(exc).__name__, str(exc))
            raise
        else:
            self.finish(execution, "ok")

    def finish(self, execution: Execution, status: str, error_code: str | None = None, error_message: str | None = None) -> dict | None:
        if execution.sampled_out:
            return None
        execution.completed_at = datetime.now(timezone.utc)
        execution.duration_ms = (execution.completed_at - execution.started_at).total_seconds() * 1000
        execution.status = status
        execution.error_code = error_code
        execution.error_message = redact(error_message) if error_message else None
        record = {
            "function_id": execution.function_id,
            "feature": execution.feature,
            "function_name": execution.function_name,
            "execution_id": execution.execution_id,
            "request_id": execution.request_id,
            "session_id": execution.session_id,
            "player_id": execution.player_id,
            "match_id": execution.match_id,
            "started_at": execution.started_at.isoformat(),
            "completed_at": execution.completed_at.isoformat(),
            "duration_ms": round(execution.duration_ms, 3),
            "status": execution.status,
            "error_code": execution.error_code,
            "error_message": execution.error_message,
            "trace_id": execution.trace_id,
            "stages": list(execution.stages),
        }
        self.records.append(record)
        logger.info(json.dumps(record, separators=(",", ":")))
        observe_function(execution.feature, execution.function_id, status, execution.duration_ms / 1000)
        return record


function_tracker = FunctionTracker()
