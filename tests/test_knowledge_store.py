from src.core.knowledge.knowledge_store import build_store, exact_lookup


def test_exact_lookup_drug_hit_and_alias():
    store = build_store()
    assert exact_lookup("amoxicillin", "drug", store) is not None
    alias_hit = exact_lookup("amoxicilin", "drug", store)
    assert alias_hit is not None
    assert alias_hit.get("name") == "amoxicillin"


def test_exact_lookup_miss_returns_none():
    store = build_store()
    assert exact_lookup("nonexistent-drug", "drug", store) is None
    assert exact_lookup("unknown-test", "lab_test", store) is None
