import io
import time
import traceback
import json
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
from pypdf import PdfReader
from typing import Optional, List
from app.graph import app as langgraph_pipeline, app_with_review as langgraph_pipeline_with_review
from app.state import DocState
from functools import lru_cache

api = FastAPI(title="Agentic Document Processor")


class ProcessResponse(BaseModel):
    doc_type: Optional[str] = "unknown"
    validated_data: Optional[dict] = {}
    redacted_text: Optional[str] = ""
    latency_ms: float
    trace: List[dict]
    errors: List[str]
    validation_flags: Optional[List[dict]] = []


@api.post("/process", response_model=ProcessResponse)
async def process_document(
    file: UploadFile = File(...),
    llm_provider: str = "ollama"  # Default to ollama, can be: ollama, groq, bedrock
):
    start_time = time.time()

    try:
        # Validate provider
        valid_providers = ["ollama", "groq", "bedrock"]
        if llm_provider.lower() not in valid_providers:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid LLM provider '{llm_provider}'. Must be one of: {', '.join(valid_providers)}"
            )

        # 1. PDF Parsing
        content = await file.read()
        pdf_reader = PdfReader(io.BytesIO(content))
        raw_text = "\n".join([page.extract_text()
                             for page in pdf_reader.pages if page.extract_text()])

        if not raw_text or len(raw_text.strip()) < 10:
            raise HTTPException(
                status_code=400,
                detail="Could not extract sufficient text from document. Please ensure the file is a valid text-based PDF."
            )

        # 2. State Initialization
        initial_state = DocState(
            raw_text=raw_text,
            file_path=file.filename,
            doc_type=None,
            extracted_data={},
            validated_data={},
            redacted_text="",
            errors=[],
            trace_log=[],
            repair_attempts=0,
            repair_summary=None,
            llm_provider=llm_provider.lower(),  # Pass provider to agents
            llm_model_name=None,
            confidence_score=0.0,
            validation_flags=[]
        )

        # 3. Graph Invocation (with thread_id for checkpointer)
        thread_id = f"process_{int(time.time() * 1000)}"
        config = {"configurable": {"thread_id": thread_id}}
        final_state = langgraph_pipeline.invoke(initial_state, config)

        latency_ms = (time.time() - start_time) * 1000

        # 4. Return Final State
        return {
            "doc_type": final_state.get("doc_type"),
            "validated_data": final_state.get("validated_data"),
            "redacted_text": final_state.get("redacted_text"),
            "latency_ms": round(latency_ms, 2),
            "trace": final_state.get("trace_log"),
            "errors": final_state.get("errors"),
            "validation_flags": final_state.get("validation_flags", [])
        }

    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# ===== HUMAN-IN-THE-LOOP ENDPOINTS =====

class InterruptResponse(BaseModel):
    """Response when processing is interrupted for human review."""
    status: str  # "interrupted", "completed"
    thread_id: str
    interrupted_at: Optional[str] = None  # Node name where interrupted
    repair_summary: Optional[dict] = None
    current_state: Optional[dict] = None
    message: str


class ApprovalRequest(BaseModel):
    """Request to approve or reject a repair."""
    thread_id: str
    approved: bool
    modified_data: Optional[dict] = None  # If user wants to manually override


class ContinueResponse(BaseModel):
    """Response after continuing from interrupt."""
    status: str
    doc_type: Optional[str] = None
    validated_data: Optional[dict] = None
    redacted_text: Optional[str] = None
    latency_ms: float
    trace: List[dict]
    errors: List[str]
    validation_flags: List[dict]


@api.post("/process/with-review", response_model=InterruptResponse)
async def process_with_human_review(
    file: UploadFile = File(...),
    llm_provider: str = "groq"
):
    """
    Process document with human-in-the-loop for repair approval.

    Returns immediately when repair is triggered, allowing human to review.
    Use /repair/approve or /repair/reject to continue processing.
    """
    try:
        # Validate provider
        valid_providers = ["ollama", "groq", "bedrock"]
        if llm_provider.lower() not in valid_providers:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid LLM provider '{llm_provider}'. Must be one of: {', '.join(valid_providers)}"
            )

        # Parse PDF
        content = await file.read()
        pdf_reader = PdfReader(io.BytesIO(content))
        raw_text = "\n".join([page.extract_text()
                             for page in pdf_reader.pages if page.extract_text()])

        if not raw_text or len(raw_text.strip()) < 10:
            raise HTTPException(
                status_code=400,
                detail="Could not extract sufficient text from document."
            )

        # Generate unique thread ID
        thread_id = f"thread_{int(time.time() * 1000)}"

        # Initialize state
        initial_state = {
            "raw_text": raw_text,
            "file_path": file.filename,
            "doc_type": None,
            "extracted_data": {},
            "validated_data": {},
            "redacted_text": "",
            "errors": [],
            "trace_log": [],
            "repair_attempts": 0,
            "repair_summary": None,
            "llm_provider": llm_provider.lower(),
            "llm_model_name": None,
            "confidence_score": 0.0,
            "validation_flags": []
        }

        # Run graph with thread config (enables checkpointing)
        config = {"configurable": {"thread_id": thread_id}}
        final_state = langgraph_pipeline_with_review.invoke(
            initial_state, config)

        # Check if interrupted
        state_snapshot = langgraph_pipeline_with_review.get_state(config)

        if state_snapshot.next:  # If there are next nodes, we're interrupted
            return {
                "status": "interrupted",
                "thread_id": thread_id,
                "interrupted_at": "repair",
                "repair_summary": final_state.get("repair_summary"),
                "current_state": {
                    "doc_type": final_state.get("doc_type"),
                    "validation_flags": final_state.get("validation_flags", []),
                    "repair_attempts": final_state.get("repair_attempts", 0)
                },
                "message": "Repair completed. Please review the changes and approve or reject."
            }
        else:
            # Completed without interruption (no repair needed)
            return {
                "status": "completed",
                "thread_id": thread_id,
                "interrupted_at": None,
                "repair_summary": None,
                "current_state": {
                    "doc_type": final_state.get("doc_type"),
                    "validated_data": final_state.get("validated_data"),
                    "validation_flags": final_state.get("validation_flags", [])
                },
                "message": "Processing completed without requiring repairs."
            }

    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@api.get("/repair/status/{thread_id}", response_model=InterruptResponse)
async def get_repair_status(thread_id: str):
    """
    Get the current status and repair details for an interrupted thread.
    """
    try:
        config = {"configurable": {"thread_id": thread_id}}
        state_snapshot = langgraph_pipeline_with_review.get_state(config)

        if not state_snapshot:
            raise HTTPException(
                status_code=404, detail=f"Thread {thread_id} not found")

        state = state_snapshot.values

        return {
            "status": "interrupted" if state_snapshot.next else "completed",
            "thread_id": thread_id,
            "interrupted_at": state_snapshot.next[0] if state_snapshot.next else None,
            "repair_summary": state.get("repair_summary"),
            "current_state": {
                "doc_type": state.get("doc_type"),
                "validation_flags": state.get("validation_flags", []),
                "repair_attempts": state.get("repair_attempts", 0),
                "extracted_data": state.get("extracted_data")
            },
            "message": "Review pending" if state_snapshot.next else "Completed"
        }

    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@api.post("/repair/approve", response_model=ContinueResponse)
async def approve_repair(request: ApprovalRequest):
    """
    Approve the repair and continue processing.

    If approved=True: Continue with repaired data
    If approved=False: Revert to original data or use modified_data if provided
    """
    start_time = time.time()

    try:
        config = {"configurable": {"thread_id": request.thread_id}}
        state_snapshot = langgraph_pipeline_with_review.get_state(config)

        if not state_snapshot:
            raise HTTPException(
                status_code=404, detail=f"Thread {request.thread_id} not found")

        current_state = state_snapshot.values

        # Handle rejection
        if not request.approved:
            # Revert to original or use user's modified data
            repair_summary = current_state.get("repair_summary", {})

            if request.modified_data:
                # User provided manual correction
                current_state["extracted_data"] = request.modified_data
                current_state["trace_log"].append({
                    "agent": "human",
                    "action": "manual_correction",
                    "message": "Human provided manual data correction"
                })
            else:
                # Revert to original
                original_data = repair_summary.get("original_data", {})
                current_state["extracted_data"] = original_data
                current_state["trace_log"].append({
                    "agent": "human",
                    "action": "reject_repair",
                    "message": "Repair rejected, reverted to original data"
                })
        else:
            # Approved - just log it
            current_state["trace_log"].append({
                "agent": "human",
                "action": "approve_repair",
                "message": "Repair approved by human reviewer"
            })

        # Update state and continue
        langgraph_pipeline_with_review.update_state(config, current_state)

        # Continue execution (set to None to resume from interrupt)
        final_state = langgraph_pipeline_with_review.invoke(None, config)

        latency_ms = (time.time() - start_time) * 1000

        return {
            "status": "completed",
            "doc_type": final_state.get("doc_type"),
            "validated_data": final_state.get("validated_data"),
            "redacted_text": final_state.get("redacted_text"),
            "latency_ms": round(latency_ms, 2),
            "trace": final_state.get("trace_log", []),
            "errors": final_state.get("errors", []),
            "validation_flags": final_state.get("validation_flags", [])
        }

    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
