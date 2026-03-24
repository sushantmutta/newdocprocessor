# Multi-Agent Document Intelligence — Implementation Plan

## What Already Exists (Don't Break)

| Component | Status | Notes |
|-----------|--------|-------|
| Classifier, Extractor, Validator, Repair, Redactor, Reporter agents | ✅ Working | Core pipeline intact |
| LangGraph `StateGraph` with conditional edges | ✅ Working | `graph.py` |
| `DocState` TypedDict | ✅ Working | Needs new fields |
| `UnifiedLLMManager` (Ollama/Groq/Bedrock) | ✅ Working | Reuse as-is |
| FastAPI `/process` and `/process/with-review` | ✅ Working | Extend, don't replace |
| Streamlit UI | ✅ Working | Add tabs |
| `MemorySaver` checkpointer for HITL | ✅ Partial | Only triggers on repair — needs to also trigger on low confidence + validation failure |
| FAISS in requirements.txt | ✅ Installed | Not yet used |

---

## Task 1 — Refactor: Code Quality Fixes

**1a. `should_repair` router is too narrow**
Currently only triggers on `NON_STANDARD_UNIT` / `INVALID_DOSAGE_UNIT`. Expand to also route to human review when:
- `confidence_score < 0.7` (configurable threshold)
- Validator emitted HIGH severity flags
- Schema `ValidationError` occurred

**1b. `reporter.py` saves to wrong directory**
`os.path.dirname(__file__)` chains resolve to `src/reports/` but the code expects `data/reports/`. Add a `REPORTS_DIR` setting from `config/settings.py` rather than computing it via `__file__` traversal.

**1c. `DocState` is missing fields needed by new features**
Add:
- `review_required: bool` — flag set by supervisor when human review is needed
- `review_reason: str` — why review was triggered (low confidence / validation fail / repair exceeded)
- `human_decision: Optional[str]` — "approve" / "reject" / "override"
- `human_override_data: Optional[dict]` — manually corrected data from reviewer
- `knowledge_hits: List[dict]` — results from knowledge lookup
- `supervisor_decision: Optional[str]` — routing decision log from supervisor
- `responsible_ai_log: List[dict]` — structured log entries for all agent actions

**1d. Replace hardcoded `repair_attempts >= 3` magic number**
Pull from `settings.processing.max_repair_attempts`.

---

## Task 2 — Supervisor Agent

### Purpose
A new LangGraph node that sits **before the classifier** and **after each agent** (or as a conditional router). It decides:
- Which agent to invoke next
- Whether to pause for human review
- Whether to skip agents based on context

### Where it lives
`src/core/agents/supervisor.py`

### What it does

```
pre_supervisor  →  classifier  →  post_classifier_supervisor
                                        ↓
                               extractor / redactor
                                        ↓
                           post_extractor_supervisor
                                        ↓
                        validator → should_repair router
                                        ↓
                           post_validator_supervisor
                                        ↓
              [HITL interrupt] OR [repair] OR [redactor]
```

**The supervisor is NOT a separate LLM call.** It is a pure Python routing function (like `should_repair` already is) that reads state and makes routing decisions. This keeps it fast and deterministic.

### Supervisor routing logic

| Condition | Decision |
|-----------|----------|
| `doc_type == "unknown"` after classification | Flag `review_required=True`, reason: "unclassifiable document" |
| `confidence_score < threshold` after extraction | Flag `review_required=True`, reason: "low confidence extraction" |
| Validator returned HIGH/CRITICAL flags | Flag `review_required=True`, reason: "critical validation flags" |
| `repair_attempts >= max` | Flag `review_required=True`, reason: "repair limit exceeded" |
| `errors` list non-empty | Flag `review_required=True`, reason: "pipeline error" |
| All clear | Continue to next node |

### Graph change
Replace the existing `should_repair` conditional with a richer `supervisor_router` that returns:
- `"repair"` — unit errors, repair attempts remaining
- `"human_review"` — HITL interrupt needed
- `"redactor"` — clean, continue
- `"abort"` — unrecoverable error

---

## Task 3 — HITL (Human-in-the-Loop) System

### Current state
HITL only exists for **repair approval**. The graph has `interrupt_after=["repair"]` in `app_with_review`.

### What needs to change

**3a. Expand interrupt points**
`app_with_review` should interrupt at a new `human_review` node, not just after `repair`.
The `human_review` node sets `review_required=True` in state and the graph pauses there.

**3b. New `human_review` agent node**
- Reads `review_reason` from state
- Packages the current `extracted_data`, `validation_flags`, `confidence_score`, and `errors` into `repair_summary` for the UI
- Sets `interrupt_after=["human_review"]` in the compiled graph

**3c. Three review decision paths**

| Human Decision | System Action |
|---------------|---------------|
| `approve` | Accept current `extracted_data` as-is, continue to redactor |
| `reject` | Clear `extracted_data`, re-route to extractor with higher-quality prompt |
| `override` | Accept `human_override_data` from request body, replace `extracted_data`, continue to validator |

**3d. New API endpoints needed**

| Endpoint | Purpose |
|----------|---------|
| `GET /review/pending` | List all paused thread_ids waiting for review |
| `POST /review/{thread_id}/approve` | Approve and continue |
| `POST /review/{thread_id}/reject` | Reject and re-extract |
| `POST /review/{thread_id}/override` | Submit corrected data and continue |

**3e. Trigger conditions (configurable in `settings.py`)**

```
processing.confidence_threshold = 0.7
processing.require_review_on_validation_fail = True
processing.require_review_on_critical_flags = True
processing.require_review_flag_severities = ["CRITICAL", "HIGH"]
```

---

## Task 4 — Knowledge Lookup (FAISS)

### Purpose
Validate extracted field values against a curated knowledge base. Examples:
- Drug name "Amoxicilin" → lookup → suggest "Amoxicillin" + standard dosage range
- Lab test "HbA1c" → lookup → reference range 4.0–5.6%, flags if outside
- ICD-10 diagnosis codes → lookup → validate code format and description

### Architecture

**4a. Knowledge base storage**
- Location: `data/knowledge/`
- Files: `drugs.json`, `lab_tests.json`, `icd10_codes.json`
- Seeded with medical reference data (open-source datasets)
- FAISS index built on first run, saved to `data/knowledge/faiss_index/`

**4b. New file: `src/core/knowledge/knowledge_store.py`**

Responsibilities:
- Load medical reference data from JSON files
- Build FAISS index over drug names, test names, ICD codes using `sentence-transformers` embeddings
- `lookup(query: str, category: str, top_k: int) -> List[dict]` — semantic search
- `exact_lookup(value: str, category: str) -> Optional[dict]` — dict lookup for known values
- Cache index after first build (pickle or `.faiss` file)

**4c. New file: `src/core/agents/knowledge_agent.py`**

A new LangGraph node `knowledge_lookup` inserted **between validator and repair**:

```
validator → knowledge_lookup → should_repair / supervisor_router
```

What it does:
- For **prescriptions**: look up each medication name (fuzzy match + FAISS similarity), validate dosage against reference range
- For **lab reports**: look up each test name, validate value against reference range from knowledge base (not just from the document's own reference range field)
- Appends `knowledge_hits` to state — a list of `{field, extracted_value, closest_match, reference_range, is_valid}`
- Adds `KNOWLEDGE_MISMATCH` validation flags for any field that doesn't match knowledge base
- Does NOT modify `extracted_data` — only adds flags

**4d. Embedding model**
Use `sentence-transformers/all-MiniLM-L6-v2` (runs locally, no API key, ~80MB).
Add `sentence-transformers` to `requirements.txt`.

**4e. Chroma as alternative**
If persistent storage is preferred over in-memory FAISS, swap the backend to ChromaDB with `chromadb` package. The `knowledge_store.py` interface stays the same (`lookup()` / `exact_lookup()`) — only the implementation changes. Recommend FAISS for local/offline, Chroma for persistent server mode.

---

## Task 5 — Responsible AI Logging & Tracing

### Current state
`trace_log` is a `List[dict]` in state — unstructured, written ad-hoc by each agent. It's good but lacks: timestamps, severity, agent version, input/output hash, latency per agent, decision rationale.

### What needs to change

**5a. Structured log entry schema**
Define an `AgentLogEntry` Pydantic model (used only at logging time, not stored in state):

```python
class AgentLogEntry(BaseModel):
    timestamp: str               # ISO 8601
    agent: str                   # "classifier", "extractor", etc.
    action: str                  # "classify", "extract", "validate_flag", "repair", "redact", "route"
    status: str                  # "success", "failed", "skipped", "interrupted"
    input_summary: str           # First 200 chars of relevant input
    output_summary: str          # First 200 chars of relevant output
    confidence: Optional[float]
    latency_ms: Optional[float]
    model_used: Optional[str]
    provider: Optional[str]
    decision: Optional[str]      # For routing decisions — what was chosen and why
    flags: List[str]             # Validation flags generated
    error: Optional[str]
```

**5b. Central logging utility: `src/core/logging/ai_logger.py`**

- `log_agent_action(state, entry: AgentLogEntry)` — appends to `state["responsible_ai_log"]`
- `log_routing_decision(state, from_node, to_node, reason)` — specialized logger for supervisor decisions
- `export_audit_log(state, path)` — saves full responsible AI log to JSON file
- Wraps around Python's standard `logging` module — also writes to rotating file at `logs/agents.log`

**5c. Each existing agent needs 2–3 line updates**
Replace ad-hoc `state["trace_log"].append({"agent": "...", ...})` calls with `log_agent_action(state, AgentLogEntry(...))`. The `trace_log` list can remain for backward compatibility (the reporter and UI still read it), but `responsible_ai_log` becomes the structured audit record.

**5d. New reporter output: `audit_report_{timestamp}.json`**
The reporter generates a second output file (alongside the existing `trace_{type}_{timestamp}.json`) containing only the `responsible_ai_log` entries, formatted as a human-readable audit trail.

**5e. LangSmith integration (already partly wired)**
The existing `setup_langsmith.py` and `.env` `LANGCHAIN_TRACING_V2` config already traces LangChain calls.
Add: tag each LangChain invocation with `{"agent": agent_name, "doc_type": doc_type}` metadata using `with_config(tags=[...], metadata={...})` on the LLM calls. This makes LangSmith traces filterable by agent.

**5f. SQLite audit log (optional persistence)**
Add a `data/audit.db` SQLite database (via Python's built-in `sqlite3`) with a single `agent_logs` table. The `ai_logger.py` writes to both the state list and SQLite. This satisfies the storage requirement for long-running insurance company use cases without adding a heavy dependency.

---

## Revised LangGraph Pipeline

```
[START]
    ↓
pre_supervisor                 ← NEW: validates input, sets start_time
    ↓
classifier
    ↓
post_classifier_supervisor     ← NEW: routes unknown docs to HITL
    ↓
extractor  OR  redactor
    ↓ (if extractor)
knowledge_lookup               ← NEW: FAISS drug/test/code validation
    ↓
validator
    ↓
post_validator_supervisor      ← NEW: checks confidence + severity flags
    ↓
[human_review]  ←──────────── INTERRUPT POINT (HITL)
    ↓           OR
repair          ←──────────── REPAIR LOOP (as before)
    ↓
redactor
    ↓
reporter                       ← EXTENDED: writes responsible_ai_log
    ↓
[END]
```

---

## New File Structure

```
src/
├── core/
│   ├── agents/
│   │   ├── supervisor.py          ← NEW
│   │   ├── knowledge_agent.py     ← NEW
│   │   ├── classifier.py          refactored (use ai_logger)
│   │   ├── extractor.py           refactored (use ai_logger)
│   │   ├── validator.py           refactored (use ai_logger)
│   │   ├── repair.py              refactored (use ai_logger)
│   │   ├── redactor.py            refactored (use ai_logger)
│   │   └── reporter.py            extended (write audit log)
│   ├── knowledge/
│   │   ├── __init__.py            ← NEW
│   │   ├── knowledge_store.py     ← NEW (FAISS + JSON)
│   │   └── seed_data/
│   │       ├── drugs.json         ← NEW (drug reference data)
│   │       ├── lab_tests.json     ← NEW (lab test reference ranges)
│   │       └── icd10_codes.json   ← NEW (diagnosis codes)
│   ├── logging/
│   │   ├── __init__.py            ← NEW
│   │   └── ai_logger.py           ← NEW
│   ├── state.py                   extended (new fields)
│   └── graph.py                   refactored (new nodes + edges)
├── api/
│   └── main.py                    extended (review endpoints)
└── ui/
    └── app.py                     extended (review tab + knowledge tab)
data/
├── knowledge/
│   └── faiss_index/               ← auto-generated on first run
└── audit.db                       ← SQLite audit log
logs/
└── agents.log                     ← rotating file log
```

---

## New `requirements.txt` Additions

```
sentence-transformers    # local embeddings for FAISS knowledge lookup
chromadb                 # optional alternative to FAISS
```

---

## Implementation Order

| Step | Task | Dependencies |
|------|------|-------------|
| 1 | Extend `DocState` with new fields | Nothing |
| 2 | Build `ai_logger.py` | `DocState` |
| 3 | Build `knowledge_store.py` + seed JSON files | Nothing |
| 4 | Build `knowledge_agent.py` | `knowledge_store.py` |
| 5 | Build `supervisor.py` | `DocState`, new state fields |
| 6 | Refactor `graph.py` — add supervisor + knowledge nodes | Steps 3–5 |
| 7 | Refactor existing agents to use `ai_logger` | Step 2 |
| 8 | Extend `reporter.py` — write audit log | Step 2 |
| 9 | Extend `main.py` — add review endpoints | Step 6 |
| 10 | Extend `app.py` — review tab + knowledge hits display | Step 9 |
| 11 | Update `settings.py` — add thresholds + new config | Nothing |
| 12 | Write PyTest tests for supervisor, knowledge, HITL | Steps 1–10 |
