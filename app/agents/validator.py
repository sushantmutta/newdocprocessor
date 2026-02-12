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

    try:
        # Pydantic validates and cleans the data
        validated_obj = schema_class(**data)
        state["validated_data"] = validated_obj.model_dump()
        
        # Clear ONLY validation errors from Pydantic checks
        state["errors"] = [
            err for err in state.get("errors", [])
            if not any(err.startswith(f"{field}:") for field in data.keys())
        ]
        
        # --- Perform Medical Validation Checks and Generate Flags ---
        flags = []
        
        if doc_type == "prescription":
            # Check for controlled substances (now checks for DEA)
            warnings = validated_obj.check_controlled_substances()
            for w in warnings:
                flags.append({
                    "code": "CONTROLLED_SUBSTANCE",
                    "message": w,
                    "severity": "HIGH"  # DEA missing for controlled substance is high risk
                })
            
            # Check for pediatric dosing (now checks for weight)
            warnings = validated_obj.check_pediatric_dosing()
            for w in warnings:
                code = "PEDIATRIC_DOSING" if "WEIGHT" not in w else "MISSING_PEDIATRIC_WEIGHT"
                flags.append({
                    "code": code,
                    "message": w,
                    "severity": "MEDIUM"
                })

        elif doc_type == "lab_report":
            # Check for date consistency
            warnings = validated_obj.check_date_consistency()
            for w in warnings:
                flags.append({
                    "code": "DATE_INCONSISTENCY",
                    "message": w,
                    "severity": "MEDIUM"
                })
            
            # Check for amended status (New)
            warnings = validated_obj.check_amended_status()
            for w in warnings:
                flags.append({
                    "code": "AMENDED_REPORT",
                    "message": w,
                    "severity": "LOW"
                })

            # Check for critical values
            criticals = validated_obj.check_critical_values()
            for c in criticals:
                flags.append({
                    "code": "CRITICAL_VALUE",
                    "message": c,
                    "severity": "CRITICAL"
                })

        # Add PII check (simulated based on logic, usually comes from Redactor but we can flag here if needed)
        # For now, we rely on the specific schema methods

        state["validation_flags"].extend(flags)
        
        state["trace_log"].append({
            "agent": "validator",
            "status": "passed",
            "schema": schema_class.__name__,
            "flags_generated": len(flags),
            "flags": flags
        })
        
        print(f"✅ Validation passed: {len(flags)} medical alerts generated")

    except ValidationError as e:
        # Extract detailed error messages
        error_messages = []
        for err in e.errors():
            loc = err['loc']
            field_name = loc[0] if loc else "root"
            error_messages.append(f"{field_name}: {err['msg']}")
        
        # Append validation errors
        state["errors"].extend(error_messages)
        
        state["trace_log"].append({
            "agent": "validator",
            "status": "failed",
            "schema": schema_class.__name__,
            "error_count": len(error_messages),
            "errors": error_messages
        })
        
        print(f"⚠️ Validation failed for {doc_type}: {len(error_messages)} errors")
        for err_msg in error_messages:
            print(f"   - {err_msg}")

    return state
