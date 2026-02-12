import json
from langchain_core.messages import HumanMessage, SystemMessage
from app.llm_client import UnifiedLLMManager
from app.state import DocState

# Enhanced specialized prompts for different document types
PROMPTS = {
    "prescription": """You are an advanced Medical Document Intelligence Agent specializing in Prescriptions.

TASK: Extract structured data from the document with 100% accuracy.

REQUIRED FIELDS:
1. doctor (object):
   - name: doctor's full name (e.g., "Dr. Gregory House")
   - license_number: Medical license (Format: StateCode-Digits e.g., "MH-12345")
2. patient (object):
   - name: patient's full name
   - id: patient ID (Format: PT#####, e.g., "PT12345")
   - age: integer age
   - gender: patient's gender (Male/Female)
3. medications (list of objects):
   - name: generic or brand name (e.g., "Amoxicillin")
   - dosage: strength with unit (e.g., "500mg")
   - frequency: intake instructions (e.g., "3 times daily")
   - duration: treatment length (e.g., "7 days")

SPECIAL ATTENTION:
- Capture specific instructions for Pediatric (child) or Geriatric (elderly) patients if mentioned.
- Look for DEA Number if controlled substances (e.g., Morphine) are present.
- Apply fuzzy matching for medical entities if text is noisy or handwritten.

OUTPUT FORMAT: Return a JSON object with:
- "document_type": "PRESCRIPTION"
- "confidence_score": 0.0-1.0
- "data": { ...extracted_fields... }""",

    "lab_report": """You are an advanced Medical Document Intelligence Agent specializing in Lab Reports.

TASK: Extract structured data from the lab report with 100% accuracy.

REQUIRED FIELDS:
1. lab (object):
   - name: name of the laboratory
   - report_id: unique report identifier (Format: LAB######, e.g., "LAB123456")
   - address: lab address
   - accreditation: lab accreditation or CLIA number (e.g., "CLIA 10D1234567" or "CAP Accredited")
   - has_pathologist_signature: boolean (True if you see "digitally signed by", "validated by", a names stamp, or signature image/line)
2. dates (object):
   - collection_date: Date sample collected (YYYY-MM-DD)
   - report_date: Date report issued (YYYY-MM-DD)
3. test_results (list of objects):
   - test_name: name of the analyte (e.g., "Hemoglobin")
   - value: numeric or string result (e.g., "14.5")
   - unit: measurement unit (e.g., "g/dL")
   - reference_range: normal range string (e.g., "12.0 - 18.0")
   - status: Interpretation (Normal, High, Low, Critical, Extreme)

SPECIAL ATTENTION:
- Detect if report is an AMENDED report (look for "AMENDED" or "CORRECTED").
- Note any critical/panic ranges explicitly listed.
- Apply fuzzy matching if text contains OCR noise.

OUTPUT FORMAT: Return a JSON object with:
- "document_type": "LAB_REPORT"
- "confidence_score": 0.0-1.0
- "data": { ...extracted_fields... }"""
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
        content = response.content.strip()
        
        # Robust JSON extraction: Find first '{' and last '}'
        start = content.find('{')
        end = content.rfind('}')
        
        if start != -1 and end != -1:
            clean_content = content[start:end+1]
        else:
            clean_content = content

        extracted_resp = json.loads(clean_content)

        # Handle guide-compliant nested structure
        if "data" in extracted_resp:
            state["extracted_data"] = extracted_resp["data"]
            state["confidence_score"] = float(extracted_resp.get("confidence_score", 0.85))
        else:
            # Fallback for non-compliant outputs
            state["extracted_data"] = extracted_resp
            state["confidence_score"] = 0.7 # Lower confidence if structure is unexpected

        state["trace_log"].append({
            "agent": f"extractor_{doc_type}",
            "status": "success",
            "confidence": state["confidence_score"],
            "fields_found": list(state["extracted_data"].keys())
        })

    except Exception as e:
        error_msg = f"Extraction parse error: {str(e)}"
        state["errors"].append(error_msg)
        state["trace_log"].append(
            {"agent": "extractor", "status": "failed", "error": error_msg})

    return state
