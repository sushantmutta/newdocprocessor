from langchain_core.messages import HumanMessage, SystemMessage
from app.llm_client import UnifiedLLMManager
from app.state import DocState


def classify_doc(state: DocState) -> DocState:
    """
    Determines document type using LLM with enhanced prompting.
    Routes to: [invoice, id_card, other]
    """
    # Initialize LLM manager with provider from state
    llm_manager = UnifiedLLMManager(provider=state.get("llm_provider"))
    
    print(f"--- 🔍 Agent: Classifier ({llm_manager.provider_name}) ---")

    # Access the model name dynamically from the manager
    active_model = getattr(llm_manager, 'model_name', 'unknown')

    system_prompt = """You are an advanced Medical Document Intelligence Agent. Your goal is to accurately classify documents.

### 1. CLASSIFICATION TASK
Analyze the document structure to determine its type EXACTLY as one of the following:

- **PRESCRIPTION**: Contains "Rx" symbol, doctor details (Name, License), and medication list.
- **LAB_REPORT**: Contains "Test Results", reference ranges, and lab accreditation.
- **UNKNOWN**: If neither pattern matches.

CLASSIFICATION RULES:
1. Look for key indicators:
   - Prescription: "Rx" symbol (☤), "Doctor Name", "License Number", "Patient Name", "Medication List", "Dosage", "Sig"
   - Lab Report: "Test Results", "Reference Range", "Lab Name", "Collection Date", "Report Date", "Analyte", "Specimen"
2. If uncertain or ambiguous, default to "UNKNOWN".

OUTPUT FORMAT: Return ONLY the category name in uppercase (PRESCRIPTION/LAB_REPORT/UNKNOWN).
NO explanations, NO markdown, NO additional text."""

    # Send a snippet to minimize token usage
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=f"Classify this document text:\n\n{state['raw_text'][:2000]}")
    ]

    response = llm_manager.invoke_with_fallback(messages)
    doc_type = response.content.strip().upper()
    
    # Validate output
    if doc_type not in ['PRESCRIPTION', 'LAB_REPORT', 'UNKNOWN']:
        print(f"⚠️ Invalid classification '{doc_type}', defaulting to 'UNKNOWN'")
        doc_type = 'UNKNOWN'

    # Update State
    state["doc_type"] = doc_type.lower() # Keep internal logic lowercased but follow guide names
    state["confidence_score"] = 1.0 # Initial classification confidence

    # Log for Responsible AI reporting
    state["trace_log"].append({
        "agent": "classifier",
        "output": doc_type,
        "model": active_model,
        "provider": llm_manager.provider_name
    })

    return state
