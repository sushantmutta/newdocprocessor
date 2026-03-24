from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from src.core.clients.llm_client import UnifiedLLMManager
from src.core.state import DocState
from src.core.prompts import CLASSIFIER_SYSTEM_PROMPT, CLASSIFIER_HUMAN_PROMPT


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

    system_prompt = CLASSIFIER_SYSTEM_PROMPT.format(
        format_instructions=parser.get_format_instructions()
    )

    # Send a snippet to minimize token usage
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=CLASSIFIER_HUMAN_PROMPT.format(raw_text=state['raw_text'][:2000]))
    ]

    classification_status = "completed"

    try:
        response = llm_manager.invoke_with_fallback(messages)
        if llm_manager.fallback_was_used():
            state["llm_fallback_used"] = True
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
        classification_status = "failed"

    # Update State
    state["doc_type"] = doc_type.lower()
    state["confidence_score"] = confidence

    # Log for Responsible AI reporting
    state["trace_log"].append({
        "agent": "classifier",
        "status": classification_status,
        "output": doc_type,
        "confidence": confidence,
        "model": active_model,
        "provider": llm_manager.provider_name
    })

    return state
