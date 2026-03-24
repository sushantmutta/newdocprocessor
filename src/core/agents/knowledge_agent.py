from __future__ import annotations

from src.core.knowledge.knowledge_store import build_store, exact_lookup
from src.core.state import DocState


def knowledge_lookup(state: DocState) -> DocState:
    """Exact-match knowledge validation against curated JSON/CSV data."""
    state.setdefault("knowledge_hits", [])
    state.setdefault("knowledge_conflicts", [])
    state.setdefault("knowledge_recommendations", [])

    store = build_store()
    doc_type = (state.get("doc_type") or "").lower()

    hits: list[dict] = []
    conflicts: list[dict] = []
    recs: list[dict] = []

    validated = state.get("validated_data") or state.get(
        "extracted_data") or {}

    if doc_type == "prescription":
        meds = validated.get("medications") if isinstance(
            validated, dict) else []
        meds = meds if isinstance(meds, list) else []
        for idx, med in enumerate(meds):
            name = str((med or {}).get("name") or "").strip()
            dosage = str((med or {}).get("dosage") or "").strip().lower()
            if not name:
                continue
            ref = exact_lookup(name, "drug", store)
            if ref:
                hits.append(
                    {"field": f"medications[{idx}].name", "value": name, "reference": ref})
                allowed_units = [u.lower()
                                 for u in (ref.get("allowed_units") or [])]
                if allowed_units and dosage:
                    unit_ok = any(u in dosage for u in allowed_units)
                    if not unit_ok:
                        conflict = {
                            "code": "KNOWLEDGE_MISMATCH",
                            "severity": "HIGH",
                            "field": f"medications[{idx}].dosage",
                            "message": f"Dosage unit for '{name}' does not match curated units {allowed_units}",
                            "value": dosage,
                        }
                        conflicts.append(conflict)
                        recs.append({
                            "field": f"medications[{idx}].dosage",
                            "suggestion": f"Use one of: {', '.join(allowed_units)}",
                        })
            else:
                recs.append({
                    "field": f"medications[{idx}].name",
                    "suggestion": f"Drug '{name}' not found in curated knowledge base. Verify spelling.",
                })

    elif doc_type == "lab_report":
        tests = validated.get("test_results") if isinstance(
            validated, dict) else []
        tests = tests if isinstance(tests, list) else []
        for idx, test in enumerate(tests):
            name = str((test or {}).get("test_name") or "").strip()
            unit = str((test or {}).get("unit") or "").strip().lower()
            if not name:
                continue
            ref = exact_lookup(name, "lab_test", store)
            if ref:
                hits.append(
                    {"field": f"test_results[{idx}].test_name", "value": name, "reference": ref})
                expected_units = [u.lower() for u in (ref.get("units") or [])]
                if expected_units and unit and unit not in expected_units:
                    conflict = {
                        "code": "KNOWLEDGE_MISMATCH",
                        "severity": "HIGH",
                        "field": f"test_results[{idx}].unit",
                        "message": f"Unit '{unit}' for '{name}' not in curated units {expected_units}",
                        "value": unit,
                    }
                    conflicts.append(conflict)
                    recs.append({
                        "field": f"test_results[{idx}].unit",
                        "suggestion": f"Use one of: {', '.join(expected_units)}",
                    })
            else:
                recs.append({
                    "field": f"test_results[{idx}].test_name",
                    "suggestion": f"Lab test '{name}' not found in curated knowledge base. Verify naming.",
                })

    if conflicts:
        state.setdefault("validation_flags", []).extend(conflicts)

    state["knowledge_hits"] = hits
    state["knowledge_conflicts"] = conflicts
    state["knowledge_recommendations"] = recs
    state.setdefault("trace_log", []).append(
        {
            "agent": "knowledge_lookup",
            "status": "completed",
            "knowledge_hits": len(hits),
            "knowledge_conflicts": len(conflicts),
            "knowledge_recommendations": len(recs),
        }
    )
    return state
