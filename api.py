import io
import time
import traceback
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
from pypdf import PdfReader
from typing import Optional, List
from app.graph import app as langgraph_pipeline
from app.state import DocState

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
            llm_provider=llm_provider.lower(),  # Pass provider to agents
            llm_model_name=None
        )

        # 3. Graph Invocation
        final_state = langgraph_pipeline.invoke(initial_state)

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
