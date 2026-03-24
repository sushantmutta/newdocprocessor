"""Deterministic supervisor routing logic for the LangGraph pipeline.

This module contains pure-Python state checks and route decisions.
No LLM calls are made here.
"""

from datetime import datetime, timedelta, timezone
import uuid

from config.settings import get_settings
from src.core.agents.repair import REPAIRABLE_FLAGS
from src.core.state import DocState


def _settings():
    return get_settings().processing


def _review_severities() -> set[str]:
    configured = getattr(_settings(), "review_flag_severities", [
                         "HIGH", "CRITICAL"])
    return {str(s).upper() for s in configured}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _review_deadline_iso() -> str:
    timeout_hours = int(getattr(_settings(), "review_timeout_hours", 4))
    return (datetime.now(timezone.utc) + timedelta(hours=timeout_hours)).isoformat()


def _append_supervisor_trace(state: DocState, decision: str, reason: str, stage: str) -> None:
    state.setdefault("trace_log", []).append(
        {
            "agent": "supervisor",
            "stage": stage,
            "decision": decision,
            "reason": reason,
            "status": "routed",
        }
    )


def _mark_review(state: DocState, reason: str, stage: str) -> str:
    state["review_required"] = True
    reasons = list(state.get("review_reason") or [])
    reasons.append(reason)
    state["review_reason"] = list(dict.fromkeys(reasons))
    state["review_deadline"] = state.get(
        "review_deadline") or _review_deadline_iso()
    state["paused_since"] = state.get("paused_since") or _now_iso()
    state["supervisor_decision"] = "human_review"
    _append_supervisor_trace(state, "human_review", reason, stage)
    return "human_review"


def _mark_abort(state: DocState, reason: str, stage: str) -> str:
    state["abort_reason"] = reason
    state["supervisor_decision"] = "abort"
    state.setdefault("errors", []).append(f"Pipeline aborted: {reason}")
    _append_supervisor_trace(state, "abort", reason, stage)
    return "abort"


def _set_decision(state: DocState, decision: str, reason: str, stage: str) -> str:
    state["supervisor_decision"] = decision
    _append_supervisor_trace(state, decision, reason, stage)
    return decision


def _has_pipeline_errors(state: DocState) -> bool:
    return bool(state.get("errors"))


def _has_unrecoverable_error(state: DocState) -> bool:
    if state.get("abort_reason"):
        return True
    errors = [str(e).lower() for e in (state.get("errors") or [])]
    return any("fatal" in e or "unrecoverable" in e for e in errors)


def _has_high_or_critical_flags(state: DocState) -> bool:
    severities = _review_severities()
    flags = state.get("validation_flags") or []
    return any(str(f.get("severity", "")).upper() in severities for f in flags)


def _repair_limit_exceeded(state: DocState) -> bool:
    max_attempts = int(getattr(_settings(), "max_repair_attempts", 3))
    return int(state.get("repair_attempts", 0)) >= max_attempts


def _has_repairable_flags_with_attempts_left(state: DocState) -> bool:
    flags = state.get("validation_flags") or []
    flag_attempts = state.get("repair_flag_attempts") or {}
    max_attempts = int(getattr(_settings(), "max_repair_attempts", 3))
    for flag in flags:
        code = flag.get("code")
        if code in REPAIRABLE_FLAGS and int(flag_attempts.get(code, 0)) < max_attempts:
            return True
    return False


def _is_structured_doc(doc_type: str) -> bool:
    return doc_type in {"prescription", "lab_report"}


def pre_supervisor(state: DocState) -> DocState:
    """Initialize supervisor-related state defaults before any LLM agent runs."""
    state.setdefault("errors", [])
    state.setdefault("trace_log", [])
    state.setdefault("validation_flags", [])
    state.setdefault("repair_attempts", 0)
    state.setdefault("review_required", False)
    state.setdefault("review_reason", [])
    state.setdefault("review_deadline", None)
    state.setdefault("paused_since", None)
    state.setdefault("escalated", False)
    state.setdefault("reviewer_id", None)
    state.setdefault("reviewer_notes", None)
    state.setdefault("schema_validation_failed", False)
    state.setdefault("validation_error_message", None)
    state.setdefault("extraction_empty", False)
    state.setdefault("llm_fallback_used", False)
    state.setdefault("human_decision", None)
    state.setdefault("modified_data", None)
    state.setdefault("hint_prompt", None)
    state.setdefault("original_data", state.get("extracted_data") or {})
    state.setdefault("responsible_ai_log", [])
    state.setdefault("knowledge_hits", [])
    state.setdefault("knowledge_conflicts", [])
    state.setdefault("knowledge_recommendations", [])
    state.setdefault("trace_events", [])
    state.setdefault("trace_correlation_id", f"trace-{uuid.uuid4().hex[:10]}")
    state.setdefault("supervisor_decision", None)
    state.setdefault("abort_reason", None)
    _append_supervisor_trace(
        state, "classifier", "pipeline initialized", "pre")
    return state


def post_classifier_supervisor(state: DocState) -> DocState:
    """Post-classifier gate to route unknown documents to human review."""
    doc_type = (state.get("doc_type") or "").lower().strip()
    if _has_unrecoverable_error(state):
        _mark_abort(
            state, "unrecoverable error after classification", "post_classifier")
    elif _has_pipeline_errors(state):
        _mark_review(state, "pipeline error", "post_classifier")
    elif doc_type == "unknown":
        _mark_review(state, "unclassifiable document", "post_classifier")
    elif _is_structured_doc(doc_type):
        _set_decision(state, "extractor",
                      "structured document", "post_classifier")
    else:
        _set_decision(state, "redactor",
                      "non-structured document", "post_classifier")
    return state


def post_classifier_router(state: DocState) -> str:
    """Router after post_classifier_supervisor."""
    decision = state.get("supervisor_decision") or "redactor"
    if decision in {"extractor", "human_review", "redactor", "abort"}:
        return decision
    return "redactor"


def post_extractor_supervisor(state: DocState) -> DocState:
    """Post-extractor gate to pause low-confidence outputs for human review."""
    threshold = float(getattr(_settings(), "confidence_threshold", 0.70))
    confidence = float(state.get("confidence_score") or 0.0)
    if _has_unrecoverable_error(state):
        _mark_abort(state, "unrecoverable error after extraction",
                    "post_extractor")
    elif _has_pipeline_errors(state):
        _mark_review(state, "pipeline error", "post_extractor")
    elif confidence < threshold:
        _mark_review(state, "low confidence extraction", "post_extractor")
    else:
        _set_decision(state, "validator",
                      "confidence acceptable", "post_extractor")
    return state


def post_extractor_router(state: DocState) -> str:
    """Router after post_extractor_supervisor."""
    decision = state.get("supervisor_decision") or "validator"
    if decision in {"validator", "human_review", "abort"}:
        return decision
    return "validator"


def post_validator_supervisor(state: DocState) -> DocState:
    """Post-validator gate that sets routing intent for repair/review/redaction/abort."""
    if _has_unrecoverable_error(state):
        _mark_abort(state, "unrecoverable error after validation",
                    "post_validator")
    elif _has_pipeline_errors(state):
        _mark_review(state, "pipeline error", "post_validator")
    elif bool(state.get("schema_validation_failed")):
        _mark_review(state, "schema validation failed", "post_validator")
    elif bool(state.get("extraction_empty")):
        _mark_review(state, "extraction appears empty", "post_validator")
    elif bool(state.get("llm_fallback_used")):
        _mark_review(state, "llm fallback model was used", "post_validator")
    elif bool(state.get("knowledge_conflicts")):
        _mark_review(state, "knowledge conflicts detected", "post_validator")
    elif _has_high_or_critical_flags(state):
        _mark_review(state, "critical validation flags", "post_validator")
    elif _repair_limit_exceeded(state):
        _mark_review(state, "repair limit exceeded", "post_validator")
    elif _has_repairable_flags_with_attempts_left(state):
        _set_decision(state, "repair",
                      "repairable flags present", "post_validator")
    else:
        _set_decision(state, "redactor", "no repair needed", "post_validator")
    return state


def supervisor_router(state: DocState) -> str:
    """Rich deterministic router replacing the previous should_repair conditional.

    Returns one of: "repair", "human_review", "redactor", "abort".
    """
    decision = state.get("supervisor_decision")
    if decision in {"repair", "human_review", "redactor", "abort"}:
        return decision

    # Defensive fallback if node ordering is changed.
    post_validator_supervisor(state)
    return state.get("supervisor_decision") or "redactor"


def human_review_node(state: DocState) -> DocState:
    """Prepare review payload for HITL interruption point."""
    if not state.get("review_required"):
        state["review_required"] = True
        reasons = list(state.get("review_reason") or [])
        reasons.append("manual review requested")
        state["review_reason"] = list(dict.fromkeys(reasons))

    reasons = list(state.get("review_reason") or [])
    if not reasons:
        reasons = ["manual review requested"]
        state["review_reason"] = reasons

    state["review_deadline"] = state.get(
        "review_deadline") or _review_deadline_iso()
    state["paused_since"] = state.get("paused_since") or _now_iso()

    state["repair_summary"] = {
        "reasoning": "; ".join(reasons),
        "flags_repaired": state.get("validation_flags") or [],
        "confidence": state.get("confidence_score", 0.0),
        "original_data": state.get("validated_data") or state.get("extracted_data") or {},
        "repaired_data": state.get("extracted_data") or {},
        "errors": state.get("errors") or [],
    }
    _append_supervisor_trace(
        state,
        "human_review",
        "; ".join(reasons),
        "human_review",
    )
    return state


def abort_node(state: DocState) -> DocState:
    """Finalize abort state before reporter runs."""
    reason = state.get("abort_reason") or "unrecoverable error"
    state["supervisor_decision"] = "abort"
    if not any("Pipeline aborted" in str(e) for e in (state.get("errors") or [])):
        state.setdefault("errors", []).append(f"Pipeline aborted: {reason}")
    _append_supervisor_trace(state, "abort", reason, "abort")
    return state
