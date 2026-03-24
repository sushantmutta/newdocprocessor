from src.core.agents.supervisor import post_validator_supervisor, supervisor_router


def test_knowledge_conflict_routes_to_human_review():
    state = {
        "errors": [],
        "abort_reason": None,
        "validation_flags": [],
        "repair_attempts": 0,
        "repair_flag_attempts": {},
        "schema_validation_failed": False,
        "extraction_empty": False,
        "llm_fallback_used": False,
        "knowledge_conflicts": [{"code": "KNOWLEDGE_MISMATCH", "severity": "HIGH"}],
        "review_required": False,
        "review_reason": [],
        "trace_log": [],
        "supervisor_decision": None,
    }

    post_validator_supervisor(state)

    assert supervisor_router(state) == "human_review"
    assert "knowledge conflicts detected" in state.get("review_reason", [])
