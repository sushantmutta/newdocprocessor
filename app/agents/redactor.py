import re
from langchain_core.messages import HumanMessage, SystemMessage
from app.llm_client import UnifiedLLMManager
from app.state import DocState


def redact_pii(state: DocState) -> DocState:
    print("--- 🔒 Agent: Redactor ---")
    
    # Initialize LLM manager with provider from state
    llm_manager = UnifiedLLMManager(provider=state.get("llm_provider"))
    
    doc_type = (state.get("doc_type") or "document").lower().strip()
    text_to_redact = state["raw_text"]

    # 1. Regex Layer: High-Precision for Structured Data
    patterns = {
        "EMAIL": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "IBAN": r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b",
        "PHONE": r"\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}",
        "ID_NUMBER": r"\b[A-Z0-9]{6,12}\b",
        "DATE": r"\b\d{2}[./-]\d{2}[./-]\d{4}\b"
    }

    # 2. Enhanced LLM Layer: GDPR-Compliant PII Detection
    system_prompt = f"""You are a GDPR/Privacy Compliance Expert specializing in PII redaction.

TASK: Identify and redact ALL personally identifiable information (PII) from the {doc_type}.

DOCUMENT CONTEXT: {doc_type}
SENSITIVITY LEVEL: High (assume all PII must be protected)

PII CATEGORIES TO REDACT:

1. PERSONAL NAMES:
   - Full names, first names, last names
   - Nicknames, aliases, maiden names
   - Replace with: [NAME_REDACTED]

2. CONTACT INFORMATION:
   - Physical addresses (street, city, postal code, country)
   - Email addresses (already handled by regex, but double-check)
   - Phone numbers (already handled by regex, but double-check)
   - Replace addresses with: [ADDRESS_REDACTED]

3. IDENTIFIERS:
   - ID numbers, employee IDs, customer IDs
   - Social security numbers, passport numbers
   - Account numbers, reference numbers
   - Replace with: [ID_NUMBER_REDACTED]

4. SENSITIVE ATTRIBUTES:
   - Dates of birth (if not already redacted)
   - Signatures, signature blocks
   - Replace with: [SIGNATURE_REDACTED] or [DOB_REDACTED]

REDACTION RULES:
1. Be CONSERVATIVE: When in doubt, redact
2. Preserve document structure and readability
3. Keep non-PII information intact:
   - Invoice numbers, dates (non-birth dates)
   - Amounts, prices, quantities
   - Product names, categories
4. Do NOT redact:
   - Company names (unless it's a sole proprietorship with person's name)
   - Generic job titles (e.g., "Manager", "Director")
   - Document types, headers, labels

QUALITY CHECKS:
- Ensure NO personal names remain visible
- Verify addresses are fully masked (not partial)
- Check for partial redactions (e.g., "John [NAME_REDACTED]" should be "[NAME_REDACTED]")
- Maintain document flow and context

OUTPUT: Return the COMPLETE original text with PII replaced by redaction tags.
Do NOT summarize, do NOT omit any content, ONLY replace PII with tags.
Preserve all formatting, line breaks, and structure."""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=text_to_redact)
    ]

    # 3. Invoke LLM for contextual PII detection
    response = llm_manager.invoke_with_fallback(messages)
    redacted_text = response.content

    # 4. Final Regex Scrub (safety net)
    pii_types_found = []
    for label, pattern in patterns.items():
        if re.search(pattern, redacted_text):
            pii_types_found.append(label)
            redacted_text = re.sub(
                pattern, f"[{label}_REDACTED]", redacted_text)

    # 5. Update State
    state["redacted_text"] = redacted_text
    state["trace_log"].append({
        "agent": "redactor",
        "pii_types_scrubbed": pii_types_found + ["NAMES", "ADDRESSES"],
        "status": "completed",
        "doc_context": doc_type
    })

    return state
