import time
import json
import os
from app.state import DocState

# Expected field counts per document type
EXPECTED_FIELDS = {
    "invoice": 4,  # invoice_number, vendor_name, total_amount, date
    "id_card": 4   # full_name, id_number, date_of_birth, expiry_date
}


def generate_report(state: DocState) -> DocState:
    """
    Generates comprehensive metrics report including accuracy, latency,
    extraction completeness, PII redaction, and repair effectiveness.
    """
    print("--- 📊 Agent: Reporter ---")

    # Setup reports directory
    base_dir = os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))
    reports_dir = os.path.join(base_dir, "reports")
    os.makedirs(reports_dir, exist_ok=True)

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
    expected_count = EXPECTED_FIELDS.get(doc_type, 0)
    extracted_count = len([v for v in (extracted_data or {}).values() if v is not None])
    validated_count = len([v for v in (validated_data or {}).values() if v is not None])
    
    extraction_completeness = (extracted_count / expected_count * 100) if expected_count > 0 else 0
    validation_accuracy = (validated_count / expected_count * 100) if expected_count > 0 else 0

    # 2. Calculate Success Rate
    pipeline_success = len(errors) == 0 and validated_count == expected_count

    # 3. PII Redaction Metrics
    pii_redaction_count = 0
    pii_types = []
    for log_entry in trace_log:
        if log_entry.get("agent") == "redactor":
            pii_types = log_entry.get("pii_types_scrubbed", [])
            # Count redaction tags
            pii_redaction_count = sum([
                redacted_text.count(f"[{pii_type}_REDACTED]") 
                for pii_type in pii_types
            ])
    
    redaction_coverage = (pii_redaction_count / len(raw_text.split())) * 100 if raw_text else 0

    # 4. Repair Effectiveness
    repair_success = repair_attempts > 0 and pipeline_success
    
    # 5. Agent Performance Breakdown
    agent_performance = {}
    for log_entry in trace_log:
        agent = log_entry.get("agent", "unknown")
        status = log_entry.get("status", "unknown")
        if agent not in agent_performance:
            agent_performance[agent] = {"success": 0, "failed": 0, "skipped": 0}
        
        if status in ["passed", "success", "completed", "fixed_attempted"]:
            agent_performance[agent]["success"] += 1
        elif status == "failed":
            agent_performance[agent]["failed"] += 1
        elif status == "skipped":
            agent_performance[agent]["skipped"] += 1

    # 6. Build Comprehensive Report
    report = {
        "document_info": {
            "type": doc_type,
            "file_path": state.get("file_path", "unknown")
        },
        "extraction_metrics": {
            "expected_fields": expected_count,
            "extracted_fields": extracted_count,
            "validated_fields": validated_count,
            "extraction_completeness": f"{extraction_completeness:.2f}%",
            "validation_accuracy": f"{validation_accuracy:.2f}%"
        },
        "quality_metrics": {
            "pipeline_success": pipeline_success,
            "error_count": len(errors),
            "errors": errors
        },
        "pii_redaction": {
            "redaction_count": pii_redaction_count,
            "pii_types_found": pii_types,
            "redaction_coverage": f"{redaction_coverage:.2f}%"
        },
        "repair_metrics": {
            "repair_attempts": repair_attempts,
            "repair_success": repair_success,
            "final_status": "repaired" if repair_success else ("failed" if repair_attempts > 0 else "no_repair_needed")
        },
        "agent_performance": agent_performance,
        "trace": trace_log,
        "data": {
            "extracted": extracted_data,
            "validated": validated_data
        }
    }

    # 7. Save Report
    file_name = f"report_{doc_type}_{int(time.time())}.json"
    report_path = os.path.join(reports_dir, file_name)
    
    with open(report_path, "w") as f:
        json.dump(report, f, indent=4)
    
    print(f"✅ Report saved: {file_name}")
    print(f"   Extraction: {extraction_completeness:.1f}% | Validation: {validation_accuracy:.1f}%")
    print(f"   Success: {pipeline_success} | Errors: {len(errors)} | Repairs: {repair_attempts}")

    # Add trace entry
    state["trace_log"].append({
        "agent": "reporter",
        "status": "completed",
        "report_path": file_name,
        "metrics": {
            "extraction_completeness": f"{extraction_completeness:.2f}%",
            "validation_accuracy": f"{validation_accuracy:.2f}%",
            "pipeline_success": pipeline_success
        }
    })

    return state
