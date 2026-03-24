# Recent Changes: SQLite, Supervisor, HITL, Knowledge Lookup, and Repair Agent

Date: 2026-03-22

This document summarizes the recent implementation changes in the pipeline and explains the key code paths.

## 1) SQLite Changes

### What changed
- Switched graph checkpoint persistence from in-memory behavior to SQLite-backed persistence for HITL continuity.
- Added API-level SQLite tables for:
  - review queue state
  - trace event persistence
  - human decision audit logs
- Added timeout worker behavior that reads pending reviews from SQLite and auto-escalates or auto-approves based on config.

### Why it matters
- Pending human reviews survive service restarts.
- Auditability is stronger because trace events and human decisions are persisted.
- Review operations become queue-driven and operationally manageable.

### Code snippets

```python
# src/core/graph.py
from langgraph.checkpoint.sqlite import SqliteSaver

settings = get_settings()
reviews_db_path = Path(settings.processing.reviews_db_path)
reviews_db_path.parent.mkdir(parents=True, exist_ok=True)
_checkpointer_ctx = SqliteSaver.from_conn_string(str(reviews_db_path))
checkpointer = _checkpointer_ctx.__enter__()

app_with_review = workflow.compile(
    checkpointer=checkpointer,
    interrupt_after=["human_review"],
    interrupt_before=interrupt_before,
)
```

```python
# src/api/main.py
def _connect_db() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS review_queue (
            thread_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            doc_type TEXT,
            file_path TEXT,
            confidence_score REAL,
            review_reason TEXT,
            review_deadline TEXT,
            paused_since TEXT,
            escalated INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_trace_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id TEXT NOT NULL,
            correlation_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            agent TEXT NOT NULL,
            action TEXT NOT NULL,
            status TEXT NOT NULL,
            input_hash TEXT NOT NULL,
            output_hash TEXT NOT NULL,
            model TEXT,
            fallback_used INTEGER NOT NULL DEFAULT 0,
            duration_ms REAL,
            reviewer_id TEXT,
            reviewer_notes TEXT,
            metadata_json TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS human_decisions_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id TEXT NOT NULL,
            correlation_id TEXT,
            timestamp TEXT NOT NULL,
            action TEXT NOT NULL,
            reviewer_id TEXT,
            reviewer_notes TEXT,
            decision_rationale TEXT,
            metadata_json TEXT,
            UNIQUE(thread_id, action, timestamp, reviewer_id)
        )
    """)
    conn.commit()
    return conn
```

```python
# src/api/main.py
async def _timeout_worker() -> None:
    settings = get_settings().processing
    interval = int(settings.review_poll_interval_seconds)

    while True:
        ...
        rows = conn.execute(
            """
            SELECT thread_id, review_deadline
            FROM review_queue
            WHERE status = 'pending' AND review_deadline IS NOT NULL
            """
        ).fetchall()

        for row in rows:
            if deadline and deadline < now_iso:
                if settings.timeout_action == "auto_approve":
                    _apply_decision(... decision="approve" ...)
                else:
                    # Escalate and persist escalation trace + audit
                    ...

        await asyncio.sleep(interval)
```

## 2) Supervisor Changes

### What changed
- Introduced deterministic supervisor decision logic at multiple stages:
  - pre-supervisor initialization
  - post-classifier routing
  - post-extractor routing
  - post-validator routing
- Supervisor now controls canonical routing decisions (`repair`, `human_review`, `redactor`, `abort`).
- Added more review triggers into supervisor logic, including knowledge conflicts and fallback usage.

### Why it matters
- Routing is explicit and testable.
- Human review is triggered earlier for risky states, not only after repair.
- Abort/review behavior is consistent across failure modes.

### Code snippets

```python
# src/core/agents/supervisor.py
def post_validator_supervisor(state: DocState) -> DocState:
    if _has_unrecoverable_error(state):
        _mark_abort(state, "unrecoverable error after validation", "post_validator")
    elif _has_pipeline_errors(state):
        _mark_review(state, "pipeline error", "post_validator")
    elif bool(state.get("schema_validation_failed")):
        _mark_review(state, "schema validation failed", "post_validator")
    elif bool(state.get("extraction_empty")):
        _mark_review(state, "extraction appears empty", "post_validator")
    elif bool(state.get("llm_fallback_used")):
        _mark_review(state, "llm fallback model was used", "post_validator")
    elif bool(state.get("knowledge_conflicts")):
        _mark_review(state, "knowledge conflicts detected", "post_validator")
    elif _has_high_or_critical_flags(state):
        _mark_review(state, "critical validation flags", "post_validator")
    elif _repair_limit_exceeded(state):
        _mark_review(state, "repair limit exceeded", "post_validator")
    elif _has_repairable_flags_with_attempts_left(state):
        _set_decision(state, "repair", "repairable flags present", "post_validator")
    else:
        _set_decision(state, "redactor", "no repair needed", "post_validator")
    return state
```

```python
# src/core/graph.py
workflow.add_conditional_edges("post_validator_supervisor", supervisor_router, {
    "repair": "repair",
    "human_review": "human_review",
    "redactor": "redactor",
    "abort": "abort",
})
```

## 3) HITL (Human-in-the-Loop) Changes

### What changed
- HITL interruption is centered around `human_review` and uses SQLite checkpointing.
- Added API endpoints for review operations:
  - `POST /process/with-review`
  - `GET /review/pending`
  - `POST /review/{thread_id}/decision`
  - backward-compatible `POST /repair/approve`
- Added rich decision handling:
  - `approve`, `reject`, `override`, `re_extract`, `escalate`

### Why it matters
- Review queue can be managed operationally.
- Human actions become first-class state transitions.
- Manual override and re-extract paths are preserved in graph execution.

### Code snippets

```python
# src/core/graph.py
app_with_review = workflow.compile(
    checkpointer=checkpointer,
    interrupt_after=["human_review"],
    interrupt_before=interrupt_before,
)
```

```python
# src/core/graph_nodes/review_gate.py
def human_review_router(state: DocState) -> str:
    decision = str(state.get("human_decision") or "approve").lower()
    if decision == "re_extract":
        return "extractor"
    if decision == "override":
        return "validator"
    if decision == "reject":
        return "redactor"
    return "repair"
```

```python
# src/api/main.py
@api.get("/review/pending", response_model=List[PendingReviewItem])
async def get_pending_reviews() -> List[PendingReviewItem]:
    rows = conn.execute(
        """
        SELECT thread_id, doc_type, file_path, confidence_score, review_reason, paused_since
        FROM review_queue
        WHERE status = 'pending'
        ORDER BY paused_since ASC
        """
    ).fetchall()
    ...
```

```python
# src/api/main.py
@api.post("/review/{thread_id}/decision", response_model=ContinueResponse)
async def submit_review_decision(thread_id: str, request: DecisionRequest):
    return _apply_decision(thread_id=thread_id, request=request)
```

## 4) Knowledge Base Lookup Changes

### What changed
- Added feature-flagged knowledge lookup between validator and final supervisor decision.
- Added curated knowledge store loader for:
  - `data/knowledge/drugs.json`
  - `data/knowledge/lab_tests.json`
  - `data/knowledge/drug_aliases.csv`
- Added conflict generation (`KNOWLEDGE_MISMATCH`) with recommendations.

### Why it matters
- Extracted values are checked against curated references.
- Mismatches become structured validation signals and can trigger human review.
- Controlled rollout via environment flag.

### Code snippets

```python
# config/settings.py
enable_knowledge_lookup: bool = Field(
    default=os.getenv("ENABLE_KNOWLEDGE_LOOKUP", "false").lower() == "true",
    description="Enable exact-match knowledge validation between validator and supervisor"
)
knowledge_dir: Path = Field(
    default=PROJECT_ROOT / "data" / "knowledge",
    description="Curated knowledge base directory (JSON/CSV)"
)
```

```python
# src/core/graph.py
def _knowledge_node(state: DocState) -> DocState:
    if not get_settings().processing.enable_knowledge_lookup:
        state.setdefault("knowledge_hits", [])
        state.setdefault("knowledge_conflicts", [])
        state.setdefault("knowledge_recommendations", [])
        state.setdefault("trace_log", []).append(
            {"agent": "knowledge_lookup", "status": "skipped", "reason": "feature_flag_disabled"}
        )
        return state
    return knowledge_lookup(state)

workflow.add_edge("validator", "knowledge_lookup")
workflow.add_edge("knowledge_lookup", "post_validator_supervisor")
```

```python
# src/core/agents/knowledge_agent.py
if doc_type == "prescription":
    ...
    ref = exact_lookup(name, "drug", store)
    if ref:
        allowed_units = [u.lower() for u in (ref.get("allowed_units") or [])]
        if allowed_units and dosage:
            unit_ok = any(u in dosage for u in allowed_units)
            if not unit_ok:
                conflicts.append({
                    "code": "KNOWLEDGE_MISMATCH",
                    "severity": "HIGH",
                    "field": f"medications[{idx}].dosage",
                    ...
                })
```

```python
# src/core/knowledge/knowledge_store.py
def exact_lookup(value: str, category: str, store: KnowledgeStore) -> dict | None:
    key = _normalize(value)
    if not key:
        return None
    if category == "drug":
        mapped = store.drug_aliases.get(key, key)
        return store.drugs.get(mapped)
    if category == "lab_test":
        return store.lab_tests.get(key)
    return None
```

## 5) Repair Agent Changes

### What changed
- Expanded repairable flag scope (not just dosage unit errors).
- Added per-flag attempt tracking and capped retries per flag.
- Added robust JSON extraction for LLM outputs.
- Added focused context-window prompting around flagged values.
- Added repair confidence handling and low-confidence human-review signaling.
- Added structured repair outcomes for metrics/reporting.

### Why it matters
- Repairs are safer and more targeted.
- Fewer brittle failures from malformed LLM output.
- Better observability of what was repaired and with what confidence.

### Code snippets

```python
# src/core/agents/repair.py
REPAIRABLE_FLAGS = {
    "NON_STANDARD_UNIT",
    "INVALID_DOSAGE_UNIT",
    "MISSING_REQUIRED_FIELD",
    "INVALID_DATE_FORMAT",
    "INCONSISTENT_DOSAGE",
    "AMBIGUOUS_VALUE",
}
MAX_ATTEMPTS_PER_FLAG = 3
LOW_CONFIDENCE_THRESHOLD = 0.6
```

```python
# src/core/agents/repair.py
def _extract_largest_json(text: str) -> dict | None:
    best_obj, best_len = None, 0
    for m in re.finditer(r'\{', text):
        try:
            obj, end = json.JSONDecoder().raw_decode(text, m.start())
            if isinstance(obj, dict) and (end - m.start()) > best_len:
                best_obj, best_len = obj, end - m.start()
        except json.JSONDecodeError:
            continue
    return best_obj
```

```python
# src/core/agents/repair.py
repair_flags = [
    flag for flag in validation_flags
    if flag.get("code") in REPAIRABLE_FLAGS
    and flag_attempts.get(flag.get("code"), 0) < MAX_ATTEMPTS_PER_FLAG
]
...
if confidence < LOW_CONFIDENCE_THRESHOLD:
    state["errors"].append(
        f"Repair confidence low ({confidence:.2f}) - flagged for human review"
    )
```

## State and Config Surface Added

The pipeline state and configuration were expanded to support all changes above.

```python
# src/core/state.py (representative)
knowledge_hits: Optional[List[dict]]
knowledge_conflicts: Optional[List[dict]]
knowledge_recommendations: Optional[List[dict]]
trace_correlation_id: Optional[str]
trace_events: Optional[List[dict]]
supervisor_decision: Optional[str]
abort_reason: Optional[str]
review_required: Optional[bool]
review_reason: List[str]
```

```python
# config/settings.py (representative)
review_timeout_hours: int
interrupt_before_repair: bool
timeout_action: str
review_poll_interval_seconds: int
reviews_db_path: Path
enable_knowledge_lookup: bool
knowledge_dir: Path
```

## End-to-End Flow (Current)

`initialize -> pre_supervisor -> classifier -> post_classifier_supervisor -> extractor -> post_extractor_supervisor -> validator -> knowledge_lookup -> post_validator_supervisor -> (repair | human_review | redactor | abort) -> reporter`

- HITL interruptions happen at `human_review` in `app_with_review`.
- Queue and audit records are persisted in SQLite.
- Supervisor remains the central deterministic router.
