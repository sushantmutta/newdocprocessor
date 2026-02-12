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

    system_prompt = """You are an advanced Medical Document Intelligence Agent with 99% accuracy.

TASK: Classify the document into EXACTLY ONE category.

CATEGORIES:
- prescription: Medical prescriptions, medication orders
- lab_report: Laboratory test results, pathology reports, diagnostic reports
- other: Any document that doesn't fit the above categories

CLASSIFICATION RULES:
1. Look for key indicators:
   - Prescription: "Rx" symbol (☤), "Doctor Name", "License Number", "Patient Name", "Medication List", "Dosage", "Sig"
   - Lab Report: "Test Results", "Reference Range", "Lab Name", "Collection Date", "Report Date", "Analyte", "Specimen"
2. If multiple categories match, choose the PRIMARY purpose
3. If uncertain or ambiguous, default to "other"

OUTPUT FORMAT: Return ONLY the category name in lowercase (prescription/lab_report/other)
NO explanations, NO markdown, NO additional text.

EXAMPLES:
- Document with "Rx: Amoxicillin" and "Dr. Smith" → prescription
- Document with "Hemoglobin: 14.5 g/dL" and "Normal Range" → lab_report
- Document with "Invoice #12345" or "Payment Receipt" → other
- "Pharmacy Receipt for $15.00" → other
- "Hospital Discharge Summary" → other"""

    # Send a snippet to minimize token usage
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=f"Classify this document text:\n\n{state['raw_text'][:2000]}")
    ]

    response = llm_manager.invoke_with_fallback(messages)
    doc_type = response.content.strip().lower()
    
    # Validate output
    if doc_type not in ['prescription', 'lab_report', 'other']:
        print(f"⚠️ Invalid classification '{doc_type}', defaulting to 'other'")
        doc_type = 'other'

    # Update State
    state["doc_type"] = doc_type

    # Log for Responsible AI reporting
    state["trace_log"].append({
        "agent": "classifier",
        "output": doc_type,
        "model": active_model,
        "provider": llm_manager.provider_name
    })

    return state
