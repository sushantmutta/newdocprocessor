from __future__ import annotations

from datetime import datetime, timedelta, timezone

from config.settings import get_settings
from src.core.state import DocState


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _review_deadline_iso() -> str:
    timeout_hours = int(get_settings().processing.review_timeout_hours)
    return (datetime.now(timezone.utc) + timedelta(hours=timeout_hours)).isoformat()


def _append_trace(state: DocState, decision: str, reason: str) -> None:
    state.setdefault("trace_log", []).append(
        {
            "agent": "confidence_gate",
            "decision": decision,
            "reason": reason,
            "status": "routed",
        }
    )


def confidence_gate_node(state: DocState) -> DocState:
    """Evaluate extraction confidence and prime review metadata if low."""
    threshold = float(get_settings().processing.confidence_threshold)
    score = float(state.get("confidence_score") or 0.0)

    if score < threshold:
        reasons = list(state.get("review_reason") or [])
        reasons.append(
            f"low confidence extraction ({score:.2f} < {threshold:.2f})")
        state["review_required"] = True
        state["review_reason"] = reasons
        state["review_deadline"] = state.get(
            "review_deadline") or _review_deadline_iso()
        state["paused_since"] = state.get("paused_since") or _now_iso()
        _append_trace(state, "human_review", reasons[-1])
    else:
        _append_trace(state, "validator", "confidence acceptable")

    return state


def confidence_gate_router(state: DocState) -> str:
    """Route directly to human review when confidence is below threshold."""
    if state.get("review_required"):
        return "human_review"
    return "validator"
