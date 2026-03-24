from __future__ import annotations

from pydantic import BaseModel
from typing import Optional


class TraceEvent(BaseModel):
    thread_id: str
    correlation_id: str
    timestamp: str
    agent: str
    action: str
    status: str
    input_hash: str
    output_hash: str
    model: Optional[str] = None
    fallback_used: bool = False
    duration_ms: Optional[float] = None
    reviewer_id: Optional[str] = None
    reviewer_notes: Optional[str] = None
    metadata_json: Optional[str] = None
