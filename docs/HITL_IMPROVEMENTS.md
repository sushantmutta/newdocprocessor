# Human-in-the-Loop (HITL) — Improvement Plan

## What the Current HITL Does

- Only triggers after the **repair agent** runs (`interrupt_after=["repair"]`)
- Review options: Approve / Reject (revert to original) / Manual override
- State stored in memory (`MemorySaver`) — lost on server restart
- Single pending review at a time per thread
- UI is a toggle that enables/disables review mode globally

---

## Improvement 1 — Widen the Trigger Conditions

**Current gap:** Review only happens when a repair fires. A document with low extraction confidence or failed schema validation bypasses review entirely.

**Add these trigger conditions to the graph router:**

| New Trigger | Threshold | Why |
|-------------|-----------|-----|
| `confidence_score < 0.70` | Configurable | Extraction uncertainty needs human eyes |
| Schema `ValidationError` (Pydantic fails) | Any | Structured data is corrupted |
| Validation flags with severity `CRITICAL` or `HIGH` | Any HIGH/CRITICAL flag | Clinical safety risk |
| `doc_type == "unknown"` after classification | Any | Can't proceed without correct type |
| `repair_attempts >= max` without resolution | `max_repair_attempts` | Agent gave up, human must intervene |

**Implementation:** Add a `review_gate` conditional node after the validator that checks all these conditions and either routes to a `human_review` interrupt or continues to the redactor. The existing `should_repair` logic folds into this gate.

---

## Improvement 2 — Persist Review State (SQLite, not MemorySaver)

**Current gap:** `MemorySaver` stores graph state in-process RAM. Any server restart wipes all pending reviews — a critical problem for an insurance company processing thousands of documents.

**Replace / supplement with `SqliteSaver`:**

```python
from langgraph.checkpoint.sqlite import SqliteSaver

checkpointer = SqliteSaver.from_conn_string("data/reviews.db")
app_with_review = workflow.compile(
    checkpointer=checkpointer,
    interrupt_after=["human_review"]
)
```

**Benefits:**
- Pending reviews survive server restarts
- Multiple reviewers can check the status of any `thread_id`
- Full audit history of all state transitions
- `GET /review/pending` endpoint can query the DB for all unresolved threads

---

## Improvement 3 — `GET /review/pending` Endpoint

**Current gap:** There is no way to list all documents waiting for review. An insurance company receiving thousands of documents daily needs a review queue.

**Add endpoint:**
```
GET /review/pending
```

Returns all `thread_id`s where `state_snapshot.next` is non-empty (paused at interrupt), with:
- `thread_id`
- `doc_type`
- `file_path`
- `review_reason` (why it was flagged)
- `confidence_score`
- `validation_flags` summary
- `paused_since` timestamp

This becomes the backend for a **review queue dashboard** in the UI.

---

## Improvement 4 — Granular Decision Options

**Current gap:** Only two options exist — Approve (continue with repaired data) or Reject (revert to original). No middle ground.

**Add three more decision paths:**

| Decision | Status | Action |
|----------|--------|--------|
| `approve` | ✅ Exists | Accept AI repair as-is |
| `reject` | ✅ Exists | Revert to original data |
| `override` | ✅ Partial | Human submits fully corrected JSON via `modified_data` |
| `re_extract` | ❌ New | Wipe `extracted_data`, go back to extractor with a hint prompt |
| `escalate` | ❌ New | Mark as requiring senior review, freeze thread, send notification |

The `re_extract` path is valuable: instead of manually fixing bad JSON, the reviewer types a correction hint (e.g. "the patient name is actually John Smith") and the extractor re-runs with that context injected into the prompt.

---

## Improvement 5 — Field-Level Review UI

**Current gap:** The UI shows the entire `repair_summary` as a JSON block and the reviewer approves/rejects the whole document. On a real insurance document, only one or two fields might be wrong.

**Improve the UI to show a diff table:**

| Field | Original Value | AI Repaired Value | Action |
|-------|---------------|-------------------|--------|
| `medications[0].dosage` | `7 liters` | `7 mg` | ✅ Accept / ❌ Reject / ✏️ Edit |
| `medications[0].frequency` | `twice/day` | `twice daily` | ✅ Accept / ❌ Reject / ✏️ Edit |

The reviewer can accept some changes and reject others — sending back a partial override. The API `modified_data` field already supports this; the UI needs to be wired to build a field-merged payload.

---

## Improvement 6 — Review Timeout & Escalation

**Current gap:** A paused thread waits indefinitely. If a reviewer is unavailable, the document is stuck forever.

**Add a timeout mechanism:**

```python
# New fields in DocState
review_deadline: Optional[str]   # ISO timestamp — when review expires
escalated: bool                  # Whether it moved to senior review
```

A background task (APScheduler or a simple loop in `run.py`) checks for threads paused longer than the configured timeout (e.g. 4 hours) and either:
- Auto-approves with a log entry: `"Auto-approved after timeout: no reviewer responded"`
- Escalates to a senior reviewer queue
- Sends a notification (email / webhook)

---

## Improvement 7 — Reviewer Identity & Audit Trail

**Current gap:** Approval/rejection is anonymous. The trace log only records `"agent": "human"`. For an insurance company, this is a compliance failure — regulators require knowing *who* approved what decision.

**Add to `ApprovalRequest`:**
```python
reviewer_id: str       # Employee ID or email
reviewer_notes: str    # Optional comment explaining the decision
```

**Log to `responsible_ai_log`:**
```json
{
  "agent": "human",
  "reviewer_id": "ssmutta@company.com",
  "action": "approve_repair",
  "decision_rationale": "Dosage correction is clinically correct",
  "timestamp": "2026-03-12T14:32:10Z",
  "thread_id": "thread_1741784123456"
}
```

This also enables per-reviewer accuracy reporting: which reviewers catch AI errors vs. rubber-stamp everything.

---

## Improvement 8 — Confidence Score Display & Threshold UI Control

**Current gap:** The confidence score exists in state but is not displayed prominently at review time. The HITL trigger threshold is hardcoded.

**UI improvements:**
- Show a confidence meter (0–100%) prominently in the review dialog
- Show which fields contributed to low confidence (empty/uncertain extractor fields)
- Let admins adjust the HITL trigger threshold via a settings panel in the sidebar (`confidence_threshold` slider: 0.50–0.95)

---

## Summary by Priority

| Priority | Improvement | Effort |
|----------|-------------|--------|
| High | Widen trigger conditions (confidence, validation fail, unknown doc) | Medium |
| High | SQLite persistence (survive restarts, enable review queue) | Small |
| High | `GET /review/pending` queue endpoint | Small |
| High | Reviewer identity + audit trail in approval request | Small |
| Medium | Field-level diff UI (accept/reject individual fields) | Medium |
| Medium | Granular decision options (`re_extract`, `escalate`) | Medium |
| Medium | Review timeout + auto-escalation background task | Medium |
| Low | Confidence threshold UI control for admins | Small |
