from src.core.agents.knowledge_agent import knowledge_lookup


def test_knowledge_agent_adds_conflicts_for_bad_dosage_unit():
    state = {
        "doc_type": "prescription",
        "validated_data": {
            "medications": [
                {"name": "Amoxicillin", "dosage": "500 liters"},
            ]
        },
        "validation_flags": [],
        "trace_log": [],
    }
    updated = knowledge_lookup(state)

    assert len(updated.get("knowledge_hits", [])) >= 1
    assert len(updated.get("knowledge_conflicts", [])) >= 1
    assert any(flag.get("code") == "KNOWLEDGE_MISMATCH" for flag in updated.get(
        "validation_flags", []))


def test_knowledge_agent_recommendation_on_missing_reference():
    state = {
        "doc_type": "lab_report",
        "validated_data": {
            "test_results": [
                {"test_name": "UnknownLabTest", "unit": "mg/dl"},
            ]
        },
        "validation_flags": [],
        "trace_log": [],
    }
    updated = knowledge_lookup(state)
    recs = updated.get("knowledge_recommendations", [])
    assert len(recs) >= 1
    assert "not found" in recs[0]["suggestion"].lower()
