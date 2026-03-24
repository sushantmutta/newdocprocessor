# API Endpoint Usage Guide

This guide explains how to use all available FastAPI endpoints in the project, with practical examples.

## 1. Quick Start

### 1.1 Start the API server

From project root:

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn src.api.main:api --host 127.0.0.1 --port 8000
```

API base URL:

```text
http://127.0.0.1:8000
```

Interactive docs:

```text
http://127.0.0.1:8000/docs
```

ReDoc view:

```text
http://127.0.0.1:8000/redoc
```

### 1.2 Supported inputs

The API accepts multipart file upload with the `file` field.

Supported file formats:

- `.pdf`
- `.txt`

### 1.3 Optional feature flags

To enable curated knowledge checks:

```powershell
$env:ENABLE_KNOWLEDGE_LOOKUP="true"
```

Then restart the API process.

## 1.4 Using FastAPI Swagger Docs (`/docs`)

Use the Swagger UI as the primary place to explore and test endpoints.

1. Open `http://127.0.0.1:8000/docs`.
2. Click an endpoint card to expand details.
3. Click `Try it out`.
4. Fill query/body/form fields.
5. Click `Execute`.
6. Inspect:
- Request URL
- Generated cURL command
- Response body and status code

For file upload endpoints (`/process`, `/process/with-review`):

1. Click `Try it out`.
2. Use the `file` picker to select `.pdf` or `.txt`.
3. Set `llm_provider` (`ollama`, `groq`, `bedrock`).
4. Click `Execute`.

For review decision endpoint (`/review/{thread_id}/decision`):

1. Replace `thread_id` with a real value from `/process/with-review`.
2. Choose a valid `decision` in JSON body.
3. Click `Execute` to continue or escalate pipeline state.

## 1.5 Using FastAPI ReDoc (`/redoc`)

Use ReDoc for clean reference-style reading of schemas and response models.

Best for:

- understanding model fields quickly
- sharing endpoint docs with non-developers
- browsing request/response schema in a structured format

## 2. Common Conventions

### 2.1 Query parameter

Most processing endpoints accept:

- `llm_provider`: `ollama`, `groq`, or `bedrock`

### 2.2 Main response fields

Processing responses typically include:

- `doc_type`
- `validated_data`
- `redacted_text`
- `latency_ms`
- `trace`
- `errors`
- `validation_flags`

## 3. Endpoint Reference

## 3.1 `POST /process`

Runs document processing without HITL interruption workflow.

### Request

- Content type: `multipart/form-data`
- Required file field: `file`
- Optional query: `llm_provider`

### cURL example

```bash
curl -X POST "http://127.0.0.1:8000/process?llm_provider=groq" \
  -F "file=@data/prescriptions/test_txt_prescription_happy_path.txt"
```

### PowerShell example

```powershell
$uri = "http://127.0.0.1:8000/process?llm_provider=groq"
$form = @{ file = Get-Item "data/prescriptions/test_txt_prescription_happy_path.txt" }
Invoke-RestMethod -Uri $uri -Method Post -Form $form
```

### Success response example

```json
{
  "doc_type": "prescription",
  "validated_data": {"doctor": {}, "patient": {}, "medications": []},
  "redacted_text": "...",
  "latency_ms": 1450.21,
  "trace": [{"agent": "classifier", "status": "success"}],
  "errors": [],
  "validation_flags": []
}
```

## 3.2 `POST /process/with-review`

Runs processing with supervisor + HITL review support.

### Behavior

Returns either:

- `status: "completed"` when no review pause is needed
- `status: "interrupted"` when paused for human decision

### cURL example

```bash
curl -X POST "http://127.0.0.1:8000/process/with-review?llm_provider=groq" \
  -F "file=@data/prescriptions/test_txt_prescription_conflict_review.txt"
```

### PowerShell example

```powershell
$uri = "http://127.0.0.1:8000/process/with-review?llm_provider=groq"
$form = @{ file = Get-Item "data/prescriptions/test_txt_prescription_conflict_review.txt" }
$response = Invoke-RestMethod -Uri $uri -Method Post -Form $form
$response
```

### Interrupted response example

```json
{
  "status": "interrupted",
  "thread_id": "thread_1773669999999",
  "interrupted_at": "human_review",
  "repair_summary": {"...": "..."},
  "current_state": {
    "doc_type": "prescription",
    "validation_flags": [{"code": "...", "severity": "HIGH"}],
    "review_required": true,
    "review_reason": ["..."],
    "supervisor_decision": "human_review",
    "confidence_score": 0.78
  },
  "message": "Review required. Submit decision via /review/{thread_id}/decision."
}
```

## 3.3 `GET /review/pending`

Returns threads currently paused and waiting for reviewer action.

### cURL example

```bash
curl "http://127.0.0.1:8000/review/pending"
```

### PowerShell example

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/review/pending" -Method Get
```

### Response example

```json
[
  {
    "thread_id": "thread_1773669999999",
    "doc_type": "prescription",
    "file_path": "test_txt_prescription_conflict_review.txt",
    "confidence_score": 0.78,
    "review_reason": ["validation risk", "knowledge conflicts detected"],
    "paused_since": "2026-03-16T10:20:30.000000+00:00"
  }
]
```

## 3.4 `GET /review/escalated`

Returns threads escalated for senior review.

### Example

```bash
curl "http://127.0.0.1:8000/review/escalated"
```

## 3.5 `POST /review/{thread_id}/decision`

Submits a human decision for an interrupted thread.

### Request body schema

```json
{
  "decision": "approve | reject | override | re_extract | escalate",
  "modified_data": {},
  "hint_prompt": "optional prompt for re-extract",
  "reviewer_id": "reviewer-123",
  "reviewer_notes": "optional notes"
}
```

### Decision meanings

- `approve`: accept current extracted data and continue
- `reject`: discard repaired/extracted changes and continue
- `override`: merge `modified_data` as human patch and continue
- `re_extract`: clear extraction and run extraction again with optional `hint_prompt`
- `escalate`: keep paused and mark escalated

### Approve example

```bash
curl -X POST "http://127.0.0.1:8000/review/thread_1773669999999/decision" \
  -H "Content-Type: application/json" \
  -d '{
    "decision": "approve",
    "reviewer_id": "dr_senior_01",
    "reviewer_notes": "Looks safe. Approved."
  }'
```

### Override example

```bash
curl -X POST "http://127.0.0.1:8000/review/thread_1773669999999/decision" \
  -H "Content-Type: application/json" \
  -d '{
    "decision": "override",
    "modified_data": {
      "medications": [
        {"name": "Metformin", "dosage": "500 mg", "frequency": "twice daily"}
      ]
    },
    "reviewer_id": "dr_senior_01",
    "reviewer_notes": "Corrected dose manually."
  }'
```

### Re-extract example

```bash
curl -X POST "http://127.0.0.1:8000/review/thread_1773669999999/decision" \
  -H "Content-Type: application/json" \
  -d '{
    "decision": "re_extract",
    "hint_prompt": "Focus on medication dosage and frequency lines only",
    "reviewer_id": "qa_reviewer",
    "reviewer_notes": "Initial extraction inconsistent"
  }'
```

## 3.6 `POST /repair/approve` (legacy compatibility)

Backward-compatible wrapper endpoint.

### Request

```json
{
  "thread_id": "thread_1773669999999",
  "approved": true,
  "modified_data": {}
}
```

### Notes

- If `approved=true`, maps to `approve`.
- If `approved=false` and `modified_data` provided, maps to `override`.
- If `approved=false` and no `modified_data`, maps to `reject`.

## 3.7 `GET /trace/{thread_id}`

Returns standardized trace events persisted for a thread.

### Example

```bash
curl "http://127.0.0.1:8000/trace/thread_1773669999999"
```

### Response example

```json
[
  {
    "thread_id": "thread_1773669999999",
    "correlation_id": "thread_1773669999999",
    "timestamp": "2026-03-16T10:20:31.100000+00:00",
    "agent": "validator",
    "action": "validate",
    "status": "success",
    "input_hash": "...",
    "output_hash": "...",
    "model": null,
    "fallback_used": false,
    "duration_ms": 33.2,
    "reviewer_id": null,
    "reviewer_notes": null,
    "metadata_json": "{}"
  }
]
```

## 3.8 `GET /audit/{thread_id}`

Returns human decision audit records for a thread.

### Example

```bash
curl "http://127.0.0.1:8000/audit/thread_1773669999999"
```

### Response example

```json
[
  {
    "thread_id": "thread_1773669999999",
    "correlation_id": "thread_1773669999999",
    "timestamp": "2026-03-16T10:25:00.000000+00:00",
    "action": "approve",
    "reviewer_id": "dr_senior_01",
    "reviewer_notes": "Looks safe. Approved.",
    "decision_rationale": "Looks safe. Approved.",
    "metadata_json": "{\"source\": \"responsible_ai_log\"}"
  }
]
```

## 4. End-to-End HITL Example Flow

1. Submit document to `/process/with-review`.
2. Read `thread_id` from response.
3. If status is `interrupted`, call `/review/pending` to list active queues.
4. Submit reviewer decision to `/review/{thread_id}/decision`.
5. Fetch `/trace/{thread_id}` to inspect full processing steps.
6. Fetch `/audit/{thread_id}` to inspect reviewer action history.

## 5. Error Handling Guide

Common API errors:

- `400 Invalid LLM provider`
- `400 Unsupported file format '.xyz'`
- `400 Could not extract sufficient text from document`
- `404 Thread not found` (review decision for unknown thread)
- `500 Internal server error`

Example error response:

```json
{
  "detail": "Unsupported file format '.docx'. Allowed formats: .pdf, .txt"
}
```

## 6. Useful Test Files

Try these existing fixtures:

- `data/prescriptions/test_txt_prescription_happy_path.txt`
- `data/prescriptions/test_txt_prescription_conflict_review.txt`
- `data/labreports/test_txt_lab_report_happy_path.txt`
- `data/labreports/test_txt_lab_report_critical_review.txt`
- `data/labreports/test_txt_too_short_invalid.txt`

## 7. Tips for Automation

- Persist `thread_id` in your client right after `/process/with-review`.
- Use polling on `/review/pending` for reviewer dashboard updates.
- Use `/trace/{thread_id}` for debugging latency and route decisions.
- Use `/audit/{thread_id}` for compliance and decision accountability.
