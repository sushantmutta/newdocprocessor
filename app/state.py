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
