import csv
import time
import json
import os
import re
from typing import List, Optional, Tuple
from src.core.state import DocState
from config.settings import PROJECT_ROOT, get_reports_dir


def _json_default(obj):
    """Safe JSON serializer for non-standard types (datetime, Path, Decimal, etc.)"""
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return str(obj)


# Expected field counts per document type
EXPECTED_FIELDS = {
    "invoice": 4,      # invoice_number, vendor_name, total_amount, date
    "id_card": 4,      # full_name, id_number, date_of_birth, expiry_date
    "prescription": 5,  # date, doctor, patient, medications, diagnosis
    # lab, report_id, sample_type, collection_date, report_date, test_results, is_amended, (lab.pathologist_name)
    "lab_report": 8
}

# Required fields per document type for validation
REQUIRED_FIELDS = {
    "prescription": ["doctor", "patient", "medications", "date"],
    "lab_report": ["lab", "report_id", "test_results", "collection_date", "report_date"]
}


def calculate_validation_accuracy(doc_type: str, extracted_data: dict,
                                  validated_data: dict, errors: List[str],
                                  trace_log: List[dict]) -> float:
    """
    Calculate validation accuracy based on extraction format correctness.
    Measures: required fields present, correct data types, valid formats.
    NOT clinical validation flags (those are separate quality metrics).

    Returns: accuracy percentage (0-100)
    """
    if not extracted_data:
        return 0.0

    score = 100.0
    penalties = []

    # 1. Check required fields presence (30 points)
    required = REQUIRED_FIELDS.get(doc_type, [])
    if required:
        missing_fields = [
            field for field in required if field not in extracted_data or not extracted_data[field]]
        if missing_fields:
            penalty = (len(missing_fields) / len(required)) * 30
            penalties.append(("missing_required_fields", penalty))
            score -= penalty

    # 2. Check for Pydantic validation errors (40 points)
    validator_failed = any(
        log.get("agent") == "validator" and log.get("status") == "failed"
        for log in trace_log
    )
    if validator_failed:
        penalties.append(("pydantic_validation_failed", 40))
        score -= 40

    # 3. Check for extraction errors (30 points)
    extraction_errors = [
        e for e in errors if "extraction" in e.lower() or "parse" in e.lower()]
    if extraction_errors:
        penalty = min(len(extraction_errors) * 15, 30)
        penalties.append(("extraction_errors", penalty))
        score -= penalty

    # 4. Data type correctness bonus (if validated_data exists, it means validation passed)
    if validated_data and not validator_failed:
        # Validation passed - formats are correct
        pass  # No penalty, keep current score

    return max(0.0, score)


def calculate_pii_metrics(detected_pii: List[dict], redacted_text: str, raw_text: str) -> Tuple[float, float]:
    """
    Calculate PII Recall and Precision based on automated PII detection.

    This method works for ALL documents regardless of structure/fields because:
    1. PII is auto-detected from the document itself
    2. Metrics measure detection success vs redaction success
    3. No manual ground truth annotations needed

    Recall = (PII successfully redacted) / (Total PII detected) × 100
    Precision = (Correct redactions) / (Total redaction tags) × 100

    Args:
        detected_pii: List of PII entities auto-detected in document
            Format: [{"type": "NAME", "value": "John Doe", "category": "patient_name"}, ...]
        redacted_text: Text after PII redaction with [TYPE_REDACTED] tags
        raw_text: Original unredacted text for verification

    Returns:
        Tuple of (recall, precision) as percentages (0-100)
    """
    if not detected_pii:
        # No PII detected in document
        # Check if any redactions were made anyway
        redaction_tags = re.findall(r'\[([A-Z_]+)_REDACTED\]', redacted_text)
        if len(redaction_tags) > 0:
            # Redactions were made but no PII detected - precision = 0%
            return (100.0, 0.0)
        else:
            # No PII, no redactions - perfect (100% for both)
            return (100.0, 100.0)

    total_pii_detected = len(detected_pii)

    # Count how many detected PII entities were successfully redacted
    successfully_redacted = 0
    failed_redactions = []

    for pii_entity in detected_pii:
        pii_type = pii_entity.get("type", "UNKNOWN").upper()
        pii_value = str(pii_entity.get("value", "")).strip()

        if not pii_value:
            continue

        # Verification: Was this PII value successfully redacted?
        # Success = PII value no longer appears in redacted text
        # (case-insensitive check to handle variations)
        if pii_value.lower() not in redacted_text.lower():
            successfully_redacted += 1
        else:
            # PII still visible in redacted text - redaction failed
            failed_redactions.append({
                "type": pii_type,
                "value": pii_value[:20] + "..." if len(pii_value) > 20 else pii_value
            })

    # RECALL: What percentage of detected PII was successfully redacted?
    recall = (successfully_redacted / total_pii_detected) * \
        100 if total_pii_detected > 0 else 0.0

    # PRECISION: What percentage of redaction tags are valid/correct?
    # Extract all redaction tags from redacted text
    redaction_tags = re.findall(r'\[([A-Z_]+)_REDACTED\]', redacted_text)
    total_redactions = len(redaction_tags)

    if total_redactions == 0:
        # No redactions made but PII was detected
        precision = 0.0
    else:
        # Count how many redaction tags correspond to detected PII types
        detected_pii_types = set(pii.get("type", "").upper()
                                 for pii in detected_pii)

        correct_redactions = 0
        for tag in redaction_tags:
            if tag in detected_pii_types:
                correct_redactions += 1

        # Precision = (correct redactions / total redactions) × 100
        precision = (correct_redactions / total_redactions) * \
            100 if total_redactions > 0 else 0.0

    # Log failed redactions for debugging
    if failed_redactions and len(failed_redactions) > 0:
        print(
            f"  ⚠️  Warning: {len(failed_redactions)} PII items not redacted:")
        for failed in failed_redactions[:5]:  # Show first 5
            print(f"     - {failed['type']}: {failed['value']}")

    return (recall, precision)


def generate_report(state: DocState) -> DocState:
    """
    Generates comprehensive metrics report including accuracy, latency,
    extraction completeness, PII redaction, and repair effectiveness.
    """
    print("--- 📊 Agent: Reporter ---")

    # Keep configured output path and legacy root-level reports path for compatibility.
    primary_reports_dir = str(get_reports_dir())
    legacy_reports_dir = str(PROJECT_ROOT / "reports")
    output_dirs = [primary_reports_dir]
    if legacy_reports_dir not in output_dirs:
        output_dirs.append(legacy_reports_dir)

    for reports_dir in output_dirs:
        os.makedirs(reports_dir, exist_ok=True)

    # Bug 6 fix: set start_time if not already set so latency is always recorded
    if not state.get("start_time"):
        state["start_time"] = time.time()

    # Extract state data
    doc_type = state.get("doc_type", "unknown")
    validated_data = state.get("validated_data", {})
    extracted_data = state.get("extracted_data", {})
    errors = state.get("errors", [])
    trace_log = state.get("trace_log", [])
    repair_attempts = state.get("repair_attempts", 0)
    redacted_text = state.get("redacted_text", "")
    raw_text = state.get("raw_text", "")

    # 1. Calculate Extraction Completeness
    # Bug 2 fix: count top-level keys only — flattening nested dicts inflated count beyond 100%
    expected_count = EXPECTED_FIELDS.get(doc_type, 0)
    if isinstance(extracted_data, dict):
        extracted_count = float(
            len([v for v in extracted_data.values()
                 if v is not None and v != [] and v != {}]))
    else:
        extracted_count = 0.0

    extraction_completeness = (
        extracted_count / float(expected_count) * 100) if expected_count > 0 else 0
    # Cap at 100% — more fields than expected is still complete, not 200%
    extraction_completeness = min(extraction_completeness, 100.0)

    # Calculate VALIDATION ACCURACY based on extraction format correctness
    # This measures: required fields present, correct data types, valid formats
    # NOT clinical validation flags (those are separate quality metrics)
    validation_accuracy = calculate_validation_accuracy(
        doc_type, extracted_data, validated_data, errors, trace_log
    )

    # Use confidence_score from state
    confidence_score = state.get("confidence_score", 0.0)

    # 2. Calculate Success Rate
    pipeline_success = len(errors) == 0 and extracted_count > 0

    # 3. PII Redaction Metrics
    pii_redaction_count = 0
    pii_types = []
    for log_entry in trace_log:
        if log_entry.get("agent") == "redactor":
            pii_types = log_entry.get("pii_types_scrubbed", [])
            pii_redaction_count = sum([
                redacted_text.count(f"[{pii_type}_REDACTED]")
                for pii_type in pii_types
            ])

    redaction_coverage = (pii_redaction_count /
                          len(raw_text.split())) * 100 if raw_text else 0

    # Calculate PII Recall/Precision based on auto-detected PII
    # This works for ALL documents regardless of structure/fields
    detected_pii = state.get("detected_pii", [])
    if detected_pii:
        pii_recall, pii_precision = calculate_pii_metrics(
            detected_pii, redacted_text, raw_text
        )
    else:
        # Fallback: Check if ground truth PII was provided
        ground_truth_pii = state.get("ground_truth_pii", [])
        if ground_truth_pii:
            # Use ground truth if available
            pii_recall, pii_precision = calculate_pii_metrics(
                ground_truth_pii, redacted_text, raw_text
            )
        else:
            # Bug 7 fix: no PII data available — record as None instead of fabricated heuristics
            pii_recall = None
            pii_precision = None
            print(
                "  ℹ️  PII metrics unavailable: no detected_pii or ground_truth_pii in state")

    # 4. Repair Effectiveness
    repair_success = repair_attempts > 0 and pipeline_success

    # Tip 10: detailed repair outcome metrics
    repair_outcomes = state.get("repair_outcomes") or []
    if repair_outcomes:
        resolved = [o for o in repair_outcomes if o.get("status") == "applied"]
        repair_success_rate = (len(resolved) / len(repair_outcomes)) * 100
    else:
        repair_success_rate = None

    repair_flag_types_list = list({
        o.get("code", "") for o in repair_outcomes if o.get("code")
    })
    repair_flag_types_str = "|".join(
        sorted(repair_flag_types_list)) if repair_flag_types_list else "N/A"

    flag_attempts = state.get("repair_flag_attempts") or {}
    repair_max_hit = any(v >= 3 for v in flag_attempts.values())

    # 5. Agent Performance Breakdown
    agent_performance = {}
    for log_entry in trace_log:
        agent = log_entry.get("agent", "unknown")
        status = log_entry.get("status", "unknown")
        if agent not in agent_performance:
            agent_performance[agent] = {
                "success": 0, "failed": 0, "skipped": 0}

        if status in ["passed", "success", "completed"]:
            agent_performance[agent]["success"] += 1
        elif status == "failed":
            agent_performance[agent]["failed"] += 1
        elif status == "skipped":
            agent_performance[agent]["skipped"] += 1

    # 6. Build Comprehensive Report
    report = {
        "document_info": {
            "type": doc_type,
            "file_path": state.get("file_path", "unknown"),
            "confidence_score": confidence_score
        },
        "extraction_metrics": {
            "expected_fields": expected_count,
            "extracted_fields": extracted_count,
            "extraction_completeness": f"{extraction_completeness:.2f}%",
            "confidence_level": "High" if confidence_score > 0.8 else ("Medium" if confidence_score > 0.5 else "Low")
        },
        "quality_metrics": {
            "pipeline_success": pipeline_success,
            "error_count": len(errors),
            "validation_flags": state.get("validation_flags", [])
        },
        "pii_redaction": {
            "redaction_count": pii_redaction_count,
            "pii_types_found": pii_types,
            "redaction_coverage": f"{redaction_coverage:.2f}%"
        },
        "agent_performance": agent_performance,
        "trace": trace_log,
        "data": {
            "extracted": extracted_data,
            "validated": validated_data
        }
    }

    # 7. Save Detailed Trace Report (JSON)
    # Bug 5 fix: use _json_default to handle datetime/Path/Decimal without crashing
    trace_file_name = f"trace_{doc_type}_{int(time.time())}.json"
    for reports_dir in output_dirs:
        trace_path = os.path.join(reports_dir, trace_file_name)
        try:
            with open(trace_path, "w") as f:
                json.dump(report, f, indent=4, default=_json_default)
        except Exception as e:
            print(f"❌ Failed to save trace report to {reports_dir}: {e}")
    print(f"✅ Trace Report saved: {trace_file_name}")

    # Calculate latency (start_time is always set by the guard above)
    latency_ms = (time.time() - state["start_time"]) * 1000

    # 8. Append to Aggregate Metrics Report (CSV)
    # Bug 4 fix: open with 'a' but write header only when file is truly new,
    # guarded by checking size after open to avoid race condition on concurrent requests.
    # Bug 8 fix: csv import moved to top of file.
    fieldnames = [
        "timestamp", "doc_type", "file_path",
        "extraction_completeness", "validation_accuracy",
        "pipeline_success", "error_count", "repair_attempts",
        "repair_success_rate", "repair_flag_types", "repair_max_attempts_hit",
        "redaction_coverage", "pii_recall", "pii_precision",
        "latency_ms"
    ]
    for reports_dir in output_dirs:
        metrics_csv_path = os.path.join(reports_dir, "metrics_report.csv")
        with open(metrics_csv_path, "a", newline="") as csvfile:
            # Bug 4 fix: check position after open — position 0 means file was just created
            write_header = csvfile.tell() == 0
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            if write_header:
                writer.writeheader()

            writer.writerow({
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "doc_type": doc_type,
                "file_path": state.get("file_path", "unknown"),
                "extraction_completeness": f"{extraction_completeness:.2f}%",
                "validation_accuracy": f"{validation_accuracy:.2f}%",
                "pipeline_success": pipeline_success,
                "error_count": len(errors),
                "repair_attempts": repair_attempts,
                "repair_success_rate": f"{repair_success_rate:.2f}%" if repair_success_rate is not None else "N/A",
                "repair_flag_types": repair_flag_types_str,
                "repair_max_attempts_hit": repair_max_hit,
                "redaction_coverage": f"{redaction_coverage:.2f}%",
                # Bug 7 fix: write N/A when metrics are unavailable instead of fabricated values
                "pii_recall": f"{pii_recall:.2f}%" if pii_recall is not None else "N/A",
                "pii_precision": f"{pii_precision:.2f}%" if pii_precision is not None else "N/A",
                "latency_ms": f"{latency_ms:.2f}"
            })

    print(f"📊 Metrics appended to: {primary_reports_dir}")

    print(
        f"   Extraction: {extraction_completeness:.1f}% | Validation: {validation_accuracy:.1f}%")
    print(
        f"   Success: {pipeline_success} | Errors: {len(errors)} | Repairs: {repair_attempts}")

    # Add trace entry
    state["trace_log"].append({
        "agent": "reporter",
        "status": "completed",
        "report_path": trace_file_name,
        "metrics": {
            "extraction_completeness": f"{extraction_completeness:.2f}%",
            "validation_accuracy": f"{validation_accuracy:.2f}%",
            "pipeline_success": pipeline_success
        }
    })

    return state
