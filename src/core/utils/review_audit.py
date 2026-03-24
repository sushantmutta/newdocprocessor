from __future__ import annotations

from datetime import datetime, timezone

from src.core.state import DocState


def append_human_audit_log(
    state: DocState,
    *,
    thread_id: str,
    reviewer_id: str | None,
    action: str,
    decision_rationale: str | None,
) -> None:
    entry = {
        "agent": "human",
        "reviewer_id": reviewer_id,
        "action": action,
        "decision_rationale": decision_rationale,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "thread_id": thread_id,
    }
    state.setdefault("responsible_ai_log", []).append(entry)
    state.setdefault("trace_log", []).append({
        "agent": "human",
        "action": action,
        "reviewer_id": reviewer_id,
        "status": "recorded",
    })
