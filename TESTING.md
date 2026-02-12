# Testing Guide - Groq Provider

## Overview
Comprehensive test suite for the Agentic Document Processor using **Groq** as the LLM provider.

## Prerequisites

1. **Groq API Key**: Set in `.env` file
   ```
   GROQ_API_KEY=your_groq_api_key_here
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   pip install pytest pytest-asyncio
   ```

## Test Structure

```
tests/
├── conftest.py                    # Pytest configuration & fixtures
├── test_agents.py                 # Unit tests (mocked)
├── test_groq_integration.py       # Integration tests (real Groq API)
├── test_groq_validation.py        # Validation & PII tests
└── test_pipeline.py               # Existing pipeline tests
```

## Running Tests

### Quick Start
```bash
# Run all Groq tests
python run_tests.py all

# Run quick tests (skip performance)
python run_tests.py quick
```

### By Category
```bash
# Integration tests only
python run_tests.py integration

# Validation tests only
python run_tests.py validation

# PII redaction tests only
python run_tests.py pii

# Performance benchmarks
python run_tests.py performance
```

### Using Pytest Directly
```bash
# All Groq tests
pytest -m groq -v

# Specific test file
pytest tests/test_groq_integration.py -v

# Specific test
pytest tests/test_groq_integration.py::TestGroqIntegration::test_groq_invoice_happy_path -v

# With coverage
pytest -m groq --cov=app --cov-report=html
```

## Test Categories

### 1. Integration Tests (`test_groq_integration.py`)
- ✅ **Happy path** - Invoice & ID card processing
- ✅ **PII redaction accuracy** - Recall ≥95%, Precision ≥90%
- ✅ **Missing fields handling**
- ✅ **OCR noise handling**
- ✅ **Malformed JSON recovery**
- ✅ **Empty document handling**
- ✅ **Special characters & unicode**

### 2. Validation Tests (`test_groq_validation.py`)
- ✅ **Schema validation** - Pydantic compliance
- ✅ **Self-repair mechanism** - Auto-fix validation errors
- ✅ **Regex validation** - Pattern enforcement
- ✅ **Field accuracy** - ≥90% threshold

### 3. PII Redaction Tests
- ✅ **PII recall** - ≥95% threshold
- ✅ **PII precision** - ≥90% threshold (no false positives)
- ✅ **Multiple PII types** - Email, phone, SSN, addresses, etc.

### 4. Performance Tests
- ✅ **Latency benchmark** - p95 ≤ 4s
- ✅ **Workflow success rate** - ≥90%

## Success Criteria

| Metric | Target | Test |
|--------|--------|------|
| Extraction Accuracy | ≥90% | `test_groq_field_accuracy_threshold` |
| PII Recall | ≥95% | `test_groq_pii_recall_threshold` |
| PII Precision | ≥90% | `test_groq_pii_precision_threshold` |
| P95 Latency | ≤4s | `test_groq_latency_benchmark` |
| Workflow Success | ≥90% | `test_groq_workflow_success_rate` |

## Example Test Output

```
tests/test_groq_integration.py::TestGroqIntegration::test_groq_invoice_happy_path PASSED

✅ Groq Invoice Test Passed:
   Latency: 2.45s
   Accuracy: 100.0%
   Fields: ['invoice_number', 'vendor_name', 'total_amount', 'date']
```

## Troubleshooting

### API Key Issues
```bash
# Check if key is loaded
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('GROQ_API_KEY'))"
```

### Rate Limiting
If you hit Groq rate limits, tests will fail. Wait a few minutes and retry.

### Timeout Errors
Increase timeout in `llm_client.py` if needed:
```python
@retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(3))
```

## Continuous Integration

Add to GitHub Actions:
```yaml
- name: Run Groq Tests
  env:
    GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}
  run: python run_tests.py quick
```

## Next Steps

1. ✅ Run quick tests: `python run_tests.py quick`
2. ✅ Review test results
3. ✅ Run full suite: `python run_tests.py all`
4. ✅ Generate coverage report: `pytest -m groq --cov=app --cov-report=html`
5. ✅ Review metrics in test output
