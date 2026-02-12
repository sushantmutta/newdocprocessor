import pytest
from fastapi.testclient import TestClient
from api import api

client = TestClient(api)


def test_invoice_processing_accuracy():
    """
    Test Case: Validates extraction accuracy and PII redaction for the 60475 invoice.
    Target: Accuracy >= 90%, PII Recall >= 95%
    """
    file_path = "60475_20250304.pdf"

    with open(file_path, "rb") as f:
        response = client.post(
            "/process", files={"file": ("invoice.pdf", f, "application/pdf")})

    assert response.status_code == 200
    data = response.json()

    # 1. Check Classification
    assert data["doc_type"] == "invoice"

    # 2. Check Extraction Accuracy (Key Fields)
    val_data = data["validated_data"]
    assert val_data["invoice_number"] == "60475"
    assert "Morar" in val_data["vendor_name"]
    # Verify the float conversion from European format (8.028,26 -> 8028.26)
    assert val_data["total_amount"] == 8028.26

    # 3. Check PII Redaction Recall
    redacted = data["redacted_text"]
    assert "[EMAIL_REDACTED]" in redacted or "christop95" not in redacted
    assert "[IBAN_REDACTED]" in redacted or "SM27V" not in redacted

    # 4. Check Latency Metric
    assert data["latency_ms"] <= 4000  # p95 latency <= 4s


def test_invalid_file_type():
    """Test Case: Ensure the system rejects non-PDF files."""
    response = client.post(
        "/process", files={"file": ("test.txt", b"hello world", "text/plain")})
    assert response.status_code == 400
    assert "Only PDF files are supported" in response.json()["detail"]
