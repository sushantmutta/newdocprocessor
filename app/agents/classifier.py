from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from app.llm_client import UnifiedLLMManager
from app.state import DocState


class DocumentClassification(BaseModel):
    """Structured output for document classification."""
    document_type: str = Field(
        description="The classified document type: PRESCRIPTION, LAB_REPORT, or UNKNOWN"
    )
    confidence: float = Field(
        description="Confidence score between 0.0 and 1.0",
        ge=0.0,
        le=1.0
    )
    reasoning: str = Field(
        description="Brief explanation of the classification decision"
    )


def classify_doc(state: DocState) -> DocState:
    """
    Determines document type using LLM with enhanced prompting and structured output parsing.
    Routes to: [prescription, lab_report, unknown]
    """
    # Initialize LLM manager with provider from state
    llm_manager = UnifiedLLMManager(provider=state.get("llm_provider"))

    print(f"--- 🔍 Agent: Classifier ({llm_manager.provider_name}) ---")

    # Access the model name dynamically from the manager
    active_model = getattr(llm_manager, 'model_name', 'unknown')

    # Setup structured output parser
    parser = PydanticOutputParser(pydantic_object=DocumentClassification)

    system_prompt = f"""You are an advanced Medical Document Intelligence Agent. Your goal is to accurately classify documents.

### CLASSIFICATION TASK
Analyze the document structure to determine its type EXACTLY as one of the following:

- **PRESCRIPTION**: Contains "Rx" symbol, doctor details (Name, License), and medication list.
- **LAB_REPORT**: Contains "Test Results", reference ranges, and lab accreditation.
- **UNKNOWN**: If neither pattern matches.

CLASSIFICATION RULES:
1. Look for key indicators:
   - Prescription: "Rx" symbol (☤), "Doctor Name", "License Number", "Patient Name", "Medication List", "Dosage", "Sig"
   - Lab Report: "Test Results", "Reference Range", "Lab Name", "Collection Date", "Report Date", "Analyte", "Specimen"
2. If uncertain or ambiguous, default to "UNKNOWN".

{parser.get_format_instructions()}"""

    # Send a snippet to minimize token usage
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=f"Classify this document text:\n\n{state['raw_text'][:2000]}")
    ]

    try:
        response = llm_manager.invoke_with_fallback(messages)
        content = response.content.strip()

        # Try structured parsing first
        try:
            classification = parser.parse(content)
            doc_type = classification.document_type.upper()
            confidence = classification.confidence
        except Exception:
            # Fallback: Check if response is just a simple text classification
            content_upper = content.upper()
            if content_upper in ['PRESCRIPTION', 'LAB_REPORT', 'UNKNOWN']:
                doc_type = content_upper
                confidence = 0.8
            elif 'PRESCRIPTION' in content_upper:
                doc_type = 'PRESCRIPTION'
                confidence = 0.75
            elif 'LAB_REPORT' in content_upper or 'LAB REPORT' in content_upper:
                doc_type = 'LAB_REPORT'
                confidence = 0.75
            else:
                doc_type = 'UNKNOWN'
                confidence = 0.5

        # Validate output
        if doc_type not in ['PRESCRIPTION', 'LAB_REPORT', 'UNKNOWN']:
            print(
                f"⚠️ Invalid classification '{doc_type}', defaulting to 'UNKNOWN'")
            doc_type = 'UNKNOWN'
            confidence = 0.5

    except Exception as e:
        print(f"⚠️ Classification failed: {e}, defaulting to 'UNKNOWN'")
        doc_type = 'UNKNOWN'
        confidence = 0.3

    # Update State
    state["doc_type"] = doc_type.lower()
    state["confidence_score"] = confidence

    # Log for Responsible AI reporting
    state["trace_log"].append({
        "agent": "classifier",
        "output": doc_type,
        "confidence": confidence,
        "model": active_model,
        "provider": llm_manager.provider_name
    })

    return state
