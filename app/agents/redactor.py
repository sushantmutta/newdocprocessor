import re
import json
from langchain_core.messages import HumanMessage, SystemMessage
from app.llm_client import UnifiedLLMManager
from app.state import DocState


def redact_pii(state: DocState) -> DocState:
    """
    Two-phase PII redaction with automated detection and verification:
    Phase 1: Detect all PII entities in document (returns structured list)
    Phase 2: Redact detected PII and calculate metrics
    """
    print("--- 🔒 Agent: Redactor ---")

    # Initialize LLM manager with provider from state
    llm_manager = UnifiedLLMManager(provider=state.get("llm_provider"))

    doc_type = (state.get("doc_type") or "document").lower().strip()
    raw_text = state["raw_text"]

    # ============================================================================
    # PHASE 1: PII DETECTION - Identify all PII entities in document
    # ============================================================================
    print("  Phase 1: Detecting PII entities...")

    detection_prompt = f"""You are a HIPAA Privacy Compliance Expert specializing in PII/PHI detection.

TASK: Analyze the {doc_type} and identify ALL personally identifiable information (PII) and protected health information (PHI) present in the text.

### PII/PHI CATEGORIES TO DETECT (HIPAA 18 Identifiers):
1. **NAMES**: Patient names, doctor/provider names, family members, employers
2. **ADDRESSES**: Street addresses, cities, counties, states, ZIP codes
3. **DATES**: Date of birth, admission dates, discharge dates (NOT general service dates)
4. **PHONE**: Telephone numbers, fax numbers
5. **EMAIL**: Email addresses
6. **SSN**: Social Security numbers
7. **MRN**: Medical record numbers, patient IDs, chart numbers
8. **HEALTH_PLAN_ID**: Insurance numbers, policy numbers, member IDs
9. **ACCOUNT_NUMBER**: Financial account numbers
10. **LICENSE_NUMBER**: Professional licenses, DEA numbers, NPI numbers
11. **VEHICLE_ID**: License plates, vehicle identification numbers
12. **DEVICE_ID**: Device serial numbers, implant identifiers
13. **URL**: Website URLs
14. **IP_ADDRESS**: IP addresses
15. **UNIQUE_ID**: Prescription numbers (Rx#), specimen IDs, barcode numbers
16. **SIGNATURE**: Signature markers, handwritten notations
17. **BIOMETRIC**: Fingerprint, voiceprint indicators
18. **PHOTO**: Photo/image identifiers

### OUTPUT FORMAT (JSON ONLY):
Return a JSON array of ALL PII entities found. Each entity must have:
- "type": PII category (NAME, ADDRESS, PHONE, etc.)
- "value": The actual PII text found in document
- "category": Subcategory (e.g., "patient_name", "doctor_name", "street_address")

Example:
[
  {{"type": "NAME", "value": "Dr. Sarah Johnson", "category": "doctor_name"}},
  {{"type": "NAME", "value": "John Smith", "category": "patient_name"}},
  {{"type": "PHONE", "value": "555-123-4567", "category": "contact"}},
  {{"type": "MRN", "value": "MRN12345678", "category": "medical_record"}},
  {{"type": "ADDRESS", "value": "123 Main St", "category": "street_address"}},
  {{"type": "SSN", "value": "123-45-6789", "category": "ssn"}}
]

### IMPORTANT RULES:
- Extract EXACT text as it appears in document (preserve formatting)
- Include partial matches (e.g., if address is split, include each part)
- DO NOT include medication names, diagnoses, or test results as PII
- DO NOT include general service dates (prescription date, lab report date) as PII
- Only include Date of Birth if explicitly labeled as "DOB" or "Date of Birth"
- Be thorough - missing PII is a HIPAA violation

DOCUMENT TEXT:
{raw_text}

OUTPUT (JSON array only, no other text):"""

    try:
        detection_messages = [
            SystemMessage(
                content="You are a JSON-outputting PII detection system. Return only valid JSON."),
            HumanMessage(content=detection_prompt)
        ]

        detection_response = llm_manager.invoke_with_fallback(
            detection_messages)
        detection_text = detection_response.content.strip()

        # Extract JSON from response (handle markdown code blocks)
        if "```json" in detection_text:
            detection_text = detection_text.split(
                "```json")[1].split("```")[0].strip()
        elif "```" in detection_text:
            detection_text = detection_text.split(
                "```")[1].split("```")[0].strip()

        # Parse detected PII entities
        detected_pii = json.loads(detection_text)

        if not isinstance(detected_pii, list):
            print(f"  ⚠️  Warning: Detection returned non-list format, wrapping in array")
            detected_pii = [detected_pii] if detected_pii else []

        print(f"  ✓ Detected {len(detected_pii)} PII entities")

    except json.JSONDecodeError as e:
        print(f"  ⚠️  Warning: JSON parse error in PII detection: {e}")
        print(f"  Raw response: {detection_text[:200]}...")
        detected_pii = []
    except Exception as e:
        print(f"  ⚠️  Warning: PII detection failed: {e}")
        detected_pii = []

    # Store detected PII in state for metrics calculation
    state["detected_pii"] = detected_pii

    # ============================================================================
    # PHASE 2: PII REDACTION - Apply redactions based on detected entities
    # ============================================================================
    print("  Phase 2: Redacting PII...")

    redacted_text = raw_text

    # Redact each detected PII entity
    redacted_count = 0
    for pii_entity in detected_pii:
        pii_type = pii_entity.get("type", "UNKNOWN").upper()
        pii_value = str(pii_entity.get("value", "")).strip()

        if not pii_value:
            continue

        # Replace PII value with redaction tag
        # Use case-insensitive replacement to catch variations
        pattern = re.escape(pii_value)
        redaction_tag = f"[{pii_type}_REDACTED]"

        # Count how many times this PII appears and redact all occurrences
        matches = len(re.findall(pattern, redacted_text, re.IGNORECASE))
        if matches > 0:
            redacted_text = re.sub(
                pattern, redaction_tag, redacted_text, flags=re.IGNORECASE)
            redacted_count += matches

    # Additional regex-based redaction (safety net for structured patterns)
    regex_patterns = {
        "EMAIL": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "SSN": r"\b\d{3}-\d{2}-\d{4}\b",
        "PHONE": r"\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}",
        "IP_ADDRESS": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    }

    for pii_type, pattern in regex_patterns.items():
        # Only apply regex if not already redacted by LLM detection
        matches = re.findall(pattern, redacted_text)
        for match in matches:
            # Check if this PII was already detected by LLM
            already_detected = any(
                pii.get("value") == match for pii in detected_pii
            )
            if not already_detected:
                # Add to detected_pii list
                detected_pii.append({
                    "type": pii_type,
                    "value": match,
                    "category": "regex_detected"
                })
                redacted_count += 1

        redacted_text = re.sub(
            pattern, f"[{pii_type}_REDACTED]", redacted_text)

    # Extract all redaction tags for reporting
    all_tags = re.findall(r"\[([A-Z_]+)_REDACTED\]", redacted_text)
    pii_types_found = sorted(list(set(all_tags)))

    print(
        f"  ✓ Redacted {redacted_count} PII instances across {len(pii_types_found)} types")

    # Update State
    state["redacted_text"] = redacted_text
    state["detected_pii"] = detected_pii
    state["trace_log"].append({
        "agent": "redactor",
        "pii_detected": len(detected_pii),
        "pii_types_scrubbed": pii_types_found,
        "redaction_count": redacted_count,
        "status": "completed",
        "doc_context": doc_type
    })

    return state
