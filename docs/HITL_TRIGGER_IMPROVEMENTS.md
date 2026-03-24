# HITL Trigger Improvements

## Current State

`should_repair` in `src/core/agents/repair.py` only checks for `NON_STANDARD_UNIT` / `INVALID_DOSAGE_UNIT` flags, and the graph only interrupts `after=["repair"]` — meaning HITL fires **after the AI has already attempted a fix**, not before any other problem type.

---

## Additional HITL Trigger Points

### 1. Low Extraction Confidence

**Where to add it:** After `extractor` runs, check `state["confidence_score"]`.

`confidence_score` is already calculated and stored. If it drops below a threshold (e.g. `0.70`), route to HITL **before validation even runs** — there's no point validating data the extractor wasn't sure about.

```
extractor → [confidence < 0.70?] → human_review
                                 → validator (if confident)
```

---

### 2. Schema Validation Failure (Pydantic Error)

**Where it happens today:** In `validator.py`, when `PrescriptionSchema(**data)` or `LabReportSchema(**data)` raises `ValidationError`, the code catches it, logs error flags, and **continues anyway**. The extractor produced structurally broken data but it flows through silently.

**Improvement:** When a `ValidationError` is caught in the validator, set `review_required = True` and route to HITL instead of patching over it. The validator already generates `INVALID_*` flags from these errors — a human should see them.

---

### 3. Unknown / Unclassifiable Document

**Where it happens today:** Classifier returns `doc_type = "unknown"`, which routes to the **redactor** (not extractor). The document goes through redaction and reporting with zero structured data extracted — silently.

**Improvement:** When `doc_type == "unknown"`, pause for a human to either:
- Correct the document type manually
- Mark it as genuinely unclassifiable and skip
- Re-upload a better quality document

---

### 4. Critical Clinical Validation Flags

**Where it happens today:** Validator generates `CRITICAL` severity flags (e.g. extreme dosage, pediatric overdose, missing pathologist signature) but the graph just continues to repair/redactor regardless of severity.

**Improvement:** After validator runs, scan `validation_flags` for severity `CRITICAL` or `HIGH`. If any exist, route to HITL. The human reviewer sees the clinical alert and decides whether to override or accept it.

Flags that should trigger this today (already being generated):
- `EXTREME_DOSAGE`
- `PEDIATRIC_DOSING_ALERT`
- `CONTROLLED_SUBSTANCE_NO_DEA`
- `CRITICAL_VALUE` (lab reports)
- `MISSING_PATHOLOGIST_SIGNATURE`

---

### 5. Max Repair Attempts Exceeded

**Where it happens today:** When `repair_attempts >= 3`, `should_repair` returns `"redactor"` — the document silently moves on with still-broken data, no human ever sees it.

**Improvement:** Route to HITL instead of silently continuing. A human must make the call since the AI exhausted its attempts.

---

### 6. Empty or Near-Empty Extraction

**Where to add it:** After the extractor, check if `extracted_data` is `{}` or if critical fields (doctor, patient, medications for prescriptions) are all `None`.

The extractor can technically "succeed" (no exception) but return mostly null fields if the document quality is poor. `confidence_score` may not catch this if it is calculated as `filled_fields / total_fields` from the Pydantic model — optional fields inflate the denominator.

---

### 7. Interrupt BEFORE Repair, Not Just After

**Current design:** `interrupt_after=["repair"]` — the AI repairs first, then shows the human the result.

**Alternative:** Also add `interrupt_before=["repair"]` as an option (configurable). This means:
- Human sees the raw validation flags **before** the AI touches the data
- Human decides: "let AI fix it" vs. "I'll fix it myself"
- Better for high-stakes documents where the insurance company wants no AI modification without prior approval

LangGraph supports both `interrupt_after` and `interrupt_before` simultaneously.

---

### 8. LLM Provider Fallback Triggered

**Where it happens:** In `UnifiedLLMManager.invoke_with_fallback()` — if the primary model fails and the fallback is used, the agent gets a lower-quality response but the pipeline doesn't know.

**Improvement:** If the fallback model was used, add a `LOW_QUALITY_FALLBACK` flag to `trace_log`. The supervisor/gate checks for this flag and routes to HITL — the human verifies results when the AI was degraded.

---

## Summary

| Trigger | Currently Handled | Proposed Action |
|---------|------------------|-----------------|
| `NON_STANDARD_UNIT` / `INVALID_DOSAGE_UNIT` | ✅ Routes to repair → HITL after repair | Already works |
| `confidence_score < threshold` | ❌ Ignored | Route to HITL before validator |
| Pydantic `ValidationError` | ❌ Continues silently | Route to HITL |
| `doc_type == "unknown"` | ❌ Goes to redactor with no data | Route to HITL |
| `CRITICAL` / `HIGH` severity flags | ❌ Continues to redactor | Route to HITL |
| `repair_attempts >= max` | ❌ Silently continues | Route to HITL |
| Empty extraction result | ❌ Ignored | Route to HITL |
| Interrupt before repair (not just after) | ❌ Only after | Add `interrupt_before=["repair"]` option |
| LLM fallback triggered | ❌ Ignored | Add flag → route to HITL |
