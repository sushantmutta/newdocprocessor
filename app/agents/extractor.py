import json
from langchain_core.messages import HumanMessage, SystemMessage
from app.llm_client import UnifiedLLMManager
from app.state import DocState

# Enhanced specialized prompts for different document types
PROMPTS = {
    "invoice": """You are a specialized invoice data extraction system.

TASK: Extract structured data from the invoice text with 100% accuracy.

REQUIRED FIELDS:
1. invoice_number (string): The unique invoice identifier
   - Look for: "Invoice #", "Invoice No", "Bill #", "Reference", "Inv No"
   - Format: Preserve exactly as written (e.g., "INV-2024-001")
   
2. vendor_name (string): The company/person issuing the invoice
   - Look for: "From:", "Vendor:", "Seller:", company name at top of document
   - Format: Full legal name, clean extra whitespace
   
3. total_amount (float): The final amount to be paid
   - Look for: "Total", "Amount Due", "Grand Total", "Balance", "Total Amount"
   - Format: Convert to standard float (e.g., "8.028,26" → 8028.26, "1,234.56" → 1234.56)
   - Handle: Remove €, $, £, USD, EUR symbols
   
4. date (string): Invoice issue date
   - Look for: "Date:", "Invoice Date:", "Issued:", "Date of Issue"
   - Format: YYYY-MM-DD (convert from any format)
   - Examples: "15.01.2024" → "2024-01-15", "Jan 15, 2024" → "2024-01-15"

EXTRACTION RULES:
- If a field is not found, use null (not empty string)
- For amounts: Remove currency symbols, convert European format (comma decimal) to standard (dot decimal)
- For dates: Always convert to ISO format (YYYY-MM-DD)
- Preserve case and spacing in text fields, but clean extra whitespace

OUTPUT FORMAT: Return ONLY a raw JSON object (no markdown, no ```json tags, no explanations)

EXAMPLE OUTPUT:
{
  "invoice_number": "INV-2024-001",
  "vendor_name": "Acme Corporation",
  "total_amount": 8028.26,
  "date": "2024-01-15"
}""",
    
    "id_card": """You are a specialized ID card data extraction system.

TASK: Extract personal information from the ID card with perfect accuracy.

REQUIRED FIELDS:
1. full_name (string): Complete name of the cardholder
   - Look for: "Name:", "Cardholder:", "Employee Name:", name near photo area
   - Format: "FirstName LastName" (clean extra spaces, preserve capitalization)
   
2. id_number (string): Unique identifier on the card
   - Look for: "ID:", "Employee ID:", "Card Number:", "Badge #", "ID No"
   - Format: Preserve exactly as written (alphanumeric, may include dashes/spaces)
   
3. date_of_birth (string): Cardholder's birth date
   - Look for: "DOB:", "Date of Birth:", "Born:", "Birth Date"
   - Format: YYYY-MM-DD (convert from any format)
   - Examples: "01/15/1990" → "1990-01-15", "15.01.1990" → "1990-01-15"
   
4. expiry_date (string): Card expiration date
   - Look for: "Expiry:", "Valid Until:", "Expires:", "Expiration Date"
   - Format: YYYY-MM-DD (convert from any format)

EXTRACTION RULES:
- Clean all extra whitespace from names and IDs
- Convert all dates to ISO format (YYYY-MM-DD)
- If a field is missing or not found, use null
- Preserve uppercase/lowercase in IDs exactly as shown on card
- For names: Keep proper capitalization (e.g., "John Doe" not "JOHN DOE")

OUTPUT FORMAT: Return ONLY a raw JSON object (no markdown, no explanations)

EXAMPLE OUTPUT:
{
  "full_name": "John Doe",
  "id_number": "EMP56725065",
  "date_of_birth": "1990-01-15",
  "expiry_date": "2025-12-31"
}"""
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
