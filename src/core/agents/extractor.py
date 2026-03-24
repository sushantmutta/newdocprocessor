import json
import re
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from src.core.clients.llm_client import UnifiedLLMManager
from src.core.state import DocState
from src.core.schemas.prescription_schema import PrescriptionSchema
from src.core.schemas.lab_report_schema import LabReportSchema
from src.core.prompts import EXTRACTOR_PROMPT_TEMPLATES, EXTRACTOR_HUMAN_PROMPT

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
PROMPT_TEMPLATES = EXTRACTOR_PROMPT_TEMPLATES


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
        # Unknown/non-medical docs should be routed by review gate without
        # forcing extractor hard-errors.
        state.setdefault("extracted_data", {})
        state["confidence_score"] = float(state.get("confidence_score") or 0.0)
        state["trace_log"].append(
            {
                "agent": "extractor",
                "status": "skipped",
                "reason": "unsupported_type",
                "doc_type": doc_type,
            }
        )
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
        HumanMessage(content=EXTRACTOR_HUMAN_PROMPT.format(
            raw_text=state['raw_text']))
    ]

    # Optional HITL hint used by re_extract decision path.
    hint_prompt = (state.get("hint_prompt") or "").strip()
    if hint_prompt:
        messages.append(
            HumanMessage(
                content=f"Human review hint for re-extraction: {hint_prompt}"
            )
        )

    try:
        # Invoke LLM with fallback
        response = llm_manager.invoke_with_fallback(messages)
        if llm_manager.fallback_was_used():
            state["llm_fallback_used"] = True
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
            if llm_manager.fallback_was_used():
                state["llm_fallback_used"] = True
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
