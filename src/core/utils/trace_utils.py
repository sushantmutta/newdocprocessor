from __future__ import annotations

import hashlib
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from src.core.state import DocState
from src.core.utils.trace_schema import TraceEvent


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_correlation_id(state: DocState, thread_id: str | None = None) -> str:
    cid = state.get("trace_correlation_id")
    if cid:
        return cid
    seed = thread_id or "trace"
    cid = f"{seed}-{uuid.uuid4().hex[:10]}"
    state["trace_correlation_id"] = cid
    return cid


def payload_hash(payload: Any) -> str:
    try:
        blob = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    except Exception:
        blob = str(payload).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def append_trace_event(
    state: DocState,
    *,
    thread_id: str,
    agent: str,
    action: str,
    status: str,
    input_payload: Any,
    output_payload: Any,
    duration_ms: float | None,
    model: str | None = None,
    fallback_used: bool = False,
    reviewer_id: str | None = None,
    reviewer_notes: str | None = None,
    metadata: dict | None = None,
) -> None:
    correlation_id = ensure_correlation_id(state, thread_id)
    event = TraceEvent(
        thread_id=thread_id,
        correlation_id=correlation_id,
        timestamp=now_iso(),
        agent=agent,
        action=action,
        status=status,
        input_hash=payload_hash(input_payload),
        output_hash=payload_hash(output_payload),
        model=model,
        fallback_used=bool(fallback_used),
        duration_ms=duration_ms,
        reviewer_id=reviewer_id,
        reviewer_notes=reviewer_notes,
        metadata_json=json.dumps(metadata or {}, default=str),
    )
    state.setdefault("trace_events", []).append(event.model_dump())


def timed_call(func, state: DocState, *, thread_id: str, agent: str, action: str):
    start = time.perf_counter()
    before = {
        "doc_type": state.get("doc_type"),
        "validation_flags": state.get("validation_flags", []),
        "review_required": state.get("review_required", False),
        "repair_attempts": state.get("repair_attempts", 0),
    }
    try:
        updated = func(state)
        duration_ms = (time.perf_counter() - start) * 1000
        after = {
            "doc_type": updated.get("doc_type"),
            "validation_flags": updated.get("validation_flags", []),
            "review_required": updated.get("review_required", False),
            "repair_attempts": updated.get("repair_attempts", 0),
        }
        append_trace_event(
            updated,
            thread_id=thread_id,
            agent=agent,
            action=action,
            status="success",
            input_payload=before,
            output_payload=after,
            duration_ms=duration_ms,
            model=updated.get("llm_model_name"),
            fallback_used=bool(updated.get("llm_fallback_used")),
        )
        return updated
    except Exception as exc:
        duration_ms = (time.perf_counter() - start) * 1000
        append_trace_event(
            state,
            thread_id=thread_id,
            agent=agent,
            action=action,
            status="failed",
            input_payload=before,
            output_payload={"error": str(exc)},
            duration_ms=duration_ms,
            model=state.get("llm_model_name"),
            fallback_used=bool(state.get("llm_fallback_used")),
        )
        raise
