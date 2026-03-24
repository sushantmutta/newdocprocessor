import re
import json
from langchain_core.messages import HumanMessage, SystemMessage
from src.core.clients.llm_client import UnifiedLLMManager
from src.core.state import DocState
from src.core.prompts import REDACTOR_SYSTEM_PROMPT, REDACTOR_DETECTION_PROMPT

# PII types that behave like names (title-stripping, variant matching)
_NAME_LIKE_TYPES = {"NAME", "SIGNATURE", "PRINTED_NAME", "PROVIDER_NAME"}


def _normalize_pii_value(value: str) -> str:
    """Collapse LLM hallucinations like duplicate titles ('Dr. Dr.') and extra whitespace."""
    # Collapse duplicated titles: "Dr. Dr." → "Dr."
    value = re.sub(
        r'\b(Dr|Mr|Mrs|Ms|Prof|Mx)\.?\s+\1\.?\s*',
        r'\1. ', value, flags=re.IGNORECASE
    )
    # Normalise internal whitespace
    value = re.sub(r'\s{2,}', ' ', value).strip()
    return value


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

    detection_prompt = REDACTOR_DETECTION_PROMPT.format(
        doc_type=doc_type,
        raw_text=raw_text
    )

    try:
        detection_messages = [
            SystemMessage(
                content=REDACTOR_SYSTEM_PROMPT),
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

        # Fix 3: Deduplicate on (type, normalised_value) to prevent the same
        # entity being processed twice and generating a false warning on the 2nd pass
        seen_keys: set = set()
        deduped: list = []
        for _entity in detected_pii:
            _key = (
                _entity.get("type", "").upper(),
                _normalize_pii_value(str(_entity.get("value", ""))).lower()
            )
            if _key not in seen_keys:
                seen_keys.add(_key)
                deduped.append(_entity)
        detected_pii = deduped

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
        pii_value = _normalize_pii_value(
            str(pii_entity.get("value", "")).strip())

        if not pii_value:
            continue

        # Fix 1: Skip if value was already consumed by a prior iteration
        # (covers duplicate detections and names embedded inside larger entities)
        if not re.search(re.escape(pii_value), redacted_text, re.IGNORECASE):
            continue

        redaction_tag = f"[{pii_type}_REDACTED]"
        successfully_redacted = False

        # Strategy 1: Exact match (case-insensitive)
        pattern = re.escape(pii_value)
        matches = len(re.findall(pattern, redacted_text, re.IGNORECASE))

        if matches > 0:
            redacted_text = re.sub(
                pattern, redaction_tag, redacted_text, flags=re.IGNORECASE)
            redacted_count += matches
            successfully_redacted = True
        else:
            # Strategy 2: Flexible matching for special cases

            # For addresses: try without punctuation
            if pii_type == "ADDRESS":
                # Remove commas and try matching
                flexible_value = pii_value.replace(
                    ",", "").replace("  ", " ").strip()
                # Also try matching the address with flexible whitespace/punctuation
                flexible_pattern = re.escape(
                    flexible_value).replace(r"\ ", r"[\s,]+")
                matches = len(re.findall(flexible_pattern,
                              redacted_text, re.IGNORECASE))
                if matches > 0:
                    redacted_text = re.sub(
                        flexible_pattern, redaction_tag, redacted_text, flags=re.IGNORECASE)
                    redacted_count += matches
                    successfully_redacted = True

            # For names and name-like types (SIGNATURE, PRINTED_NAME, PROVIDER_NAME):
            # try matching with title variations and credential stripping
            if pii_type in _NAME_LIKE_TYPES and not successfully_redacted:
                name_variants = [
                    pii_value,
                    re.sub(r"^(Dr|Mr|Mrs|Ms|Prof|Mx)\.?\s+", "",
                           pii_value, flags=re.IGNORECASE).strip(),
                    re.sub(r",?\s+(MD|MBBS|MS|PhD|DO|DPM|FRCR|FRCS)$",
                           "", pii_value, flags=re.IGNORECASE).strip(),
                    re.sub(r"^(Dr|Mr|Mrs|Ms|Prof|Mx)\.?\s+", "Dr. ",
                           pii_value, flags=re.IGNORECASE).strip(),
                ]

                # Deduplicate while preserving order
                for variant in dict.fromkeys(v for v in name_variants if v):
                    variant_pattern = re.escape(variant)
                    matches = len(re.findall(variant_pattern,
                                  redacted_text, re.IGNORECASE))
                    if matches > 0:
                        redacted_text = re.sub(
                            variant_pattern, redaction_tag, redacted_text, flags=re.IGNORECASE)
                        redacted_count += matches
                        successfully_redacted = True
                        break

            # Strategy 3: Word-by-word matching for long values
            if not successfully_redacted and len(pii_value.split()) > 2:
                # Try matching with flexible word boundaries
                words = pii_value.split()
                flexible_pattern = r"\s+".join([re.escape(word)
                                               for word in words])
                matches = len(re.findall(flexible_pattern,
                              redacted_text, re.IGNORECASE))
                if matches > 0:
                    redacted_text = re.sub(
                        flexible_pattern, redaction_tag, redacted_text, flags=re.IGNORECASE)
                    redacted_count += matches
                    successfully_redacted = True

            # Strategy 4: Significant-token sequence matching
            # Handles extra credentials, missing middle names, and other minor LLM hallucinations
            if not successfully_redacted:
                tokens = [re.escape(w) for w in re.findall(
                    r"[A-Za-z]{3,}", pii_value)]
                if len(tokens) >= 2:
                    token_pattern = r"[\w.\-\s]*?".join(tokens)
                    token_matches = re.findall(
                        token_pattern, redacted_text, re.IGNORECASE)
                    if token_matches:
                        redacted_text = re.sub(
                            token_pattern, redaction_tag, redacted_text, flags=re.IGNORECASE)
                        redacted_count += len(token_matches)
                        successfully_redacted = True

        if not successfully_redacted:
            # Fix 2: Final presence check — value may have been consumed by a
            # broader token-pattern match or an earlier overlapping entity
            if re.search(re.escape(pii_value), redacted_text, re.IGNORECASE):
                # Still present in text and all strategies failed — genuine miss
                display_value = pii_value[:80] + \
                    ("..." if len(pii_value) > 80 else "")
                print(
                    f"  ⚠️  Failed to redact: {pii_type} = '{display_value}'")

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
