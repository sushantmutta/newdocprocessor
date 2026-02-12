import json
from langchain_core.messages import HumanMessage, SystemMessage
from app.llm_client import UnifiedLLMManager
from app.state import DocState

# Enhanced specialized prompts for different document types
PROMPTS = {
    "prescription": """You are a specialized medical prescription extraction system.

TASK: Extract structured data from the prescription with 100% accuracy.

REQUIRED FIELDS:
1. date (string): Date of prescription (any format).

2. doctor (object):
   - name: doctor's full name (e.g., "Dr. Gregory House")
   - license_number: Medical license (Format: StateCode-Digits e.g., "MH-12345")
   - dea_number: DEA Registration Number if present (Format: 2 letters + 7 digits, e.g., "AB1234567")
   - specialization: doctor's medical specialty

3. patient (object):
   - name: patient's full name
   - id: patient ID (Format: PT#####, e.g., "PT12345")
   - age: integer age
   - weight: float weight in kg (CRITICAL for pediatric dosing)
   - gender: patient's gender (Male/Female)

4. diagnosis (string): Medical indication or diagnosis if stated.

5. medications (list of objects):
   - name: generic or brand name
   - dosage: strength with unit (MUST be standard units: mg, ml, g, mcg, iu, tablet). Reject "liters" or invalid units.
   - frequency: how often (e.g., "BID", "twice daily")
   - duration: how long (e.g., "7 days")
   - refills: number of refills allowed

EXTRACTION RULES:
- Use null if a field is not found.
- DEA number is MANDATORY for controlled substances (Morphine, etc).
- Weight is MANDATORY for patients under 12.

OUTPUT FORMAT: Return ONLY a raw JSON object.""",

    "lab_report": """You are a specialized lab report extraction system.

TASK: Extract structured data from the medical lab report with 100% accuracy.

REQUIRED FIELDS:
1. lab (object):
   - name: name of the laboratory
   - address: lab address
   - accreditation: CLIA or CAP number

2. patient (object):
   - name: patient's full name
   - dob: date of birth
   - mrn: medical record number
   - patient_id: internal ID

3. report_id: unique report identifier (Format: LAB######, e.g., "LAB123456")
4. is_amended (boolean): Set to true ONLY if document contains "AMENDED REPORT" or "CORRECTED REPORT".
5. collection_date: Date sample collected.
6. report_date: Date report issued.

7. test_results (list of objects):
   - test_name: name of the analyte
   - value: numeric or string result
   - unit: measurement unit (e.g., "g/dL")
   - reference_range: normal range string (e.g., "12.0 - 16.0")
   - status: Explicit status from report. MUST be one of: "Normal", "High", "Low", "Critical", "Extreme".

EXTRACTION RULES:
- If status is not explicit, derive it from reference range.
- Mark status as "Critical" or "Extreme" if the report creates urgency (often red text or ALL CAPS).
- Normalize dates where possible, but return original string if ambiguous.

OUTPUT FORMAT: Return ONLY a raw JSON object."""
}


def extract_data(state: DocState) -> DocState:
    """
    Agent: Extractor
    Logic: Uses specialized prompts to extract structured JSON from raw text.
    """
    # Initialize LLM manager with provider from state
    llm_manager = UnifiedLLMManager(provider=state.get("llm_provider"))
    
    doc_type = (state.get("doc_type") or "other").lower().strip()
    print(f"--- 📝 Agent: Extractor ({doc_type}) ---")

    # Handle unsupported types early
    if doc_type not in PROMPTS:
        state["errors"].append(
            f"Unsupported document type for extraction: {doc_type}")
        state["trace_log"].append(
            {"agent": "extractor", "status": "skipped", "reason": "unsupported_type"})
        return state

    # Use the enhanced prompt directly
    system_prompt = PROMPTS[doc_type]

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Document Text:\n\n{state['raw_text']}")
    ]

    # Invoke LLM with fallback
    response = llm_manager.invoke_with_fallback(messages)

    try:
        # Clean the response string of any common LLM debris
        clean_content = response.content.replace(
            "```json", "").replace("```", "").strip()
        extracted_json = json.loads(clean_content)

        state["extracted_data"] = extracted_json
        state["trace_log"].append({
            "agent": f"extractor_{doc_type}",
            "status": "success",
            "fields_found": list(extracted_json.keys())
        })

    except Exception as e:
        error_msg = f"Extraction parse error: {str(e)}"
        state["errors"].append(error_msg)
        state["trace_log"].append(
            {"agent": "extractor", "status": "failed", "error": error_msg})

    return state
