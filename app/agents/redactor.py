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
        "SSN": r"\b\d{3}-\d{2}-\d{4}\b",  # Added SSN
        "PHONE": r"\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}",
        "MRN": r"\bMRN\s*[:#-]?\s*[A-Z0-9]+\b",  # Medical Record Number
    }

    # 2. Enhanced LLM Layer: HIPAA/GDPR-Compliant PII Detection
    system_prompt = f"""You are a HIPAA/Privacy Compliance Expert specializing in Medical PII redaction.

TASK: Identify and redact ALL protected health information (PHI/PII) from the {doc_type}.

DOCUMENT CONTEXT: {doc_type}
SENSITIVITY LEVEL: High (Medical Records)

PII CATEGORIES TO REDACT:

1. PERSONAL NAMES:
   - Patient names, relative names, doctor names (in non-prescriber context)
   - Nicknames, aliases
   - Replace with: [NAME_REDACTED]

2. CONTACT INFORMATION:
   - Physical addresses (home, work)
   - Email addresses
   - Phone numbers
   - Replace with: [ADDRESS_REDACTED], [EMAIL_REDACTED], [PHONE_REDACTED]

3. IDENTIFIERS (CRITICAL):
   - SSN (Social Security Numbers) -> [SSN_REDACTED]
   - MRN (Medical Record Numbers) -> [MRN_REDACTED]
   - Patient IDs/Member IDs -> [PATIENT_ID_REDACTED]
   - Prescription Numbers (Rx#) -> [RX_NUM_REDACTED]
   - Lab Specimen IDs -> [SPECIMEN_ID_REDACTED]
   - Insurance Policy Numbers -> [INSURANCE_REDACTED]
   - Passport/Driver License -> [ID_REDACTED]
   - Account numbers -> [ACCOUNT_REDACTED]

4. DATES (HIPAA Rule):
   - All dates EXCEPT years (e.g., DOB, admission date, discharge date)
   - Replace with: [DATE_REDACTED]

5. BIOMETRICS & SENSITIVE ATTRIBUTES:
   - Signatures, signature blocks -> [SIGNATURE_REDACTED]
   - Dates of birth -> [DOB_REDACTED]
   - Fingerprints, voice recordings (references)

REDACTION RULES:
1. Be CONSERVATIVE: When in doubt, redact
2. Preserve document structure and readability
3. Maintain original formatting as much as possible

OUTPUT: Return the COMPLETE original text with PII replaced by redaction tags.
Do NOT summarize, do NOT omit any content, ONLY replace PII with tags."""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=text_to_redact)
    ]

    # 3. Invoke LLM for contextual PII detection
    response = llm_manager.invoke_with_fallback(messages)
    redacted_text = response.content

    # 4. Final Regex Scrub (safety net)
    for label, pattern in patterns.items():
        redacted_text = re.sub(
            pattern, f"[{label}_REDACTED]", redacted_text)

    # 5. Dynamic PII Detection for Trace (Scan for tags)
    # This ensures that even LLM-generated tags appear in the trace
    all_tags = re.findall(r"\[([A-Z_]+)_REDACTED\]", redacted_text)
    pii_types_found = sorted(list(set(all_tags)))

    # 6. Update State
    state["redacted_text"] = redacted_text
    state["trace_log"].append({
        "agent": "redactor",
        "pii_types_scrubbed": pii_types_found,
        "status": "completed",
        "doc_context": doc_type
    })

    return state
