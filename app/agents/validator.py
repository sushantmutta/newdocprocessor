from app.schemas.prescription_schema import PrescriptionSchema
from app.schemas.lab_report_schema import LabReportSchema
from app.state import DocState
from pydantic import ValidationError

# Mapping doc types to their specific Pydantic models
SCHEMA_MAP = {
    "prescription": PrescriptionSchema,
    "lab_report": LabReportSchema
}


def validate_data(state: DocState) -> DocState:
    """
    Validates extracted data against medical schemas.
    Generates validation_flags for clinical alerts and compliance issues.
    """
    doc_type = state.get("doc_type")
    print(f"--- ✅ Agent: Validator ({doc_type}) ---")

    data = state.get("extracted_data")
    
    # Initialize validation flags if not present
    if "validation_flags" not in state:
        state["validation_flags"] = []

    # Early exit if no data
    if not data:
        error_msg = "No data extracted to validate."
        state["errors"].append(error_msg)
        state["trace_log"].append({
            "agent": "validator",
            "status": "skipped",
            "reason": "no_data"
        })
        return state

    # Check for schema support
    schema_class = SCHEMA_MAP.get(doc_type)
    if not schema_class:
        error_msg = f"No validation schema for document type: {doc_type}"
        state["errors"].append(error_msg)
        state["trace_log"].append({
            "agent": "validator",
            "status": "skipped",
            "reason": "unsupported_type",
            "doc_type": doc_type
        })
        print(f"⚠️ {error_msg}")
        return state

    # Create instance anyway to run clinical checks if possible
    # We use .model_validate(data, from_attributes=True) or similar
    # But simpler: make fields optional in schemas and handle None in checks.
    
    try:
        # Pydantic validates and cleans the data
        validated_obj = schema_class(**data)
        state["validated_data"] = validated_obj.model_dump()
        
        # --- Perform Medical Validation Checks and Generate Flags ---
        flags = []
        
        if doc_type == "prescription":
            flags.extend(validated_obj.check_extreme_dosage())
            flags.extend(validated_obj.check_controlled_substances())
            flags.extend(validated_obj.check_pediatric_dosing())
            flags.extend(validated_obj.check_geriatric_polypharmacy())
            flags.extend(validated_obj.check_missing_dosage())
            flags.extend(validated_obj.check_unit_standards())
            flags.extend(validated_obj.check_mandatory_fields())

        elif doc_type == "lab_report":
            flags.extend(validated_obj.check_date_consistency())
            flags.extend(validated_obj.check_amended_status())
            flags.extend(validated_obj.check_critical_values())
            flags.extend(validated_obj.check_extreme_values())
            flags.extend(validated_obj.check_pathologist_signature())
            flags.extend(validated_obj.check_unit_standards())
            flags.extend(validated_obj.check_mandatory_fields())

        # Sync with state
        state["validation_flags"] = flags
        
        state["trace_log"].append({
            "agent": "validator",
            "status": "passed",
            "schema": schema_class.__name__,
            "flags_generated": len(flags)
        })

    except ValidationError as e:
        # If schema validation fails, we still want to try to flag what we can
        # For now, let's just log the errors as flags for visibility
        error_flags = []
        for err in e.errors():
            loc = err['loc']
            field_name = loc[0] if loc else "root"
            error_flags.append({
                "code": f"INVALID_{field_name.upper()}",
                "message": f"Validation Error: {field_name} - {err['msg']}",
                "severity": "HIGH"
            })
        
        state["validation_flags"].extend(error_flags)
        state["errors"].extend([f["message"] for f in error_flags])
        
        state["trace_log"].append({
            "agent": "validator",
            "status": "failed",
            "schema": schema_class.__name__,
            "error_count": len(error_flags)
        })

    return state
