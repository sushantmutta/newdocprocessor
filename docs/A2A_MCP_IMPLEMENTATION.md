# A2A + MCP Combined Implementation Plan

## Protocol Roles — How They Complement Each Other

| Protocol | Invented By | Purpose | Direction |
|----------|------------|---------|-----------|
| **MCP** (Model Context Protocol) | Anthropic | Agent ↔ Tools / Resources | LLM accesses external capabilities (tools, data) |
| **A2A** (Agent-to-Agent) | Google | Agent ↔ Agent | Agents delegate tasks to other agents |

They solve **different problems** and are **designed to be used together**:
- **MCP** = *how this agent uses tools* (classify, extract, validate, redact)
- **A2A** = *how external agents send work to this agent, and how this agent delegates to specialists*

---

## Combined Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│              External Orchestrator Agent (any vendor)           │
│                  e.g. Google ADK, LangGraph, AutoGen            │
└───────────────────────┬─────────────────────────────────────────┘
                        │  A2A Protocol (task delegation)
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│          Medical Document Agent  ◄── THIS PROJECT              │
│                                                                  │
│   A2A Server  ──►  Task Manager  ──►  LangGraph Pipeline        │
│      │                                      │                   │
│      │  A2A Client                          │ MCP Client        │
│      ▼                                      ▼                   │
│  Sub-Agents                           MCP Server (tools)        │
│  (OCR, Pharma,                        classify_document         │
│   Compliance, NLP)                    extract_data              │
│                                       validate_extraction        │
│                                       redact_pii                │
│                                       process_document           │
└─────────────────────────────────────────────────────────────────┘
```

---

## A2A Core Concepts (Quick Reference)

| Concept | Description |
|---------|-------------|
| **Agent Card** | JSON file at `/.well-known/agent.json` — advertises agent capabilities |
| **Task** | Unit of work sent from one agent to another |
| **Message** | Input/output of a task, composed of Parts |
| **Part** | A chunk inside a message: `TextPart`, `FilePart`, or `DataPart` |
| **Artifact** | Structured output produced by an agent (the result) |
| **Task States** | `submitted → working → completed / failed / canceled` |
| **Streaming** | SSE-based real-time task progress updates |
| **Push Notification** | Webhook callbacks when task state changes |

---

## Phase 1: Install Dependencies

```bash
pip install a2a-sdk            # Google's A2A Python SDK
pip install mcp                # Anthropic's MCP Python SDK (already planned)
pip install httpx              # Async HTTP client for A2A task sending
```

Add to `requirements.txt`:
```
a2a-sdk>=0.2.0
mcp>=1.0.0
httpx>=0.27.0
```

---

## Phase 2: Agent Card — Advertise This Agent

The Agent Card is a JSON metadata file served at `/.well-known/agent.json`. It tells other agents what this agent can do, how to reach it, and what authentication is needed.

### `src/a2a/agent_card.py`

```python
from a2a.types import AgentCard, AgentCapabilities, AgentSkill, AgentAuthentication

def build_agent_card(base_url: str = "http://localhost:8000") -> AgentCard:
    return AgentCard(
        name="Medical Document Intelligence Agent",
        description=(
            "Processes medical documents (prescriptions, lab reports, invoices, ID cards) "
            "through classification, structured data extraction, clinical validation, "
            "PII redaction, and HIPAA-compliant reporting."
        ),
        url=base_url,
        version="1.0.0",
        capabilities=AgentCapabilities(
            streaming=True,           # SSE streaming supported
            pushNotifications=True,   # Webhook callbacks supported
            stateTransitionHistory=True
        ),
        authentication=AgentAuthentication(
            schemes=["bearer"]        # API key via Bearer token
        ),
        skills=[
            AgentSkill(
                id="process_medical_document",
                name="Process Medical Document",
                description="Full pipeline: classify → extract → validate → repair → redact → report",
                inputModes=["text", "file"],
                outputModes=["data", "text"]
            ),
            AgentSkill(
                id="classify_document",
                name="Classify Document",
                description="Classify document as PRESCRIPTION, LAB_REPORT, or UNKNOWN",
                inputModes=["text"],
                outputModes=["data"]
            ),
            AgentSkill(
                id="redact_pii",
                name="Redact PII",
                description="HIPAA Safe Harbor PII detection and redaction across 18 PHI categories",
                inputModes=["text"],
                outputModes=["text", "data"]
            ),
            AgentSkill(
                id="validate_extraction",
                name="Validate Extraction",
                description="Clinically validate structured data with domain-specific flags",
                inputModes=["data"],
                outputModes=["data"]
            ),
        ],
        defaultInputModes=["text", "file"],
        defaultOutputModes=["data"]
    )
```

### Register in FastAPI (`src/api/main.py`)

```python
from src.a2a.agent_card import build_agent_card

@app.get("/.well-known/agent.json")
async def get_agent_card():
    """A2A Agent Card discovery endpoint."""
    return build_agent_card(base_url=settings.api.base_url)
```

---

## Phase 3: A2A Server — Accept Tasks from External Agents

### `src/a2a/task_manager.py`

Manages task lifecycle and maps incoming A2A tasks to the LangGraph pipeline.

```python
import uuid
import asyncio
from typing import AsyncIterator
from a2a.types import Task, TaskStatus, TaskState, Message, TextPart, DataPart, Artifact
from src.core.graph import build_graph
from src.core.state import DocState

class MedicalDocTaskManager:
    """Handles A2A task lifecycle and routes to LangGraph pipeline."""

    def __init__(self):
        self.tasks: dict[str, Task] = {}
        self.graph = build_graph()

    async def create_task(self, message: Message, skill_id: str = None) -> Task:
        task_id = str(uuid.uuid4())
        task = Task(
            id=task_id,
            status=TaskStatus(state=TaskState.submitted),
            history=[message]
        )
        self.tasks[task_id] = task
        asyncio.create_task(self._execute_task(task_id, message, skill_id))
        return task

    async def _execute_task(self, task_id: str, message: Message, skill_id: str):
        task = self.tasks[task_id]
        task.status = TaskStatus(state=TaskState.working)

        try:
            # Extract document text from message parts
            raw_text = self._extract_text(message)
            llm_provider = self._extract_provider(message)

            # Build initial DocState
            initial_state: DocState = {
                "raw_text": raw_text,
                "llm_provider": llm_provider,
                "file_path": "a2a_task",
                "doc_type": None,
                "extracted_data": None,
                "validated_data": None,
                "validation_flags": [],
                "redacted_text": None,
                "errors": [],
                "trace_log": [],
                "repair_attempts": 0,
                "repair_summary": None,
                "llm_model_name": None,
                "confidence_score": None,
                "start_time": None,
                "detected_pii": [],
                "ground_truth_pii": []
            }

            # Route to specific skill if requested
            if skill_id == "classify_document":
                result = await self._run_classifier_only(initial_state)
            elif skill_id == "redact_pii":
                result = await self._run_redactor_only(initial_state)
            else:
                result = await self.graph.ainvoke(initial_state)

            # Build A2A Artifact from result
            task.artifacts = [
                Artifact(
                    parts=[DataPart(data=result)],
                    description="Medical document processing result"
                )
            ]
            task.status = TaskStatus(state=TaskState.completed)

        except Exception as e:
            task.status = TaskStatus(
                state=TaskState.failed,
                message=Message(parts=[TextPart(text=str(e))])
            )

    async def stream_task(self, task_id: str) -> AsyncIterator[Task]:
        """Stream task state changes via SSE."""
        task = self.tasks[task_id]
        last_state = None
        while task.status.state in (TaskState.submitted, TaskState.working):
            if task.status.state != last_state:
                yield task
                last_state = task.status.state
            await asyncio.sleep(0.1)
        yield task  # Final state

    def get_task(self, task_id: str) -> Task | None:
        return self.tasks.get(task_id)

    def _extract_text(self, message: Message) -> str:
        for part in message.parts:
            if isinstance(part, TextPart):
                return part.text
            if isinstance(part, DataPart) and "text" in part.data:
                return part.data["text"]
        raise ValueError("No text content found in message parts")

    def _extract_provider(self, message: Message) -> str:
        for part in message.parts:
            if isinstance(part, DataPart):
                return part.data.get("llm_provider", "groq")
        return "groq"
```

### `src/a2a/server.py`

```python
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from a2a.types import SendTaskRequest, GetTaskRequest, TaskSendParams
import json

from src.a2a.task_manager import MedicalDocTaskManager

task_manager = MedicalDocTaskManager()

def register_a2a_routes(app: FastAPI):
    """Register A2A task endpoints on the existing FastAPI app."""

    @app.post("/a2a/tasks/send")
    async def send_task(request: SendTaskRequest):
        """A2A endpoint: accept a task from an external agent."""
        task = await task_manager.create_task(
            message=request.params.message,
            skill_id=request.params.metadata.get("skill_id") if request.params.metadata else None
        )
        return {"id": task.id, "status": task.status}

    @app.get("/a2a/tasks/{task_id}")
    async def get_task(task_id: str):
        """A2A endpoint: poll task status and result."""
        task = task_manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return task

    @app.get("/a2a/tasks/{task_id}/stream")
    async def stream_task(task_id: str):
        """A2A endpoint: stream task progress via SSE."""
        task = task_manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        async def event_generator():
            async for state in task_manager.stream_task(task_id):
                yield f"data: {json.dumps(state.dict())}\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")
```

### Register in `src/api/main.py`

```python
from src.a2a.server import register_a2a_routes

# After app = FastAPI(...)
register_a2a_routes(app)
```

---

## Phase 4: A2A Client — Delegate to Sub-Agents

This allows the medical document agent to delegate specialized work to other agents. This is where multi-agent collaboration happens.

### Potential Sub-Agent Delegations

| Sub-Agent | Delegated Task | When Used |
|-----------|---------------|-----------|
| **OCR Agent** | Extract text from image/scanned PDFs | `file_path` is an image |
| **Pharma Knowledge Agent** | Validate drug names, interactions | Repair agent needs drug context |
| **Compliance Agent** | Deep HIPAA audit | High-sensitivity documents |
| **Translation Agent** | Non-English documents | `doc_language != "en"` |
| **Summarization Agent** | Patient-friendly summary | Post-processing output |

### `src/a2a/client.py`

```python
import httpx
from a2a.types import Message, TextPart, DataPart, Task, TaskState
import asyncio

class A2AClient:
    """Client for delegating tasks to other A2A-compatible agents."""

    def __init__(self, agent_url: str, api_key: str = None):
        self.agent_url = agent_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    async def get_agent_card(self) -> dict:
        """Discover agent capabilities before sending tasks."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.agent_url}/.well-known/agent.json",
                headers=self.headers
            )
            resp.raise_for_status()
            return resp.json()

    async def send_task(self, text: str, skill_id: str = None, data: dict = None) -> Task:
        """Send a task to a remote A2A agent and wait for completion."""
        parts = [TextPart(text=text)]
        if data:
            parts.append(DataPart(data=data))

        payload = {
            "id": "req-1",
            "jsonrpc": "2.0",
            "method": "tasks/send",
            "params": {
                "message": {"role": "user", "parts": [p.dict() for p in parts]},
                "metadata": {"skill_id": skill_id} if skill_id else {}
            }
        }

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.agent_url}/a2a/tasks/send",
                json=payload,
                headers=self.headers
            )
            resp.raise_for_status()
            task_data = resp.json()
            task_id = task_data["id"]

        # Poll until complete
        return await self._poll_until_complete(task_id)

    async def _poll_until_complete(self, task_id: str, poll_interval: float = 0.5) -> Task:
        async with httpx.AsyncClient(timeout=120) as client:
            while True:
                resp = await client.get(
                    f"{self.agent_url}/a2a/tasks/{task_id}",
                    headers=self.headers
                )
                resp.raise_for_status()
                task = resp.json()
                state = task["status"]["state"]

                if state == TaskState.completed:
                    return task
                elif state == TaskState.failed:
                    raise RuntimeError(f"Sub-agent task failed: {task['status']}")
                elif state == TaskState.canceled:
                    raise RuntimeError("Sub-agent task was canceled")

                await asyncio.sleep(poll_interval)
```

### Example: Calling OCR Sub-Agent from Repair Agent

```python
# In src/core/agents/repair.py — when document is an image
from src.a2a.client import A2AClient

async def repair_with_ocr_fallback(state: DocState) -> DocState:
    if state.get("is_image_document"):
        ocr_agent = A2AClient(
            agent_url="http://ocr-agent.internal:8001",
            api_key=settings.sub_agents.ocr_api_key
        )
        result = await ocr_agent.send_task(
            text="Extract text from this medical document image",
            skill_id="ocr_extract",
            data={"file_path": state["file_path"]}
        )
        state["raw_text"] = result["artifacts"][0]["parts"][0]["text"]
    # Continue with normal repair...
    return state
```

---

## Phase 5: Sub-Agent Registry

Centralize all external agent connections in one place.

### `src/a2a/registry.py`

```python
from dataclasses import dataclass
from src.a2a.client import A2AClient
from config.settings import settings

@dataclass
class SubAgentRegistry:
    """Registry of all delegatable A2A sub-agents."""

    ocr_agent: A2AClient | None = None
    pharma_agent: A2AClient | None = None
    compliance_agent: A2AClient | None = None
    translation_agent: A2AClient | None = None

    @classmethod
    def from_settings(cls) -> "SubAgentRegistry":
        registry = cls()

        if hasattr(settings, "sub_agents"):
            if settings.sub_agents.ocr_url:
                registry.ocr_agent = A2AClient(
                    agent_url=settings.sub_agents.ocr_url,
                    api_key=settings.sub_agents.ocr_api_key
                )
            if settings.sub_agents.pharma_url:
                registry.pharma_agent = A2AClient(
                    agent_url=settings.sub_agents.pharma_url,
                    api_key=settings.sub_agents.pharma_api_key
                )
        return registry

# Global registry instance
sub_agents = SubAgentRegistry.from_settings()
```

---

## Phase 6: Multi-Agent Workflow Example

This illustrates an end-to-end scenario where an external orchestrator uses A2A to send a task, and this agent internally uses MCP tools + delegates to sub-agents.

```
External Orchestrator
    │
    │  A2A: "Process this prescription PDF"
    ▼
Medical Document Agent (THIS PROJECT)
    │
    ├─► A2A Client → OCR Agent: "Extract text from PDF image"
    │        └── returns raw text
    │
    ├─► MCP Tool: classify_document(raw_text)
    │        └── returns: PRESCRIPTION
    │
    ├─► MCP Tool: extract_data(raw_text, type=PRESCRIPTION)
    │        └── returns: structured JSON
    │
    ├─► MCP Tool: validate_extraction(json)
    │        └── returns: validation_flags [EXTREME_DOSAGE]
    │
    ├─► A2A Client → Pharma Agent: "Verify dosage for Amoxicillin 7000mg"
    │        └── returns: "7000mg is invalid, standard is 500mg"
    │
    ├─► MCP Tool: repair_data(json, flags, pharma_context)
    │        └── returns: corrected JSON
    │
    ├─► MCP Tool: redact_pii(raw_text)
    │        └── returns: redacted text
    │
    └─► A2A Response → External Orchestrator
             └── Artifact: { validated_data, redacted_text, flags, metrics }
```

---

## Phase 7: File Structure

```
src/
├── a2a/
│   ├── __init__.py
│   ├── agent_card.py       # AgentCard definition (skills, capabilities)
│   ├── server.py           # A2A task endpoints (send, get, stream)
│   ├── task_manager.py     # Task lifecycle → LangGraph pipeline
│   ├── client.py           # A2A client for calling sub-agents
│   └── registry.py         # Sub-agent registry
├── mcp_server/
│   ├── __init__.py
│   ├── server.py           # MCP tool server
│   └── tool_handlers.py    # Tool → agent mapping
├── mcp_host/
│   ├── __init__.py
│   ├── host.py             # Custom MCP host (Groq/Ollama/Bedrock)
│   └── tool_formatter.py   # MCP → LLM tool format
config/
└── settings.py             # Add SubAgentsConfig section
scripts/
└── mcp_cli.py              # CLI entry point
```

---

## Phase 8: Configuration Updates

Add sub-agent URLs to `config/settings.py`:

```python
class SubAgentsConfig(BaseModel):
    """Configuration for external A2A sub-agents."""
    ocr_url: str = ""            # "" = not configured, skip delegation
    ocr_api_key: str = ""
    pharma_url: str = ""
    pharma_api_key: str = ""
    compliance_url: str = ""
    compliance_api_key: str = ""
    translation_url: str = ""
    translation_api_key: str = ""

class Settings(BaseModel):
    # ... existing fields ...
    sub_agents: SubAgentsConfig = SubAgentsConfig()
```

Environment variables (`.env`):
```
SUB_AGENTS__OCR_URL=http://ocr-agent.internal:8001
SUB_AGENTS__OCR_API_KEY=your-key-here
SUB_AGENTS__PHARMA_URL=http://pharma-agent.internal:8002
```

---

## Protocol Comparison Summary

| Feature | MCP | A2A |
|---------|-----|-----|
| **Purpose** | Agent accesses tools/data | Agent delegates to agents |
| **Transport** | stdio or HTTP/SSE | HTTP/SSE (JSON-RPC 2.0) |
| **Authentication** | API key / OAuth | Bearer token / OAuth2 |
| **Discovery** | Server lists tools | `/.well-known/agent.json` |
| **State** | Stateless tool calls | Stateful task lifecycle |
| **Streaming** | SSE | SSE |
| **This project** | LLM host calls tools | External agents send documents |

---

## Recommended Implementation Order

| Step | Task | Effort |
|------|------|--------|
| 1 | Install `a2a-sdk`, `mcp` packages | Small |
| 2 | Scaffold `src/a2a/` directory | Small |
| 3 | Build `agent_card.py` + serve at `/.well-known/agent.json` | Small |
| 4 | Build `task_manager.py` (A2A → LangGraph bridge) | Medium |
| 5 | Register A2A routes in `src/api/main.py` | Small |
| 6 | Implement MCP server (Phase 1 of MCP plan) | Medium |
| 7 | Build `mcp_host/host.py` (custom host with Groq) | Medium |
| 8 | Add `src/a2a/client.py` for sub-agent delegation | Medium |
| 9 | Add `src/a2a/registry.py` + `SubAgentsConfig` | Small |
| 10 | Test full flow: External agent → A2A → LangGraph → MCP tools | Medium |
| 11 | Add human-review A2A skill (maps to `/process/with-review`) | Medium |
| 12 | Streamlit: add MCP chat tab + A2A status dashboard | Medium |

---

## Key Benefits of the A2A + MCP Combination

1. **A2A makes this agent discoverable** — any A2A-compatible orchestrator (Google ADK, AutoGen, CrewAI, etc.) can find and use it automatically via the Agent Card
2. **MCP makes tools reusable** — the same classify/extract/redact tools can be used by the A2A task manager, the MCP host, or any future integration
3. **Layered separation** — MCP handles *capability access*, A2A handles *agent collaboration*; neither overlaps
4. **No vendor lock-in** — A2A is open standard (Google), MCP is open standard (Anthropic); both work with Groq/Ollama/Bedrock
5. **Incremental adoption** — each phase is independently useful; you don't need all sub-agents configured to run the A2A server
