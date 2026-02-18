import json
import re
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from app.llm_client import UnifiedLLMManager
from app.state import DocState
from app.schemas.prescription_schema import PrescriptionSchema
from app.schemas.lab_report_schema import LabReportSchema

# Wrapper models for structured extraction output


class ExtractionOutput(BaseModel):
    """Wrapper for extraction output with confidence."""
    document_type: str = Field(description="The document type being extracted")
    confidence_score: float = Field(
        description="Confidence score between 0.0 and 1.0",
        ge=0.0,
        le=1.0
    )
    data: dict = Field(description="Extracted structured data")


# Enhanced specialized prompts for different document types
PROMPT_TEMPLATES = {
    "prescription": """You are an advanced Medical Document Intelligence Agent specializing in Prescriptions.

TASK: Extract structured data from the document with 100% accuracy.

REQUIRED FIELDS:
1. doctor (object):
   - name: doctor's full name (e.g., "Dr. Gregory House")
   - license_number: Medical license (Format: StateCode-Digits e.g., "MH-12345")
   - dea_number: DEA number if present (required for controlled substances)
   - specialization: doctor's specialization if mentioned
2. patient (object):
   - name: patient's full name
   - id: patient ID (Format: PT#####, e.g., "PT12345")
   - age: integer age
   - weight: weight in kg if mentioned (important for pediatric dosing)
   - gender: patient's gender (Male/Female)
3. medications (list of objects):
   - name: generic or brand name (e.g., "Amoxicillin")
   - dosage: strength with unit (CRITICAL: Use ONLY valid pharmaceutical units - see examples below)
   - frequency: intake instructions (e.g., "3 times daily")
   - duration: treatment length (e.g., "7 days")
   - refills: number of refills allowed (default 0)

VALID DOSAGE UNITS (Use ONLY these):
For ORAL medications (tablets, capsules, liquid): mg, ml, g, mcg, ug, iu, u, tablet, tablets, capsule, capsules, pill, pills
For IV/IM injections: mg, ml, mcg, ug, iu, units
For topical: mg, ml, g, %
For patches: mcg/hr, mg/hr
INVALID units for oral medications: liters, kg, cm, inches, %volume, dL, L

EXTRACTION RULE - EXTRACT AS-IS:
- Extract dosage EXACTLY as written in the document, even if it appears incorrect
- DO NOT convert or "fix" units during extraction (e.g., if it says "7 liters", extract "7 liters")
- Validation and repair will happen in later pipeline stages
- Your job is accurate extraction, not correction

EXAMPLES OF EXTRACTION (extract what you see):
Document says "Amoxicillin 7 liters" → Extract: "7 liters" (don't convert to mg)
Document says "Paracetamol 27 liters" → Extract: "27 liters" (don't convert to tablets)
Document says "Aspirin 500mg" → Extract: "500mg" (correct, no change needed)

4. diagnosis: medical diagnosis or indication if present
5. date: prescription date in any format
6. follow_up_date: follow-up appointment date if mentioned (any format)

SPECIAL ATTENTION:
- EXTRACT dosages exactly as written - do not convert or correct during extraction
- Capture specific instructions for Pediatric (child) or Geriatric (elderly) patients if mentioned.
- Look for DEA Number if controlled substances (e.g., Morphine) are present.
- Apply fuzzy matching for medical entities if text is noisy or handwritten.

CRITICAL OUTPUT FORMAT RULES:
1. Output MUST be pure, valid JSON only - no markdown, no code blocks, no explanations
2. NEVER include JSON comments (// or /* */) - they are invalid and will cause parsing errors
3. Do NOT add explanatory notes like "// Corrected from..." or "// Note: ..."
4. Do NOT wrap output in ```json or ``` markers
5. Just return the raw JSON object matching the schema

{format_instructions}""",

    "lab_report": """You are an advanced Medical Document Intelligence Agent specializing in Lab Reports.

TASK: Extract structured data from the lab report with 100% accuracy.

REQUIRED FIELDS:
1. lab (object):
   - name: name of the laboratory
   - address: lab address
   - accreditation: lab accreditation or CLIA number (e.g., "CLIA 10D1234567" or "CAP Accredited")
   - pathologist_name: name of the pathologist who validated/signed the report (extract actual name, if you see "N/A" or blank, extract "N/A")
   - has_pathologist_signature: boolean (True if pathologist name is present and valid (NOT "N/A"), OR you see "digitally signed by", "validated by", signature line, or stamp)
2. report_id: unique report identifier (Format: LAB######, e.g., "LAB123456")
3. sample_type: type of specimen (e.g., "Serum", "Plasma", "Whole Blood", "Urine", "CSF") - CRITICAL for test interpretation
4. collection_date: Date sample collected (any format)
5. report_date: Date report issued (any format)
6. test_results (list of objects):
   - test_name: name of the analyte (e.g., "Hemoglobin")
   - value: numeric or string result (e.g., "14.5")
   - unit: measurement unit (e.g., "g/dL", "mg/dL", "cells/mcL", "pg/mL", "U/L", "mmol/L", "ng/mL")
   - reference_range: normal range string (e.g., "12.0 - 18.0")
   - status: Interpretation (Normal, High, Low, Critical, Extreme)
7. is_amended: boolean (True if this is an AMENDED/CORRECTED report)

STANDARD LAB UNITS (Extract exactly as shown - these are all valid):
- Hematology: g/dL, cells/mcL, cells/μL, 10^3/μL, 10^6/μL, fL, pg, %
- Chemistry: mg/dL, mmol/L, mEq/L, U/L, IU/L, μg/dL, ng/mL, pg/mL
- Lipids: mg/dL, mmol/L
- Vitamins: ng/mL, pg/mL, nmol/L, μg/L
- Hormones: mIU/L, ng/dL, pg/mL, pmol/L

SPECIAL ATTENTION:
- CRITICAL: Extract pathologist name exactly as shown. If it says "N/A" or is blank, set pathologist_name to "N/A".
- CRITICAL: Set has_pathologist_signature to TRUE if pathologist name is a valid name (like "Dr. Kumar", "Dr. Smith"). Only set to FALSE if pathologist name is "N/A" or missing.
- CRITICAL: Extract sample type - look for "Sample Type:", "Specimen:", "Sample:" labels.
- CRITICAL: Extract units EXACTLY as written - do NOT modify or convert units (e.g., "cells/mcL" stays "cells/mcL", "pg/mL" stays "pg/mL").
- Detect if report is an AMENDED report (look for "AMENDED" or "CORRECTED").
- Note any critical/panic ranges explicitly listed.
- Apply fuzzy matching if text contains OCR noise.

CRITICAL OUTPUT FORMAT RULES:
1. Output MUST be pure, valid JSON only - no markdown, no code blocks, no explanations
2. NEVER include JSON comments (// or /* */) - they are invalid and will cause parsing errors
3. Do NOT add explanatory notes like "// Note: ..." or "// Extracted from..."
4. Do NOT wrap output in ```json or ``` markers
5. Just return the raw JSON object matching the schema

{format_instructions}"""
}


def extract_data(state: DocState) -> DocState:
    """
    Agent: Extractor
    Logic: Uses specialized prompts with structured output parsing to extract data from raw text.
    """
    # Initialize LLM manager with provider from state
    llm_manager = UnifiedLLMManager(provider=state.get("llm_provider"))

    doc_type = (state.get("doc_type") or "other").lower().strip()
    print(f"--- 📝 Agent: Extractor ({doc_type}) ---")

    # Handle unsupported types early
    if doc_type not in PROMPT_TEMPLATES:
        state["errors"].append(
            f"Unsupported document type for extraction: {doc_type}")
        state["trace_log"].append(
            {"agent": "extractor", "status": "skipped", "reason": "unsupported_type"})
        return state

    # Setup structured output parser based on document type
    if doc_type == "prescription":
        parser = PydanticOutputParser(pydantic_object=PrescriptionSchema)
    elif doc_type == "lab_report":
        parser = PydanticOutputParser(pydantic_object=LabReportSchema)
    else:
        state["errors"].append(f"No parser configured for: {doc_type}")
        return state

    # Build system prompt with format instructions
    system_prompt = PROMPT_TEMPLATES[doc_type].format(
        format_instructions=parser.get_format_instructions()
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Document Text:\n\n{state['raw_text']}")
    ]

    try:
        # Invoke LLM with fallback
        response = llm_manager.invoke_with_fallback(messages)
        content = response.content.strip()

        # Try to extract JSON first to handle wrapped responses
        data_to_parse = content
        start = content.find('{')
        end = content.rfind('}')

        if start != -1 and end != -1:
            clean_content = content[start:end+1]
            try:
                json_data = json.loads(clean_content)
                # If it's wrapped with "data" field, extract it
                if "data" in json_data and isinstance(json_data["data"], dict):
                    # Convert the data part back to JSON string for the parser
                    data_to_parse = json.dumps(json_data["data"])
                    stored_confidence = float(
                        json_data.get("confidence_score", 0.7))
                else:
                    stored_confidence = None
            except json.JSONDecodeError:
                stored_confidence = None
        else:
            stored_confidence = None

        # Parse structured output using LangChain parser
        parsed_data = parser.parse(data_to_parse)

        # Convert Pydantic model to dict
        state["extracted_data"] = parsed_data.model_dump(exclude_none=False)

        # Calculate confidence based on completeness or use stored value
        if stored_confidence is not None:
            state["confidence_score"] = stored_confidence
        else:
            total_fields = len(parsed_data.model_dump())
            filled_fields = len([v for v in parsed_data.model_dump().values(
            ) if v is not None and v != "" and v != [] and v != {}])
            state["confidence_score"] = round(
                filled_fields / total_fields, 2) if total_fields > 0 else 0.5

        state["trace_log"].append({
            "agent": f"extractor_{doc_type}",
            "status": "success",
            "confidence": state["confidence_score"],
            "fields_found": list(state["extracted_data"].keys()),
            "parser": "PydanticOutputParser"
        })

    except Exception as e:
        # Fallback to manual JSON parsing if structured parsing fails
        print(
            f"⚠️ Structured parsing failed: {e}, trying manual JSON extraction...")
        try:
            content = response.content.strip()
            start = content.find('{')
            end = content.rfind('}')

            if start != -1 and end != -1:
                clean_content = content[start:end+1]
                extracted_resp = json.loads(clean_content)

                # Handle guide-compliant nested structure
                if "data" in extracted_resp:
                    state["extracted_data"] = extracted_resp["data"]
                    state["confidence_score"] = float(
                        extracted_resp.get("confidence_score", 0.7))
                else:
                    # Fallback for non-compliant outputs
                    state["extracted_data"] = extracted_resp
                    state["confidence_score"] = 0.6

                state["trace_log"].append({
                    "agent": f"extractor_{doc_type}",
                    "status": "success_fallback",
                    "confidence": state["confidence_score"],
                    "parser": "manual_json"
                })
            else:
                raise ValueError("No valid JSON found in response")

        except Exception as fallback_error:
            error_msg = f"Extraction parse error: {str(e)}, Fallback error: {str(fallback_error)}"
            state["errors"].append(error_msg)
            state["trace_log"].append(
                {"agent": "extractor", "status": "failed", "error": error_msg})

    return state
