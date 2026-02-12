from app.schemas.invoice_schema import InvoiceSchema
from app.schemas.base_schema import IDCardSchema
from app.state import DocState
from pydantic import ValidationError

# Mapping doc types to their specific Pydantic models
SCHEMA_MAP = {
    "invoice": InvoiceSchema,
    "id_card": IDCardSchema
}


def validate_data(state: DocState) -> DocState:
    """
    Validates extracted data against document-specific Pydantic schemas.
    Appends validation errors without clearing previous agent errors.
    """
    doc_type = state.get("doc_type")
    print(f"--- ✅ Agent: Validator ({doc_type}) ---")

    data = state.get("extracted_data")
    
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
        
        # Clear ONLY validation errors, keep other errors
        state["errors"] = [
            err for err in state.get("errors", [])
            if not any(err.startswith(f"{field}:") for field in data.keys())
        ]
        
        state["trace_log"].append({
            "agent": "validator",
            "status": "passed",
            "schema": schema_class.__name__,
            "fields_validated": list(validated_obj.model_dump().keys()),
            "field_count": len(validated_obj.model_dump())
        })
        
        print(f"✅ Validation passed: {len(validated_obj.model_dump())} fields validated")

    except ValidationError as e:
        # Extract detailed error messages for RepairAgent
        error_messages = [
            f"{err['loc'][0]}: {err['msg']}" for err in e.errors()
        ]
        
        # Append validation errors (don't overwrite)
        state["errors"].extend(error_messages)
        
        # Detailed trace with error breakdown
        state["trace_log"].append({
            "agent": "validator",
            "status": "failed",
            "schema": schema_class.__name__,
            "error_count": len(error_messages),
            "errors": error_messages,
            "failed_fields": [err['loc'][0] for err in e.errors()]
        })
        
        print(f"⚠️ Validation failed for {doc_type}: {len(error_messages)} errors")
        for err_msg in error_messages:
            print(f"   - {err_msg}")

    return state
