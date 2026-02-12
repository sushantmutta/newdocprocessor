from typing import TypedDict, List, Optional, Any


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
    llm_provider: Optional[str]  # Runtime LLM provider selection
    llm_model_name: Optional[str]  # Track which model was used
    confidence_score: float  # AI confidence in extraction (0.0-1.0)
