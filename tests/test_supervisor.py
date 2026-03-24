from src.core.agents.supervisor import (
    human_review_node,
    post_classifier_router,
    post_classifier_supervisor,
    post_extractor_router,
    post_extractor_supervisor,
    post_validator_supervisor,
    pre_supervisor,
    supervisor_router,
)


def _base_state():
    return {
        "raw_text": "sample",
        "file_path": "sample.txt",
        "doc_type": "prescription",
        "extracted_data": {},
        "validated_data": {},
        "validation_flags": [],
        "redacted_text": "",
        "errors": [],
        "trace_log": [],
        "repair_attempts": 0,
        "repair_flag_attempts": {},
        "repair_outcomes": [],
        "repair_summary": None,
        "llm_provider": "groq",
        "llm_model_name": None,
        "confidence_score": 0.95,
        "start_time": None,
        "ground_truth_pii": [],
        "detected_pii": [],
        "review_required": False,
        "review_reason": [],
        "supervisor_decision": None,
        "abort_reason": None,
    }


def test_unknown_document_routes_to_human_review():
    state = _base_state()
    state["doc_type"] = "unknown"

    post_classifier_supervisor(state)

    assert post_classifier_router(state) == "human_review"
    assert state["review_required"] is True
    assert "unclassifiable document" in state["review_reason"]


def test_low_confidence_extraction_routes_to_human_review():
    state = _base_state()
    state["confidence_score"] = 0.2

    post_extractor_supervisor(state)

    assert post_extractor_router(state) == "human_review"
    assert "low confidence extraction" in state["review_reason"]


def test_critical_validation_flags_route_to_human_review():
    state = _base_state()
    state["validation_flags"] = [
        {"code": "EXTREME_DOSAGE", "severity": "CRITICAL"}]

    post_validator_supervisor(state)

    assert supervisor_router(state) == "human_review"
    assert "critical validation flags" in state["review_reason"]


def test_repairable_flags_route_to_repair_when_attempts_left():
    state = _base_state()
    state["validation_flags"] = [
        {"code": "NON_STANDARD_UNIT", "severity": "MEDIUM"}]
    state["repair_flag_attempts"] = {"NON_STANDARD_UNIT": 0}

    post_validator_supervisor(state)

    assert supervisor_router(state) == "repair"


def test_repair_limit_exceeded_routes_to_human_review():
    state = _base_state()
    state["repair_attempts"] = 3

    post_validator_supervisor(state)

    assert supervisor_router(state) == "human_review"
    assert "repair limit exceeded" in state["review_reason"]


def test_errors_route_to_human_review():
    state = _base_state()
    state["errors"] = ["Extraction parse error"]

    post_validator_supervisor(state)

    assert supervisor_router(state) == "human_review"
    assert "pipeline error" in state["review_reason"]


def test_all_clear_routes_to_redactor():
    state = _base_state()

    post_validator_supervisor(state)

    assert supervisor_router(state) == "redactor"


def test_human_review_node_packages_review_summary():
    state = _base_state()
    state["review_required"] = True
    state["review_reason"] = ["critical validation flags"]
    state["validation_flags"] = [
        {"code": "CRITICAL_VALUE", "severity": "CRITICAL"}]
    state["confidence_score"] = 0.83

    updated = human_review_node(state)

    assert updated["repair_summary"] is not None
    assert updated["repair_summary"]["reasoning"] == "critical validation flags"
    assert updated["repair_summary"]["confidence"] == 0.83
