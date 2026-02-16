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
    system_prompt = f"""You are an advanced Privacy Compliance Expert specializing in Medical PII Redaction.

TASK: Identify and redact ALL protected health information (PHI/PII) from the {doc_type}.

### MANDATORY REDACTION CATEGORIES:
1. PERSONAL IDENTIFIERS:
   - Patient names, relatives, nicknames.
   - Doctor/Provider names.
   - Addresses (Physical and Email).
   - Phone numbers.
   - Replace with: [NAME_REDACTED], [ADDRESS_REDACTED], [EMAIL_REDACTED], [PHONE_REDACTED]
2. UNIQUE IDENTIFIERS:
   - SSN (Social Security Number).
   - MRN, Patient IDs, Insurance/Policy numbers.
   - Prescription Numbers (Rx#), Lab Specimen IDs.
   - License numbers, DEA numbers.
   - Replace with matching REDACTED tag (e.g., [SSN_REDACTED], [PATIENT_ID_REDACTED], [LICENSE_REDACTED]).
3. SENSITIVE ARTIFACTS:
   - Signatures, Handwritten initials, Stamp markers.
   - Replace with: [SIGNATURE_REDACTED]

### IMPORTANT: DO NOT REDACT THE FOLLOWING:
- **Dates**: Prescription dates, report dates, collection dates, service dates are NOT PHI and should remain visible.
- **Medical Data**: Medication names, dosages, test results, diagnoses, lab values.
- **Ages**: Patient age is allowed and should not be redacted.
- **Clinical Information**: Keep all medical findings, instructions, and clinical data intact.

REDACTION RULES:
- Only redact Date of Birth (DOB) if explicitly labeled as "Date of Birth" or "DOB".
- General dates on prescriptions and reports should NOT be redacted.
- Be CONSERVATIVE with identifiers but PRESERVE medical context and dates.
- Use fuzzy matching for handwritten simulation and noisy OCR text.

OUTPUT: Return the COMPLETE original text with only PII/PHI identifiers replaced by the specified redaction tags. Keep all dates, medical data, and clinical information intact."""

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
