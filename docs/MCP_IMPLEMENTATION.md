# MCP (Model Context Protocol) Implementation Plan

## Overview

This project is an excellent candidate for MCP. The existing modular agents, FastAPI API, and LangGraph orchestration provide a solid foundation. MCP adds a **standardized protocol layer** so any MCP-compatible client can interact with the document processing pipeline as tools.

---

## Current vs. MCP Architecture

### Current Architecture
```
Streamlit UI → FastAPI API → LangGraph Pipeline → Agents (Classifier, Extractor, Validator, Repair, Redactor, Reporter)
```

### With MCP Added
```
Any MCP Client (custom host, IDE plugins, other apps)
        ↓ (JSON-RPC over stdio/SSE)
   MCP Server (exposes pipeline as tools + resources)
        ↓
   LangGraph Pipeline → Agents
```

---

## Phase 1: MCP Server — Expose Pipeline as Tools

### Installation
```bash
pip install mcp
```

### Tools to Expose

| Tool Name | Description | Maps To |
|-----------|-------------|---------|
| `classify_document` | Classify a medical document | Classifier agent |
| `extract_data` | Extract structured data from document | Extractor agent |
| `validate_extraction` | Validate extracted data with clinical checks | Validator agent |
| `repair_data` | Repair invalid extractions | Repair agent |
| `redact_pii` | HIPAA-compliant PII redaction | Redactor agent |
| `process_document` | Full end-to-end pipeline | `/process` endpoint |
| `process_with_review` | Pipeline with human-in-the-loop | `/process/with-review` endpoint |
| `get_metrics` | Retrieve performance metrics | MetricsEvaluator |

### Resources to Expose

| Resource URI | Description |
|-------------|-------------|
| `medical://metrics` | Current metrics_report.csv data |
| `medical://reports/{id}` | Individual trace reports |
| `medical://schema/prescription` | Prescription JSON schema |
| `medical://schema/lab_report` | Lab report JSON schema |

### Server Skeleton — `src/mcp_server/server.py`

```python
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, Resource
import json

app = Server("medical-doc-processor")

@app.list_tools()
async def list_tools():
    return [
        Tool(
            name="process_document",
            description="Process a medical document through the full pipeline (classify → extract → validate → repair → redact → report)",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Raw document text"},
                    "llm_provider": {
                        "type": "string",
                        "enum": ["ollama", "groq", "bedrock"],
                        "default": "groq"
                    }
                },
                "required": ["text"]
            }
        ),
        Tool(
            name="classify_document",
            description="Classify a medical document as PRESCRIPTION, LAB_REPORT, or UNKNOWN",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Raw document text"}
                },
                "required": ["text"]
            }
        ),
        # ... additional tools
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "process_document":
        from src.core.graph import app as graph_app
        result = await graph_app.ainvoke({
            "raw_text": arguments["text"],
            "llm_provider": arguments.get("llm_provider", "groq"),
            # ... initialize DocState fields
        })
        return [TextContent(type="text", text=json.dumps(result, default=str))]
    # ... handle other tools

async def main():
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

---

## Phase 2: Custom MCP Host (No Claude Required)

Since Claude Desktop is not available, a custom host is built using the existing LLM providers (Groq, Ollama, Bedrock). The host:

1. Connects to the MCP server as a client
2. Uses your LLMs to reason about which tools to call
3. Implements the agentic tool-calling loop

### Host Implementation — `src/mcp_host/host.py`

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_core.messages import HumanMessage, SystemMessage
from src.core.clients.llm_client import UnifiedLLMManager

class MCPHost:
    """Custom MCP host using existing LLM providers (Groq/Ollama/Bedrock)."""

    def __init__(self, llm_provider: str = "groq"):
        self.llm_manager = UnifiedLLMManager()
        self.llm_provider = llm_provider
        self.session = None

    async def connect(self, server_script: str):
        """Connect to MCP server via stdio transport."""
        server_params = StdioServerParameters(
            command="python",
            args=[server_script]
        )
        self.transport = stdio_client(server_params)
        read, write = await self.transport.__aenter__()
        self.session = ClientSession(read, write)
        await self.session.__aenter__()
        await self.session.initialize()

    async def get_available_tools(self):
        """List tools exposed by the MCP server."""
        result = await self.session.list_tools()
        return result.tools

    async def process_query(self, user_query: str):
        """
        Send user query to LLM, let it decide which MCP tools to call,
        execute them, and return the final answer.
        Implements the agentic tool-calling loop.
        """
        tools = await self.get_available_tools()
        tool_descriptions = self._format_tools_for_llm(tools)
        llm = self.llm_manager.get_llm(self.llm_provider)

        messages = [
            SystemMessage(content=f"You have these tools:\n{tool_descriptions}\n\nUse them to answer the user's request."),
            HumanMessage(content=user_query)
        ]

        while True:
            response = llm.invoke(messages)

            if has_tool_calls(response):
                for tool_call in response.tool_calls:
                    result = await self.session.call_tool(
                        tool_call["name"],
                        tool_call["args"]
                    )
                    messages.append(format_tool_result(tool_call, result))
            else:
                return response.content  # Final answer reached
```

---

## Phase 3: Integration Options

### Option A: CLI Host — `scripts/mcp_cli.py`

Minimal interactive CLI for testing the MCP pipeline:

```python
async def main():
    host = MCPHost(llm_provider="groq")
    await host.connect("src/mcp_server/server.py")

    while True:
        query = input("You: ")
        response = await host.process_query(query)
        print(f"Assistant: {response}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

### Option B: Streamlit UI Integration

Add an **MCP Chat** tab to the existing Streamlit UI (`src/ui/app.py`) so users can interact with the pipeline through natural language instead of only file upload:

```python
# In src/ui/app.py — add a chat interface tab
with tab_chat:
    user_input = st.chat_input("Ask about a medical document...")
    if user_input:
        response = asyncio.run(mcp_host.process_query(user_input))
        st.chat_message("assistant").write(response)
```

### Option C: SSE Transport (HTTP-based Remote Access)

Serve MCP over HTTP/SSE instead of stdio so external applications can connect remotely. Mount alongside the existing FastAPI app:

```python
# In src/api/main.py
from mcp.server.sse import SseServerTransport
from starlette.routing import Route, Mount

sse = SseServerTransport("/mcp/messages")

# Add SSE endpoint
async def handle_sse(request):
    async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
        await mcp_app.run(streams[0], streams[1], mcp_app.create_initialization_options())

# Mount to existing FastAPI app
app.mount("/mcp", Starlette(routes=[
    Route("/sse", endpoint=handle_sse),
    Mount("/messages", app=sse.handle_post_message),
]))
```

---

## Phase 4: File Structure

```
src/
├── mcp_server/
│   ├── __init__.py
│   ├── server.py           # MCP server exposing tools + resources
│   └── tool_handlers.py    # Maps MCP tool calls → agents/graph
├── mcp_host/
│   ├── __init__.py
│   ├── host.py             # Custom MCP host (Groq/Ollama/Bedrock)
│   └── tool_formatter.py   # Converts MCP tool schemas → LLM tool format
scripts/
└── mcp_cli.py              # CLI entry point for MCP interaction
```

---

## Phase 5: Key Implementation Details

### Tool Calling Support Across LLM Providers

All three providers support tool/function calling and work with LangChain's `bind_tools()`:

| Provider | Model | Tool Calling |
|----------|-------|-------------|
| **Groq** | llama-3.3-70b-versatile | Native, via LangChain `.bind_tools()` |
| **Ollama** | llama3.1:8b | Supported in recent versions |
| **Bedrock** | Claude 3 Haiku | Native support |

### Reusing Existing Code

No duplication — MCP wraps what already exists:

| Existing Component | MCP Role |
|-------------------|----------|
| `UnifiedLLMManager` | Powers the host's reasoning |
| `build_graph()` / individual agents | Power the server's tools |
| `DocState` | Maps to MCP tool input/output schemas |
| `MetricsEvaluator` | Exposed as a resource |
| `/process` FastAPI endpoint | Wrapped by `process_document` tool |

### Security Considerations

- Add API key validation for remote MCP connections (SSE transport)
- Ensure PII data from tool responses is not logged in plaintext
- Use HTTPS for remote SSE transport in production

---

## Recommended Implementation Order

| Step | Task | Effort |
|------|------|--------|
| 1 | `pip install mcp` and scaffold `src/mcp_server/` | Small |
| 2 | Implement `process_document` tool (wraps full pipeline) | Medium |
| 3 | Add individual agent tools (classify, extract, validate, redact) | Medium |
| 4 | Build `src/mcp_host/host.py` with Groq as the reasoning LLM | Medium |
| 5 | Create CLI host in `scripts/mcp_cli.py` | Small |
| 6 | Add resources (metrics, schemas, reports) | Small |
| 7 | Add SSE transport option to `src/api/main.py` | Medium |
| 8 | Integrate MCP chat tab into Streamlit UI | Medium |

---

## Why This Works Well for This Project

1. **Modular agents** — each maps cleanly to a single MCP tool
2. **All LLM providers support tool calling** — the host can use any of them
3. **LangGraph handles orchestration** — MCP adds a standard access layer on top
4. **Composability** — other MCP servers (file system, database, web search) can be connected alongside this one
5. **Future-proof** — any MCP-compatible application can use this medical document processor without code changes
