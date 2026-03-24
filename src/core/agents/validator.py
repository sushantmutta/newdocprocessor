from src.core.schemas.prescription_schema import PrescriptionSchema
from src.core.schemas.lab_report_schema import LabReportSchema
from src.core.state import DocState
from pydantic import ValidationError

# Mapping doc types to their specific Pydantic models
SCHEMA_MAP = {
    "prescription": PrescriptionSchema,
    "lab_report": LabReportSchema
}


def _is_near_empty_extraction(doc_type: str | None, data: dict | None) -> bool:
    if not data or not isinstance(data, dict):
        return True

    doc_type = (doc_type or "").lower()
    if doc_type == "prescription":
        doctor = data.get("doctor") if isinstance(
            data.get("doctor"), dict) else {}
        patient = data.get("patient") if isinstance(
            data.get("patient"), dict) else {}
        meds = data.get("medications") if isinstance(
            data.get("medications"), list) else []
        return not doctor.get("name") and not patient.get("name") and len(meds) == 0

    if doc_type == "lab_report":
        lab = data.get("lab") if isinstance(data.get("lab"), dict) else {}
        tests = data.get("test_results") if isinstance(
            data.get("test_results"), list) else []
        return not lab.get("name") and len(tests) == 0

    return len(data.keys()) == 0


def validate_data(state: DocState) -> DocState:
    """
    Validates extracted data against medical schemas.
    Generates validation_flags for clinical alerts and compliance issues.
    """
    doc_type = state.get("doc_type")
    print(f"--- ✅ Agent: Validator ({doc_type}) ---")

    data = state.get("extracted_data")
    state.setdefault("schema_validation_failed", False)
    state.setdefault("validation_error_message", None)
    state["extraction_empty"] = _is_near_empty_extraction(doc_type, data)

    # Initialize validation flags if not present
    if "validation_flags" not in state:
        state["validation_flags"] = []

    # Early exit if no data
    if not data:
        error_msg = "No data extracted to validate."
        state["errors"].append(error_msg)
        state["extraction_empty"] = True
        state["review_required"] = True
        reasons = list(state.get("review_reason") or [])
        reasons.append("extraction empty")
        state["review_reason"] = list(dict.fromkeys(reasons))
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
            flags.extend(validated_obj.check_date_consistency())
            flags.extend(validated_obj.check_extreme_dosage())
            flags.extend(validated_obj.check_controlled_substances())
            flags.extend(validated_obj.check_pediatric_dosing())
            flags.extend(validated_obj.check_polypharmacy())
            flags.extend(validated_obj.check_geriatric_polypharmacy())
            flags.extend(validated_obj.check_missing_dosage())
            flags.extend(validated_obj.check_unit_standards())
            flags.extend(validated_obj.check_mandatory_fields())
            flags.extend(validated_obj.check_date_formats())
            flags.extend(validated_obj.check_inconsistent_dosage())
            flags.extend(validated_obj.check_ambiguous_values())

        elif doc_type == "lab_report":
            flags.extend(validated_obj.check_date_consistency())
            flags.extend(validated_obj.check_amended_status())
            flags.extend(validated_obj.check_critical_values())
            flags.extend(validated_obj.check_out_of_range_values())
            flags.extend(validated_obj.check_extreme_values())
            flags.extend(validated_obj.check_missing_reference_ranges())
            flags.extend(validated_obj.check_sample_type())
            flags.extend(validated_obj.check_pathologist_signature())
            flags.extend(validated_obj.check_unit_standards())
            flags.extend(validated_obj.check_mandatory_fields())
            flags.extend(validated_obj.check_date_formats())
            flags.extend(validated_obj.check_ambiguous_values())

        # Sync with state
        state["validation_flags"] = flags

        state["trace_log"].append({
            "agent": "validator",
            "status": "passed",
            "schema": schema_class.__name__,
            "flags_generated": len(flags)
        })

    except ValidationError as e:
        state["schema_validation_failed"] = True
        state["review_required"] = True
        state["validation_error_message"] = str(e)
        reasons = list(state.get("review_reason") or [])
        reasons.append("schema validation failed")
        state["review_reason"] = list(dict.fromkeys(reasons))

        # Map Pydantic errors to repair-compatible flag codes
        error_flags = []
        for err in e.errors():
            loc = err['loc']
            field_name = ".".join(str(x) for x in loc) if loc else "root"
            err_type = err.get("type", "")
            if err_type in ("date_parsing", "date_from_datetime_parsing"):
                code = "INVALID_DATE_FORMAT"
            elif err_type == "missing":
                code = "MISSING_REQUIRED_FIELD"
            elif err_type in ("value_error", "type_error", "string_type", "int_type", "float_type"):
                code = "AMBIGUOUS_VALUE"
            else:
                code = f"INVALID_{field_name.upper().replace('.', '_')}"
            error_flags.append({
                "code": code,
                "message": f"Schema Validation: {field_name} - {err['msg']}",
                "severity": "HIGH",
                "field": field_name,
                "value": err.get("input")
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
