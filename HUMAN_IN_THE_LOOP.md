# Self-Repair Agent with Human-in-the-Loop

## Overview

The self-repair agent automatically detects and corrects **dosage unit standardization errors** in medical documents. When repairs are made, execution pauses for **human review and approval** before continuing processing.

## Architecture

### Flow Diagram
```
Classifier → Extractor → Validator
                            ↓
                    [Has unit errors?]
                      ↙         ↘
                  YES           NO
                   ↓             ↓
                Repair       Redactor
                   ↓
        [INTERRUPT - Human Review]
                   ↓
        [Approve/Reject/Modify]
                   ↓
            Re-validate → Redactor → Reporter
```

### Key Components

1. **Repair Agent** ([app/agents/repair.py](app/agents/repair.py))
   - Detects `NON_STANDARD_UNIT` and `INVALID_DOSAGE_UNIT` flags
   - Uses LLM to intelligently correct unit errors
   - Provides repair reasoning and summary for human review
   - Maximum 3 repair attempts to prevent loops

2. **Graph Interrupts** ([app/graph.py](app/graph.py))
   - Configured with `interrupt_after=["repair"]`
   - Uses `MemorySaver` checkpointer to persist state
   - Execution pauses after repair for human approval

3. **Human-in-the-Loop API** ([api.py](api.py))
   - Three new endpoints for interrupt workflow
   - Thread-based execution tracking
   - Approval/rejection with optional manual override

## API Endpoints

### 1. Process with Human Review

**Endpoint:** `POST /process/with-review`

Start document processing with human-in-the-loop enabled.

**Request:**
```bash
curl -X POST "http://localhost:8000/process/with-review?llm_provider=groq" \
  -F "file=@prescription.pdf"
```

**Response (if interrupted):**
```json
{
  "status": "interrupted",
  "thread_id": "thread_1770980352123",
  "interrupted_at": "repair",
  "repair_summary": {
    "flags_repaired": [
      {
        "code": "NON_STANDARD_UNIT",
        "message": "Non-standard unit 'liters' detected in dosage: 500 liters daily.",
        "severity": "MEDIUM"
      }
    ],
    "reasoning": "The unit 'liters' is inappropriate for oral medication. Based on common aspirin dosing patterns, this should be 'mg'.",
    "original_data": {
      "medications": [{"name": "Aspirin", "dosage": "500 liters daily"}]
    },
    "repaired_data": {
      "medications": [{"name": "Aspirin", "dosage": "500 mg daily"}]
    }
  },
  "current_state": {
    "doc_type": "prescription",
    "validation_flags": [...],
    "repair_attempts": 1
  },
  "message": "Repair completed. Please review the changes and approve or reject."
}
```

**Response (if no repair needed):**
```json
{
  "status": "completed",
  "thread_id": "thread_1770980352456",
  "interrupted_at": null,
  "repair_summary": null,
  "current_state": {
    "doc_type": "prescription",
    "validated_data": {...},
    "validation_flags": []
  },
  "message": "Processing completed without requiring repairs."
}
```

### 2. Check Repair Status

**Endpoint:** `GET /repair/status/{thread_id}`

Review repair details before approving/rejecting.

**Request:**
```bash
curl "http://localhost:8000/repair/status/thread_1770980352123"
```

**Response:**
```json
{
  "status": "interrupted",
  "thread_id": "thread_1770980352123",
  "interrupted_at": "repair",
  "repair_summary": {
    "flags_repaired": [...],
    "reasoning": "...",
    "original_data": {...},
    "repaired_data": {...}
  },
  "current_state": {
    "doc_type": "prescription",
    "validation_flags": [...],
    "repair_attempts": 1,
    "extracted_data": {...}
  },
  "message": "Review pending"
}
```

### 3. Approve or Reject Repair

**Endpoint:** `POST /repair/approve`

Continue processing after human review.

**Request (Approve):**
```bash
curl -X POST "http://localhost:8000/repair/approve" \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "thread_1770980352123",
    "approved": true
  }'
```

**Request (Reject - Revert):**
```bash
curl -X POST "http://localhost:8000/repair/approve" \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "thread_1770980352123",
    "approved": false
  }'
```

**Request (Reject - Manual Override):**
```bash
curl -X POST "http://localhost:8000/repair/approve" \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "thread_1770980352123",
    "approved": false,
    "modified_data": {
      "medications": [
        {"name": "Aspirin", "dosage": "500 mg twice daily"}
      ]
    }
  }'
```

**Response:**
```json
{
  "status": "completed",
  "doc_type": "prescription",
  "validated_data": {...},
  "redacted_text": "...",
  "latency_ms": 4523.45,
  "trace": [
    {"agent": "classifier", "action": "classified", ...},
    {"agent": "extractor", "action": "extracted", ...},
    {"agent": "validator", "action": "validated", ...},
    {"agent": "repair", "action": "repair_applied", ...},
    {"agent": "human", "action": "approve_repair", ...},
    {"agent": "validator", "action": "validated", ...},
    {"agent": "redactor", "action": "redacted", ...},
    {"agent": "reporter", "action": "report_generated", ...}
  ],
  "errors": [],
  "validation_flags": [...]
}
```

## Repair Agent Prompt

The repair agent uses a sophisticated prompt to guide LLM corrections:

### Key Capabilities
- **Context-Aware:** Analyzes original document text to understand intent
- **Medical Knowledge:** Knows standard units (mg, ml, mcg, tablets, etc.)
- **Critical Error Detection:** Identifies dangerous units (liters, kg for oral meds)
- **Intelligent Conversion:** Converts units appropriately (0.002 liters → 2 ml)
- **Reasoning:** Provides clear explanation for each correction

### Standard Medical Units
- **Oral:** mg, g, mcg, tablet/capsule/pill
- **Liquid:** ml, drops, spray, mg/ml
- **Injectable:** mg, ml, units, iu
- **Topical:** mg/hr, mcg/hr, %, patch
- **Inhalation:** mcg, puff, mg

### Invalid Units (Auto-Corrected)
- **Volume:** liters, liter, l → ml
- **Mass:** kg, kgs → mg or g
- **Length:** cm, inches → N/A (inappropriate)

## Usage Examples

### Example 1: Approve Automatic Repair

```python
import requests

# 1. Upload document for processing
response = requests.post(
    "http://localhost:8000/process/with-review?llm_provider=groq",
    files={"file": open("prescription_with_error.pdf", "rb")}
)

data = response.json()

if data["status"] == "interrupted":
    thread_id = data["thread_id"]
    print(f"Repair Summary: {data['repair_summary']['reasoning']}")
    
    # 2. Review and approve
    approval = requests.post(
        "http://localhost:8000/repair/approve",
        json={"thread_id": thread_id, "approved": True}
    )
    
    final_result = approval.json()
    print(f"Final validated data: {final_result['validated_data']}")
```

### Example 2: Manual Override

```python
# 1. Process document
response = requests.post(
    "http://localhost:8000/process/with-review?llm_provider=groq",
    files={"file": open("prescription.pdf", "rb")}
)

data = response.json()

if data["status"] == "interrupted":
    # 2. Review repair
    repair_summary = data["repair_summary"]
    original = repair_summary["original_data"]
    repaired = repair_summary["repaired_data"]
    
    print(f"Original: {original}")
    print(f"AI Repair: {repaired}")
    
    # 3. Disagree with AI - provide manual correction
    manual_correction = {
        "medications": [
            {"name": "Aspirin", "dosage": "325 mg once daily"}
        ]
    }
    
    approval = requests.post(
        "http://localhost:8000/repair/approve",
        json={
            "thread_id": data["thread_id"],
            "approved": False,
            "modified_data": manual_correction
        }
    )
```

### Example 3: Reject and Revert

```python
# Reject repair and use original (possibly erroneous) data
approval = requests.post(
    "http://localhost:8000/repair/approve",
    json={
        "thread_id": thread_id,
        "approved": False
        # No modified_data = revert to original
    }
)
```

## Re-validation After Repair

After human approval, the repaired data **automatically re-enters the validator**:

```
Repair (with corrections)
    ↓
Validator (re-check all validations)
    ↓
Redactor (continue normal flow)
```

This ensures:
- Corrected units are verified as valid
- No new validation flags after repair
- Data integrity maintained throughout

## Error Handling

### Maximum Repair Attempts
If the same data goes through repair → validate → repair more than **3 times**, the process aborts:

```json
{
  "errors": ["Maximum repair attempts (3) exceeded. Manual review required."],
  "trace_log": [
    {"agent": "repair", "action": "abort", "reason": "Max repair attempts exceeded"}
  ]
}
```

### Repair Failure
If LLM cannot parse or repair:

```json
{
  "errors": ["Repair failed: Could not extract JSON from LLM response"],
  "trace_log": [
    {"agent": "repair", "action": "error", "error": "..."}
  ]
}
```

## State Management

### Thread Persistence
- Each processing session gets unique `thread_id`
- State persisted in **MemorySaver** (in-memory checkpointer)
- Can retrieve state at any time with `/repair/status/{thread_id}`

### State Fields
- `repair_attempts`: Counter to prevent infinite loops
- `repair_summary`: Full details for human review
  - `flags_repaired`: List of validation flags addressed
  - `reasoning`: LLM explanation of corrections
  - `original_data`: Pre-repair extracted data
  - `repaired_data`: Post-repair extracted data

## Testing the Feature

### 1. Create Test Prescription with Unit Error

Create `test_unit_error.pdf` with content:
```
Doctor: Dr. Smith
License: ABC123
Patient: John Doe
Age: 45

Medications:
- Aspirin: 500 liters daily
- Metformin: 1000 mg twice daily
```

### 2. Process with Review
```bash
curl -X POST "http://localhost:8000/process/with-review?llm_provider=groq" \
  -F "file=@test_unit_error.pdf"
```

### 3. Expected Interrupt Response
```json
{
  "status": "interrupted",
  "thread_id": "thread_...",
  "repair_summary": {
    "reasoning": "The unit 'liters' is inappropriate for oral medication...",
    "repaired_data": {
      "medications": [
        {"name": "Aspirin", "dosage": "500 mg daily"},
        {"name": "Metformin", "dosage": "1000 mg twice daily"}
      ]
    }
  }
}
```

### 4. Approve Repair
```bash
curl -X POST "http://localhost:8000/repair/approve" \
  -H "Content-Type: application/json" \
  -d '{"thread_id": "thread_...", "approved": true}'
```

## Integration with Existing Workflow

The self-repair feature is **backward compatible**:

- **Without human-in-the-loop:** Use existing `/process` endpoint (no interrupts)
- **With human-in-the-loop:** Use new `/process/with-review` endpoint

Both workflows share the same:
- Classifier agent
- Extractor agent
- Validator agent
- Redactor agent
- Reporter agent

The repair agent only activates when validation flags indicate unit errors.

## Future Enhancements

Potential extensions to the repair system:

1. **Broader Repair Scope**
   - Fix missing dosage information
   - Correct invalid date formats
   - Standardize medication names

2. **Multiple Approval Levels**
   - Pharmacist review
   - Physician review
   - Admin override

3. **Persistent Checkpointing**
   - Replace MemorySaver with database checkpointer
   - Enable cross-session state retrieval
   - Long-term audit trails

4. **Confidence Scoring**
   - LLM certainty in repairs
   - Auto-approve high-confidence (>95%)
   - Escalate low-confidence (<70%) to human

5. **Batch Repair**
   - Process multiple documents
   - Single approval for similar errors
   - Bulk operations

## Troubleshooting

### Issue: Thread Not Found
**Error:** `Thread {thread_id} not found`

**Cause:** MemorySaver is in-memory only; server restart clears threads

**Solution:** Use persistent checkpointer (PostgreSQL, SQLite)

### Issue: Repair Loop Detected
**Error:** `Maximum repair attempts (3) exceeded`

**Cause:** Repair doesn't fix validation issue, keeps re-triggering

**Solution:** Review repair prompt or validation logic; may need manual intervention

### Issue: LLM Timeout
**Error:** `Repair failed: Connection timeout`

**Cause:** LLM provider unavailable or slow

**Solution:** Check provider status, increase timeout, or use fallback provider

## Security Considerations

1. **Thread ID Exposure:** Thread IDs are sequential timestamps - consider UUIDs
2. **State Access:** No authentication on `/repair/status` - add auth middleware
3. **Manual Override:** Validate user-provided `modified_data` schema
4. **Audit Logging:** Record all human approvals/rejections for compliance

## Compliance & Audit

Every interaction is logged in `trace_log`:

```json
[
  {"agent": "repair", "action": "repair_applied", "reasoning": "...", "attempt": 1},
  {"agent": "human", "action": "approve_repair", "message": "Repair approved..."},
  {"agent": "validator", "action": "validated", "flags_count": 0}
]
```

This provides full audit trail for regulatory compliance (HIPAA, FDA 21 CFR Part 11).

---

## Quick Reference

| Endpoint | Purpose | Returns |
|----------|---------|---------|
| `POST /process/with-review` | Start processing with interrupts | Thread ID + status |
| `GET /repair/status/{thread_id}` | Review repair details | Repair summary + state |
| `POST /repair/approve` | Approve/reject/override repair | Final processed document |

**Key Concept:** Interrupt → Review → Approve → Continue → Complete
