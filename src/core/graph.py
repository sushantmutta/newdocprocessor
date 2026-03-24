from __future__ import annotations

import atexit
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph

from config.settings import get_settings
from src.core.agents.classifier import classify_doc
from src.core.agents.extractor import extract_data
from src.core.agents.knowledge_agent import knowledge_lookup
from src.core.agents.redactor import redact_pii
from src.core.agents.repair import repair_data
from src.core.agents.reporter import generate_report
from src.core.agents.supervisor import (
    abort_node,
    human_review_node,
    post_classifier_router,
    post_classifier_supervisor,
    post_extractor_router,
    post_extractor_supervisor,
    post_validator_supervisor,
    pre_supervisor,
    supervisor_router,
)
from src.core.agents.validator import validate_data
from src.core.graph_nodes.review_gate import (
    human_review_router,
)
from src.core.state import DocState
from src.core.utils.trace_utils import timed_call


def _instrument_node(agent: str, action: str, fn):
    def _runner(state: DocState) -> DocState:
        thread_id = str(state.get("trace_correlation_id") or "pipeline")
        return timed_call(fn, state, thread_id=thread_id, agent=agent, action=action)

    return _runner


def _knowledge_node(state: DocState) -> DocState:
    if not get_settings().processing.enable_knowledge_lookup:
        state.setdefault("knowledge_hits", [])
        state.setdefault("knowledge_conflicts", [])
        state.setdefault("knowledge_recommendations", [])
        state.setdefault("trace_log", []).append(
            {"agent": "knowledge_lookup", "status": "skipped",
                "reason": "feature_flag_disabled"}
        )
        return state
    return knowledge_lookup(state)


def _initialize_state(state: DocState) -> DocState:
    state.setdefault("errors", [])
    state.setdefault("trace_log", [])
    state.setdefault("validation_flags", [])
    state.setdefault("repair_attempts", 0)
    state.setdefault("review_required", False)
    state.setdefault("review_reason", [])
    state.setdefault("review_deadline", None)
    state.setdefault("escalated", False)
    state.setdefault("reviewer_id", None)
    state.setdefault("reviewer_notes", None)
    state.setdefault("schema_validation_failed", False)
    state.setdefault("validation_error_message", None)
    state.setdefault("extraction_empty", False)
    state.setdefault("llm_fallback_used", False)
    state.setdefault("paused_since", None)
    state.setdefault("human_decision", None)
    state.setdefault("modified_data", None)
    state.setdefault("hint_prompt", None)
    state.setdefault("original_data", state.get("extracted_data") or {})
    state.setdefault("responsible_ai_log", [])
    state.setdefault("knowledge_hits", [])
    state.setdefault("knowledge_conflicts", [])
    state.setdefault("knowledge_recommendations", [])
    state.setdefault("trace_correlation_id", None)
    state.setdefault("trace_events", [])
    return state


workflow = StateGraph(DocState)
workflow.add_node("initialize", _initialize_state)
workflow.add_node("pre_supervisor", _instrument_node(
    "supervisor", "pre_supervisor", pre_supervisor))
workflow.add_node("classifier", _instrument_node(
    "classifier", "classify", classify_doc))
workflow.add_node("post_classifier_supervisor", _instrument_node(
    "supervisor", "post_classifier_supervisor", post_classifier_supervisor))
workflow.add_node("extractor", _instrument_node(
    "extractor", "extract", extract_data))
workflow.add_node("post_extractor_supervisor", _instrument_node(
    "supervisor", "post_extractor_supervisor", post_extractor_supervisor))
workflow.add_node("validator", _instrument_node(
    "validator", "validate", validate_data))
workflow.add_node("knowledge_lookup", _instrument_node(
    "knowledge_lookup", "knowledge_lookup", _knowledge_node))
workflow.add_node("post_validator_supervisor", _instrument_node(
    "supervisor", "post_validator_supervisor", post_validator_supervisor))
workflow.add_node("human_review", _instrument_node(
    "supervisor", "human_review", human_review_node))
workflow.add_node("abort", _instrument_node("supervisor", "abort", abort_node))
workflow.add_node("repair", _instrument_node("repair", "repair", repair_data))
workflow.add_node("redactor", _instrument_node(
    "redactor", "redact", redact_pii))
workflow.add_node("reporter", _instrument_node(
    "reporter", "report", generate_report))

workflow.set_entry_point("initialize")
workflow.add_edge("initialize", "pre_supervisor")
workflow.add_edge("pre_supervisor", "classifier")
workflow.add_edge("classifier", "post_classifier_supervisor")

workflow.add_conditional_edges("post_classifier_supervisor", post_classifier_router, {
    "extractor": "extractor",
    "human_review": "human_review",
    "redactor": "redactor",
    "abort": "abort",
})

workflow.add_edge("extractor", "post_extractor_supervisor")
workflow.add_conditional_edges("post_extractor_supervisor", post_extractor_router, {
    "validator": "validator",
    "human_review": "human_review",
    "abort": "abort",
})

workflow.add_edge("validator", "knowledge_lookup")
workflow.add_edge("knowledge_lookup", "post_validator_supervisor")
workflow.add_conditional_edges("post_validator_supervisor", supervisor_router, {
    "repair": "repair",
    "human_review": "human_review",
    "redactor": "redactor",
    "abort": "abort",
})

workflow.add_conditional_edges("human_review", human_review_router, {
    "repair": "repair",
    "redactor": "redactor",
    "validator": "validator",
    "extractor": "extractor",
})

workflow.add_edge("abort", "reporter")
workflow.add_edge("repair", "redactor")
workflow.add_edge("redactor", "reporter")
workflow.add_edge("reporter", END)


settings = get_settings()
reviews_db_path = Path(settings.processing.reviews_db_path)
reviews_db_path.parent.mkdir(parents=True, exist_ok=True)
_checkpointer_ctx = SqliteSaver.from_conn_string(
    str(reviews_db_path)
)
checkpointer = _checkpointer_ctx.__enter__()
atexit.register(lambda: _checkpointer_ctx.__exit__(None, None, None))

# Standard graph (no interrupts)
app = workflow.compile()

# HITL graph (interrupt after human_review, optionally before repair)
interrupt_before = [
    "repair"] if settings.processing.interrupt_before_repair else []
app_with_review = workflow.compile(
    checkpointer=checkpointer,
    interrupt_after=["human_review"],
    interrupt_before=interrupt_before,
)
