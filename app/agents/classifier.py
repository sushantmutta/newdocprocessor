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

    system_prompt = """You are an expert document classification system with 99% accuracy.

TASK: Classify the document into EXACTLY ONE category.

CATEGORIES:
- invoice: Bills, receipts, purchase orders, payment requests, invoices
- id_card: Identity cards, employee badges, membership cards, licenses, credentials
- other: Any document that doesn't fit the above categories

CLASSIFICATION RULES:
1. Look for key indicators:
   - Invoice: "Invoice #", "Total Amount", "Due Date", "Vendor", "Bill To", "Payment", "Price"
   - ID Card: "ID Number", "Date of Birth", "Expiry Date", "Photo", "Cardholder", "Employee ID"
2. If multiple categories match, choose the PRIMARY purpose
3. If uncertain or ambiguous, default to "other"
4. Focus on the MAIN content, ignore headers/footers

OUTPUT FORMAT: Return ONLY the category name in lowercase (invoice/id_card/other)
NO explanations, NO markdown, NO additional text.

EXAMPLES:
- Document with "Invoice #12345" and "Total: $500" → invoice
- Document with "Employee ID: EMP001" and "DOB: 1990-01-01" → id_card  
- Document with "Meeting Notes" or "Report" → other"""

    # Send a snippet to minimize token usage
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=f"Classify this document text:\n\n{state['raw_text'][:2000]}")
    ]

    response = llm_manager.invoke_with_fallback(messages)
    doc_type = response.content.strip().lower()
    
    # Validate output
    if doc_type not in ['invoice', 'id_card', 'other']:
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
