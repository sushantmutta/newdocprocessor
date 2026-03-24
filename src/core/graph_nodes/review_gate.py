from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable

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
            "agent": "review_gate",
            "decision": decision,
            "reason": reason,
            "status": "routed",
        }
    )


def _flag_has_severity(flags: Iterable[dict], allowed: set[str]) -> bool:
    return any(str(flag.get("severity", "")).upper() in allowed for flag in flags)


def review_gate_node(state: DocState) -> DocState:
    """Centralized deterministic gate deciding whether HITL review is required."""
    processing = get_settings().processing
    threshold = float(processing.confidence_threshold)
    allowed_severity = {s.upper() for s in processing.review_flag_severities}

    reasons: list[str] = list(state.get("review_reason") or [])
    score = float(state.get("confidence_score") or 0.0)
    flags = list(state.get("validation_flags") or [])

    if score < threshold:
        reasons.append(
            f"confidence_score below threshold ({score:.2f} < {threshold:.2f})")
    if bool(state.get("schema_validation_failed")):
        reasons.append("schema validation failed")
    if str(state.get("doc_type") or "").lower() == "unknown":
        reasons.append("document type is unknown")
    if _flag_has_severity(flags, allowed_severity):
        reasons.append("high or critical validation flags present")
    if int(state.get("repair_attempts") or 0) >= int(processing.max_repair_attempts):
        reasons.append("repair attempts exceeded limit")
    if bool(state.get("extraction_empty")):
        reasons.append("extraction appears empty")
    if bool(state.get("llm_fallback_used")):
        reasons.append("llm fallback model was used")

    if reasons:
        unique_reasons = list(dict.fromkeys(reasons))
        state["review_required"] = True
        state["review_reason"] = unique_reasons
        state["review_deadline"] = state.get(
            "review_deadline") or _review_deadline_iso()
        state["paused_since"] = state.get("paused_since") or _now_iso()
        _append_trace(state, "human_review", "; ".join(unique_reasons))
    else:
        state["review_required"] = False
        state["review_reason"] = []
        _append_trace(state, "continue", "no review triggers met")

    return state


def review_gate_router(state: DocState) -> str:
    """Return human_review or continue after evaluating trigger conditions."""
    return "human_review" if state.get("review_required") else "continue"


def human_review_node(state: DocState) -> DocState:
    """Prepare review packet before interrupt and capture pause metadata."""
    reasons = list(state.get("review_reason") or [])
    if not reasons:
        reasons = ["manual review requested"]
        state["review_reason"] = reasons

    state["review_required"] = True
    state["paused_since"] = state.get("paused_since") or _now_iso()
    state["repair_summary"] = {
        "reasoning": "; ".join(reasons),
        "flags_repaired": state.get("validation_flags") or [],
        "confidence": state.get("confidence_score", 0.0),
        "original_data": state.get("original_data") or state.get("validated_data") or state.get("extracted_data") or {},
        "repaired_data": state.get("extracted_data") or {},
        "errors": state.get("errors") or [],
    }
    _append_trace(state, "human_review", "; ".join(reasons))
    return state


def human_review_router(state: DocState) -> str:
    """Route after human review based on decision injected via API."""
    decision = str(state.get("human_decision") or "approve").lower()
    if decision == "re_extract":
        return "extractor"
    if decision == "override":
        return "validator"
    if decision == "reject":
        return "redactor"
    return "repair"
