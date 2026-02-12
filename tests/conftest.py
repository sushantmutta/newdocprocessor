"""
Pytest configuration and fixtures for the Agentic Document Processor test suite.
"""
import pytest
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.state import DocState
from app.llm_client import UnifiedLLMManager


@pytest.fixture
def sample_invoice_text():
    """Sample invoice text for testing."""
    return """
    TechCorp Solutions Inc.
    123 Business Street, San Francisco, CA 94105
    Email: billing@techcorp.com | Phone: +1-555-0123
    
    INVOICE
    Invoice Number: INV-2025-001234
    Date: 2025-01-15
    
    Bill To:
    John Doe
    456 Customer Ave
    New York, NY 10001
    
    Description                 Quantity    Unit Price    Total
    Software License            5           $1,200.00     $6,000.00
    Support Services            12          $500.00       $6,000.00
    
    Subtotal:                                             $12,000.00
    Tax (8%):                                             $960.00
    Total Amount:                                         $12,960.00
    
    Payment Terms: Net 30
    """


@pytest.fixture
def sample_id_card_text():
    """Sample ID card text for testing."""
    return """
    GOVERNMENT OF SAMPLE COUNTRY
    NATIONAL IDENTITY CARD
    
    Full Name: Jane Smith
    ID Number: ABC123456789
    Date of Birth: 1990-05-15
    Expiry Date: 2030-05-14
    
    Address: 789 Residential Blvd, Sample City, SC 12345
    """


@pytest.fixture
def sample_invoice_state():
    """Sample DocState for invoice testing."""
    return DocState(
        raw_text="""TechCorp Solutions
        Invoice: INV-2025-001
        Date: 2025-01-15
        Vendor: TechCorp Solutions
        Total: $5,000.00""",
        file_path="test_invoice.pdf",
        doc_type=None,
        extracted_data=None,
        validated_data=None,
        redacted_text=None,
        errors=[],
        trace_log=[],
        repair_attempts=0,
        llm_provider="ollama",
        llm_model_name=None
    )


@pytest.fixture
def sample_id_card_state():
    """Sample DocState for ID card testing."""
    return DocState(
        raw_text="""National ID Card
        Name: John Doe
        ID: ABC123456
        DOB: 1990-01-01
        Expiry: 2030-01-01""",
        file_path="test_id.pdf",
        doc_type=None,
        extracted_data=None,
        validated_data=None,
        redacted_text=None,
        errors=[],
        trace_log=[],
        repair_attempts=0,
        llm_provider="ollama",
        llm_model_name=None
    )


@pytest.fixture
def mock_llm_response():
    """Mock LLM response for testing."""
    class MockResponse:
        def __init__(self, content):
            self.content = content
    
    return MockResponse


@pytest.fixture
def test_pdf_path(tmp_path):
    """Create a temporary test PDF file."""
    pdf_path = tmp_path / "test_document.pdf"
    # Create a simple text file for testing (in real scenario, use PyPDF2 to create actual PDF)
    pdf_path.write_text("Test document content")
    return str(pdf_path)


@pytest.fixture(scope="session")
def test_data_dir():
    """Directory for test data files."""
    data_dir = Path(__file__).parent / "test_data"
    data_dir.mkdir(exist_ok=True)
    return data_dir


@pytest.fixture
def clean_reports_dir():
    """Clean up reports directory before tests."""
    reports_dir = Path(__file__).parent.parent / "reports"
    if reports_dir.exists():
        for file in reports_dir.glob("*.json"):
            file.unlink()
    yield reports_dir
    # Cleanup after test
    if reports_dir.exists():
        for file in reports_dir.glob("*.json"):
            file.unlink()


# Environment setup
@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Setup test environment variables."""
    os.environ.setdefault("LLM_PROVIDER", "ollama")
    os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")
    os.environ.setdefault("OLLAMA_PRIMARY_MODEL", "qwen3-vl:235b-cloud")
    os.environ.setdefault("OLLAMA_FALLBACK_MODEL", "qwen3-vl:235b-cloud")
    yield
    # Cleanup is automatic


# Markers for different test categories
def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line("markers", "unit: Unit tests for individual components")
    config.addinivalue_line("markers", "integration: Integration tests for full pipeline")
    config.addinivalue_line("markers", "performance: Performance and latency tests")
    config.addinivalue_line("markers", "edge_case: Edge case and error handling tests")
    config.addinivalue_line("markers", "pii: PII redaction tests")
    config.addinivalue_line("markers", "validation: Validation and schema tests")
    config.addinivalue_line("markers", "slow: Slow-running tests")
    config.addinivalue_line("markers", "bedrock: Tests requiring AWS Bedrock")
    config.addinivalue_line("markers", "groq: Tests requiring Groq API")
