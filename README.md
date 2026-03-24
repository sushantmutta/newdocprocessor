# Agentic Document Processor

> Multi-agent medical document intelligence pipeline powered by LangGraph and AWS Bedrock

For detailed documentation, see [docs/README.md](docs/README.md)

## Quick Start

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Or install as a package
pip install -e .
```

### Running the Application

```bash
# Start all services (API + Streamlit UI)
python scripts/run.py

# Or run components individually:
# API Server
uvicorn src.api.main:api --reload --port 8000

# Streamlit UI
streamlit run src/ui/app.py
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src tests/

# Run specific test file
pytest tests/test_medical_agents.py
```

## Project Structure

```
newdocprocessor/
├── src/                    # Source code
│   ├── api/               # FastAPI endpoints
│   ├── core/              # Core business logic
│   │   ├── agents/        # LangGraph agents
│   │   ├── schemas/       # Pydantic schemas
│   │   └── clients/       # LLM clients
│   └── ui/                # Streamlit UI
├── scripts/               # Utility scripts
├── tests/                 # Test suite
├── data/                  # Data files
│   ├── labreports/       # Lab report samples
│   ├── prescriptions/    # Prescription samples
│   └── reports/          # Generated reports
├── docs/                  # Documentation
├── config/                # Configuration files
└── requirements.txt       # Dependencies
```

## Features

- 🤖 Multi-agent pipeline with specialized agents
- 📊 Real-time streaming with SSE
- 🔧 Intelligent self-repair capabilities
- 👤 Human-in-the-loop mode
- 🔒 HIPAA-compliant PII redaction
- 📈 Comprehensive metrics tracking
- 🚀 Multiple LLM providers (Bedrock, Groq, Ollama)

## Documentation

- [Full Documentation](docs/README.md)
- [Performance Metrics](docs/PERFORMANCE.md)
- [QA Basics](docs/QA_BASICS.txt)
- [Architecture Diagram](docs/diagrams/graph_diagram.mmd)

## License

MIT
