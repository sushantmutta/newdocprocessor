HITL Production Test Matrix
===========================

Purpose
-------
This folder contains plain-text test documents to validate a production-grade HITL system.

Files and Expected Trigger
--------------------------
1) 01_unknown_doc_type.txt
   - Expected: doc_type == unknown -> human_review

2) 02_low_confidence_noisy_prescription.txt
   - Expected: low confidence_score -> confidence_gate -> human_review

3) 03_schema_validation_failure_lab.txt
   - Expected: schema_validation_failed == True -> human_review

4) 04_critical_flags_lab_extreme.txt
   - Expected: HIGH/CRITICAL validation flags -> human_review

5) 05_repair_limit_exceeded_units.txt
   - Expected: repair_attempts reaches max -> human_review

6) 06_extraction_empty_like_scan_stub.txt
   - Expected: extraction_empty == True -> human_review

7) 07_fallback_trigger_candidate_prescription.txt
   - Expected: llm_fallback_used == True -> human_review

8) 08_human_override_candidate.txt
   - Expected: use for approve/reject/override/re_extract/escalate API paths

Suggested API Order
-------------------
1. POST /process/with-review for each file
2. Verify response shows interrupted_at == human_review for trigger cases
3. Use decision API to test:
   - approve
   - reject
   - override (with modified_data)
   - re_extract (with hint_prompt)
   - escalate
4. Verify /review/pending includes paused threads

Notes
-----
- Some outcomes (repair_limit_exceeded, llm_fallback_used) are environment/config dependent.
- If not triggered immediately, inspect trace_log and adjust provider or retry settings.