from typing import List, Optional, Any
from typing_extensions import TypedDict


class DocState(TypedDict):
    raw_text: str
    file_path: str
    doc_type: Optional[str]
    extracted_data: Optional[dict]
    validated_data: Optional[dict]
    validation_flags: List[dict]  # Critical validation alerts
    redacted_text: Optional[str]
    errors: List[str]
    trace_log: List[dict]
    repair_attempts: int
    # Per-flag attempt counters: {flag_code: attempt_count} (Tip 3)
    repair_flag_attempts: Optional[dict]
    # Per-flag resolution results for metrics (Tip 10)
    repair_outcomes: Optional[List[dict]]
    # Details of repair operations for human review
    repair_summary: Optional[dict]
    llm_provider: Optional[str]  # Runtime LLM provider selection
    llm_model_name: Optional[str]  # Track which model was used
    confidence_score: float  # AI confidence in extraction (0.0-1.0)
    # Timestamp when processing started (for latency tracking)
    start_time: Optional[float]
    # Ground truth PII for recall/precision calculation
    ground_truth_pii: Optional[List[dict]]
    # Auto-detected PII entities from document (for automated recall/precision)
    detected_pii: Optional[List[dict]]
    # Supervisor-managed HITL routing fields
    review_required: Optional[bool]
    review_reason: List[str]
    review_deadline: Optional[str]
    escalated: Optional[bool]
    reviewer_id: Optional[str]
    reviewer_notes: Optional[str]
    schema_validation_failed: Optional[bool]
    validation_error_message: Optional[str]
    extraction_empty: Optional[bool]
    llm_fallback_used: Optional[bool]
    paused_since: Optional[str]
    human_decision: Optional[str]
    modified_data: Optional[dict]
    hint_prompt: Optional[str]
    original_data: Optional[dict]
    responsible_ai_log: Optional[List[dict]]
    knowledge_hits: Optional[List[dict]]
    knowledge_conflicts: Optional[List[dict]]
    knowledge_recommendations: Optional[List[dict]]
    trace_correlation_id: Optional[str]
    trace_events: Optional[List[dict]]
    supervisor_decision: Optional[str]
    abort_reason: Optional[str]
