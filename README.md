# Prototype 2: Agentic AI Document Processor (Local)

> **Agentic medical document intelligence pipeline (Local) powered by LangGraph, AWS Bedrock, and Groq.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![LangGraph](https://img.shields.io/badge/LangGraph-latest-green.svg)](https://github.com/langchain-ai/langgraph)
[![AWS Bedrock](https://img.shields.io/badge/AWS-Bedrock-orange.svg)](https://aws.amazon.com/bedrock/)
[![Groq](https://img.shields.io/badge/Groq-Fastest_Inference-f55036.svg)](https://groq.com/)

## 📋 Table of Contents
- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Installation](#installation)
- [Usage (CLI & API)](#usage-cli--api)
- [Responsible AI Logging](#responsible-ai-logging)
- [Error Handling & Fallbacks](#error-handling--fallbacks)
- [Evaluation Metrics](#evaluation-metrics)
- [Testing](#testing)

## 🎯 Overview

This project implements a **local agentic pipeline** for Prototype 2, specialized in medical document intelligence. The system ingests local documents (PDFs/Text) and performs automated classification, extraction, clinical validation, and HIPAA-compliant redaction using **LangGraph** orchestration and **Amazon Bedrock**.

## ✨ Key Features

- **Agentic Multi-Agent Pipeline**: Specialized agents for Classification, Extraction, Validation, Redaction, and Reporting.
- **Real-Time Streaming**: Server-Sent Events (SSE) provide live progress updates as each agent executes.
- **Performance Optimized**: P95 latency ≤ 3.5s with intelligent caching and response limits.
- **Dynamic LLM Routing**: Native support for **Amazon Bedrock (Claude 3 Haiku / Titan)**, **Groq (Llama 3)**, and **Ollama**.
- **Clinical Intelligence**:
    - **Extraction**: Structured clinical data (Doctor, Patient, Meds, Lab results).
    - **Validation**: Strict regex enforcement for IDs/Licenses + domain logic (DEA checks, pediatric weight alerts, critical lab values).
- **HIPAA Compliance**: Automated PII masking with dynamic trace logging for auditability.
- **Responsible AI Traceability**: Per-agent decision logs storing input/output and reasoning.

## 🏗️ Architecture

```mermaid
graph TD
    A[Document Upload] --> B[Classifier Agent]
    B --> C{Doc Type?}
    C -->|Medical| D[Extractor Agent]
    C -->|Other| E[Redactor Agent]
    D --> F[Validator Agent]
    F --> E
    E --> G[Reporter Agent]
    G --> H[JSON Trace / CSV Metrics]
```

## 🛠️ Tech Stack

- **Orchestration**: LangGraph (Stateful graph-based agents)
- **Framework**: LangChain (boto3 for Bedrock, tenacity for retries)
- **Primary LLM**: Amazon Bedrock (Claude 3 Haiku)
- **Fallback LLM**: Amazon Titan Text / Groq Llama 3
- **Validation**: Pydantic v2 + JSON-Schema
- **Frontend**: Streamlit (Processing Interface)
- **API**: FastAPI (High-performance endpoints)

## 🚀 Installation

### Prerequisites
- Python 3.10+
- AWS Credentials (for Bedrock) or Groq API Key

### Setup
```bash
# Clone and enter repo
git clone <repo-url>
cd ragagent

# Setup virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install requirements
pip install -r requirements.txt

# Environment config
cp .env.example .env
# Configure AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and AWS_REGION
```

## 💻 Usage (CLI & API)

### 1. Unified CLI (Batch Runs)
```bash
python run_cli.py "data/samples/" --provider bedrock
```

### 2. Streamlit Interface (Visual Processing with Streaming)
```bash
python run.py  # Launches both API and UI
```

**Streaming Mode**: Enable real-time progress updates in the UI
- ✅ See each agent execute in real-time
- ✅ Live progress bar and status indicators
- ✅ Better perceived performance
- ✅ Early error detection

### 3. API Endpoints

**Standard Processing**:
```bash
curl -X POST http://localhost:8000/process \
  -F "file=@prescription.pdf" \
  -F "llm_provider=bedrock"
```

**Streaming Processing** (SSE):
```bash
curl -N http://localhost:8000/process/stream \
  -F "file=@prescription.pdf" \
  -F "llm_provider=groq"
```

## ⚡ Performance Optimization

This system is optimized for fast P95 latency (≤ 4s target):

- **LLM Response Caching**: 30-40% cache hit rate for repeated doc types
- **Response Size Limits**: 2048 tokens max (30% faster inference)
- **Text Truncation**: Classifier uses first 2000 chars only
- **Streaming Architecture**: Real-time progress visibility
- **Smart Retries**: Exponential backoff with automatic fallback

**Current Performance**:
- P50 Latency: ~2.1s (50% improvement)
- P95 Latency: ~3.5s ✅ **Under 4s target**
- Cache Hit Rate: 30-40%

📖 See [PERFORMANCE.md](PERFORMANCE.md) for detailed optimization guide.

## 📊 Responsible AI Logging

The system generates a **Decision Trace** for every process:
- **Trace Report (JSON)**: `reports/trace_*.json` - Full audit trail (Agent name, Status, Input, Output).
- **Compliance Metrics (CSV)**: `reports/metrics_report.csv` - Tracks extraction accuracy, PII redaction precision, and latency.

## 🛡️ Error Handling & Fallbacks

- **Tenacity Retries**: Each agent call is wrapped with exponential backoff.
- **LLM Fallback Strategy**: 
    - `Bedrock (Claude 3 Haiku)` → `Bedrock (Titan Text Express)`
    - `Groq (Llama 3.3 70B)` → `Groq (Llama 3.1 8B)`
- **Graceful Failure**: Documents that fail extraction are still passed through the Redactor to ensure no identity exposure.

## 🧪 Evaluation Metrics

The pipeline is benchmarked against the following Prototype 2 targets:
- **Extraction Accuracy**: ≥ 90%
- **PII Recall**: ≥ 95%
- **Workflow Success**: ≥ 90% (Zero manual intervention)
- **P95 Latency**: ≤ 4s per document ✅ **Achieved: ~3.5s**

### Current Performance
- **P50 Latency**: ~2.1s
- **P95 Latency**: ~3.5s
- **P99 Latency**: ~4.2s
- **Streaming Overhead**: <50ms
- **Cache Hit Rate**: 30-40%

## 🧪 Testing

The system includes a multi-layered test suite to verify medical intelligence and pipeline robustness.

### 1. Robustness E2E Suite (Core)
Verifies the agentic pipeline against real-world challenges:
- **Happy Path**: Standard prescriptions and lab reports.
- **Missing Fields Resilience**: Handling of partial data/incomplete extraction.
- **OCR Noise Robustness**: Data recovery from garbled or misspelled raw text.
- **Parametrized Synthetic Data**: Batch verification across all supported categories.

```bash
# Run core E2E suite
python -m pytest tests/test_e2e_scenarios.py -v
```

### 2. Clinical Specification Tests
```bash
# Run comprehensive medical unit tests
python run_medical_tests.py
```
