"""Observability & Distributed Tracing Module for Voice AI.

Provides:
1. OpenTelemetry-compatible distributed trace and span management.
2. Structured JSON logging with trace_id propagation across STT -> LLM -> TTS pipeline.
3. Millisecond latency telemetry logging into MongoDB telemetry_spans for dashboards.
"""

from __future__ import annotations

import json
import uuid
import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Generator

from .db.mongo import get_db

# Configure root structured logger
logger = logging.getLogger("voice_ai.telemetry")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def log_structured(
    event: str,
    component: str,
    level: str = "INFO",
    trace_id: str | None = None,
    span_id: str | None = None,
    latency_ms: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Emit a single-line structured JSON log event for cloud log aggregators (Datadog, AWS CloudWatch, Grafana)."""
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "event": event,
        "component": component,
        "trace_id": trace_id or str(uuid.uuid4()),
        "span_id": span_id or str(uuid.uuid4()),
    }
    if latency_ms is not None:
        payload["latency_ms"] = round(latency_ms, 2)
    if metadata:
        payload["metadata"] = metadata

    log_line = json.dumps(payload)
    if level == "ERROR":
        logger.error(log_line)
    elif level == "WARNING":
        logger.warning(log_line)
    else:
        logger.info(log_line)


class TraceSpan:
    def __init__(self, component: str, operation: str, trace_id: str | None = None, metadata: dict[str, Any] | None = None):
        self.component = component
        self.operation = operation
        self.trace_id = trace_id or str(uuid.uuid4())
        self.span_id = str(uuid.uuid4())[:8]
        self.metadata = metadata or {}
        self.start_time = 0.0
        self.duration_ms = 0.0

    def __enter__(self):
        self.start_time = perf_counter()
        log_structured(
            event=f"{self.operation}_start",
            component=self.component,
            trace_id=self.trace_id,
            span_id=self.span_id,
            metadata=self.metadata,
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.duration_ms = (perf_counter() - self.start_time) * 1000.0
        status = "error" if exc_type else "ok"
        meta = {**self.metadata, "status": status}
        if exc_val:
            meta["error"] = str(exc_val)

        level = "ERROR" if exc_type else "INFO"
        log_structured(
            event=f"{self.operation}_finish",
            component=self.component,
            level=level,
            trace_id=self.trace_id,
            span_id=self.span_id,
            latency_ms=self.duration_ms,
            metadata=meta,
        )

        # Record span in MongoDB telemetry_spans for dashboards and SLA monitoring
        try:
            db = get_db()
            db.get_collection("telemetry_spans").insert_one({
                "trace_id": self.trace_id,
                "span_id": self.span_id,
                "component": self.component,
                "operation": self.operation,
                "latency_ms": round(self.duration_ms, 2),
                "status": status,
                "createdAt": datetime.now(timezone.utc),
                "metadata": meta,
            })
        except Exception:
            pass


def get_recent_traces(limit: int = 50) -> list[dict[str, Any]]:
    """Retrieve recent telemetry spans for frontend observability."""
    try:
        db = get_db()
        docs = list(db.get_collection("telemetry_spans").find({}, {"_id": 0}).sort("createdAt", -1).limit(limit))
        return docs
    except Exception as exc:
        print(f"[observability][error] Failed to fetch traces: {exc}")
        return []
