# Frontend Updates for Human-in-the-Loop Repair

## Summary of Changes

The Streamlit frontend has been enhanced to support the self-repair agent with human-in-the-loop workflow. Users can now review and approve/reject automatic unit corrections before final processing.

---

## New UI Components

### 1. **Sidebar: Human Review Toggle**

**Location:** Sidebar > Processing Options

**New Element:**
```
☐ 🧑‍⚕️ Human Review for Repairs
```

**Behavior:**
- When **unchecked** (default): Documents process normally using `/process` endpoint
- When **checked**: Documents use `/process/with-review` endpoint and pause for human approval when repairs are triggered

**Help Text:**
> "Pause for human approval when unit errors are auto-corrected"

**Info Message (when enabled):**
> "💡 Processing will pause after repairs for your review"

---

### 2. **Main Area: Repair Review Interface**

When processing is interrupted for repair review, the following UI appears:

#### A. Header Section
```
⏸️ Processing paused for human review

## 🔧 Repair Review Required
Thread ID: `thread_1770980352123`
```

#### B. Repair Summary
```
### 📋 Repair Summary

Issues Detected: 2

🟡 NON_STANDARD_UNIT (MEDIUM)
  Non-standard unit 'liters' detected in dosage: 500 liters daily.

🟠 INVALID_DOSAGE_UNIT (HIGH)
  CRITICAL: Invalid dosage unit 'kg' in 'Metformin: 2 kg daily'...
```

#### C. AI Reasoning
```
### 🤖 AI Repair Reasoning

ℹ️ The unit 'liters' is inappropriate for oral medication. Based on common aspirin 
   dosing patterns, this should be 'mg'. Similarly, 'kg' is dangerous for medication 
   dosing and has been corrected to 'g' based on typical metformin prescriptions.
```

#### D. Side-by-Side Data Comparison
```
### 📊 Data Comparison

┌─────────────────────────────────┬─────────────────────────────────┐
│  Original Data (Before Repair)  │  Repaired Data (AI Suggestion)  │
│              ❌                  │              ✅                  │
├─────────────────────────────────┼─────────────────────────────────┤
│ {                               │ {                               │
│   "medications": [              │   "medications": [              │
│     {                           │     {                           │
│       "name": "Aspirin",        │       "name": "Aspirin",        │
│       "dosage": "500 liters"    │       "dosage": "500 mg daily"  │
│     },                          │     },                          │
│     {                           │     {                           │
│       "name": "Metformin",      │       "name": "Metformin",      │
│       "dosage": "2 kg daily"    │       "dosage": "2 g daily"     │
│     }                           │     }                           │
│   ]                             │   ]                             │
│ }                               │ }                               │
└─────────────────────────────────┴─────────────────────────────────┘
```

#### E. Human Decision Buttons
```
### 🧑‍⚕️ Your Decision

┌──────────────────┬──────────────────┬──────────────────┐
│  ✅ Approve      │  ❌ Reject &     │  ✏️ Manual       │
│     Repair       │     Revert       │     Override     │
│  [   PRIMARY   ] │  [   BUTTON   ]  │  [   BUTTON   ]  │
└──────────────────┴──────────────────┴──────────────────┘
```

#### F. Manual Override Interface (when clicked)
```
#### Manual Data Override
Edit the JSON below to provide your own correction:

┌─────────────────────────────────────────────────────────┐
│ Custom Data (JSON)                                      │
│ {                                                       │
│   "medications": [                                      │
│     {                                                   │
│       "name": "Aspirin",                                │
│       "dosage": "325 mg once daily"  ← User can edit   │
│     }                                                   │
│   ]                                                     │
│ }                                                       │
│                                                         │
│ [Height: 300px, Scrollable]                            │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│              📤 Submit Override                         │
└─────────────────────────────────────────────────────────┘
```

---

## User Workflow

### Scenario 1: Approve AI Repair
```
1. User uploads prescription.pdf with "500 liters" dosage error
2. Processing starts automatically
3. System detects unit error and repairs to "500 mg daily"
4. UI shows repair review interface
5. User reviews original vs repaired data
6. User clicks "✅ Approve Repair"
7. Spinner: "Continuing processing..."
8. Success message: "✅ Repair approved! Processing completed."
9. Page refreshes to show final results
```

### Scenario 2: Reject Repair
```
1-4. [Same as Scenario 1]
5. User disagrees with AI correction
6. User clicks "❌ Reject & Revert"
7. Spinner: "Reverting to original data and continuing..."
8. Warning message: "⚠️ Repair rejected. Using original data."
9. Page refreshes to show final results (with original erroneous data)
```

### Scenario 3: Manual Override
```
1-4. [Same as Scenario 1]
5. User partially agrees but wants different correction
6. User clicks "✏️ Manual Override"
7. JSON editor appears with repaired data pre-populated
8. User edits JSON: "500 liters" → "325 mg once daily"
9. User clicks "📤 Submit Override"
10. System validates JSON
11. Success message: "✅ Manual override applied! Processing completed."
12. Page refreshes to show final results (with user's custom data)
```

---

## Technical Implementation

### API Endpoints Used

| Action | Endpoint | Method | Payload |
|--------|----------|--------|---------|
| Initial Process | `/process/with-review` | POST | `file`, `llm_provider` |
| Check Status | `/repair/status/{thread_id}` | GET | - |
| Approve | `/repair/approve` | POST | `{"thread_id": "...", "approved": true}` |
| Reject | `/repair/approve` | POST | `{"thread_id": "...", "approved": false}` |
| Override | `/repair/approve` | POST | `{"thread_id": "...", "approved": false, "modified_data": {...}}` |

### State Management

- **`st.session_state['repair_thread_id']`**: Stores thread ID for reference
- **`st.rerun()`**: Refreshes page after approval/rejection to show final results
- **`st.stop()`**: Pauses execution at repair review screen until user decides

### Error Handling

```python
# JSON validation for manual override
try:
    manual_data = json.loads(manual_data_str)
except json.JSONDecodeError as e:
    st.error(f"Invalid JSON: {str(e)}")

# API communication errors
except Exception as e:
    st.error(f"Error during approval: {str(e)}")
```

---

## Visual Mockup

```
┌──────────────────────────────────────────────────────────────────────┐
│  SIDEBAR                                                             │
├──────────────────────────────────────────────────────────────────────┤
│  ### Processing Options                                              │
│                                                                       │
│  ☑ Enable Real-Time Streaming                                       │
│  ☑ 🧑‍⚕️ Human Review for Repairs                                     │
│                                                                       │
│  💡 Processing will pause after repairs for your review              │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│  MAIN CONTENT (After Clicking "Process Document")                    │
├──────────────────────────────────────────────────────────────────────┤
│  ⏸️ Processing paused for human review                               │
│                                                                       │
│  ## 🔧 Repair Review Required                                        │
│  Thread ID: `thread_1770980352123`                                   │
│                                                                       │
│  ### 📋 Repair Summary                                               │
│  Issues Detected: 1                                                  │
│  🟡 NON_STANDARD_UNIT (MEDIUM)                                       │
│    Non-standard unit 'liters' detected in dosage: 500 liters daily.  │
│                                                                       │
│  ### 🤖 AI Repair Reasoning                                          │
│  ℹ️ The unit 'liters' is inappropriate for oral medication...        │
│                                                                       │
│  ### 📊 Data Comparison                                              │
│  ┌──────────────────────┬──────────────────────┐                    │
│  │  Original ❌         │  Repaired ✅          │                    │
│  ├──────────────────────┼──────────────────────┤                    │
│  │  "500 liters daily"  │  "500 mg daily"      │                    │
│  └──────────────────────┴──────────────────────┘                    │
│                                                                       │
│  ### 🧑‍⚕️ Your Decision                                              │
│  [ ✅ Approve ] [ ❌ Reject & Revert ] [ ✏️ Manual Override ]        │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Compatibility Notes

### Backward Compatibility
- ✅ Existing workflow unchanged when "Human Review" is **unchecked**
- ✅ All current features continue to work
- ✅ No breaking changes to existing code

### Feature Interactions
- **Streaming Mode + Human Review**: Currently, human review only works with non-streaming mode
  - Future enhancement: Could add interrupt support for streaming mode
- **Multiple Documents**: Each gets unique thread_id
- **Session Persistence**: Thread stored in `st.session_state`

---

## Testing the New UI

### Step 1: Create Test Document
Create a PDF with unit errors:
```
Prescription

Doctor: Dr. Smith
License: ABC123
Patient: John Doe

Medications:
- Aspirin: 500 liters daily
- Metformin: 2 kg twice daily
```

### Step 2: Enable Human Review
1. Start Streamlit: `streamlit run streamlit_app.py`
2. In sidebar, check **"🧑‍⚕️ Human Review for Repairs"**
3. Upload test PDF
4. Click "Process Document"

### Step 3: Review Repair
- Observe repair summary display
- Compare original vs repaired data
- Read AI reasoning

### Step 4: Make Decision
Choose one of three options:
- **Approve**: Accept AI correction
- **Reject**: Revert to original (with errors)
- **Override**: Provide custom correction

### Step 5: View Final Results
After approval, normal results page displays with:
- Validated data (with approved repairs)
- Validation flags
- Trace log showing human decision

---

## Future Enhancements

### Potential Improvements
1. **Streaming Mode Support**: Add real-time interrupt for streaming
2. **Diff Viewer**: Highlight exact changes between original and repaired
3. **Approval History**: Track all human decisions across sessions
4. **Batch Approval**: Apply decision to similar errors in multiple documents
5. **Confidence Display**: Show AI confidence in each repair
6. **Undo/Redo**: Allow users to change decision after approval
7. **Comments**: Let users add notes explaining their decision

### Accessibility
- Add keyboard shortcuts (Enter = Approve, Esc = Reject)
- Screen reader compatibility for JSON comparison
- High contrast mode for repair highlighting

---

## Security & Compliance

### HIPAA Considerations
- ✅ All repairs logged in audit trail (`trace_log`)
- ✅ Thread IDs track all human interactions
- ✅ Original and modified data preserved for forensics
- ✅ No data persistence in browser (only session state)

### Audit Trail Example
```json
{
  "trace": [
    {"agent": "repair", "action": "repair_applied", "flags_addressed": ["NON_STANDARD_UNIT"]},
    {"agent": "human", "action": "approve_repair", "message": "Repair approved by human reviewer"},
    {"agent": "validator", "action": "validated", "flags_count": 0}
  ]
}
```

---

## Troubleshooting

### Issue: "Processing failed after approval"
**Cause**: API server crashed or thread expired

**Solution**: Restart API server and retry processing

### Issue: "Invalid JSON" error on manual override
**Cause**: Syntax error in custom JSON

**Solution**: Use JSON validator, ensure proper quotes and commas

### Issue: Page doesn't refresh after approval
**Cause**: `st.rerun()` not executing

**Solution**: Check browser console for JavaScript errors

### Issue: Thread not found
**Cause**: Server restarted (MemorySaver is in-memory only)

**Solution**: Reprocess document from beginning

---

## Quick Reference

| UI Element | Purpose | Action |
|------------|---------|--------|
| Human Review Checkbox | Enable/disable repair review | Toggle on to pause for approval |
| Repair Summary | Show detected issues | Read to understand what was found |
| AI Reasoning | Explain corrections | Verify AI logic is sound |
| Data Comparison | Before/after view | Compare original vs repaired |
| Approve Button | Accept AI repair | Click to continue with repairs |
| Reject Button | Revert to original | Click to keep original data |
| Override Button | Custom correction | Edit JSON and submit |

---

**Key Benefits:**
- ✅ **Safety**: Human oversight prevents incorrect auto-corrections
- ✅ **Transparency**: Full visibility into AI decisions
- ✅ **Flexibility**: Approve, reject, or customize repairs
- ✅ **Usability**: Intuitive side-by-side comparison
- ✅ **Compliance**: Complete audit trail for regulatory requirements
