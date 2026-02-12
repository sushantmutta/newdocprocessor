"""
Validation and schema tests for Groq provider.
Tests Pydantic schema validation, regex rules, and self-repair mechanisms.
"""
import pytest
from app.state import DocState
from app.graph import app as langgraph_pipeline
import os


@pytest.mark.validation
@pytest.mark.groq
class TestGroqValidation:
    """Validation tests for Groq provider."""
    
    @pytest.fixture(autouse=True)
    def setup_groq(self):
        """Ensure Groq API key is available."""
        if not os.getenv("GROQ_API_KEY"):
            pytest.skip("GROQ_API_KEY not set in environment")
    
    def test_groq_invoice_schema_validation(self):
        """Test Pydantic schema validation for invoices with Groq."""
        invoice_text = """
        TechCorp Solutions
        Invoice Number: INV-2025-12345
        Date: 2025-01-15
        Vendor: TechCorp Solutions Inc.
        Total Amount: $15,000.50
        """
        
        initial_state = DocState(
            raw_text=invoice_text,
            file_path="schema_test.pdf",
            doc_type=None,
            extracted_data=None,
            validated_data=None,
            redacted_text=None,
            errors=[],
            trace_log=[],
            repair_attempts=0,
            llm_provider="groq",
            llm_model_name=None
        )
        
        final_state = langgraph_pipeline.invoke(initial_state)
        
        # Verify schema compliance
        assert final_state["validated_data"] is not None
        assert "invoice_number" in final_state["validated_data"]
        assert "vendor_name" in final_state["validated_data"]
        assert "total_amount" in final_state["validated_data"]
        assert "date" in final_state["validated_data"]
        
        # Verify data types
        assert isinstance(final_state["validated_data"]["total_amount"], (int, float))
        assert isinstance(final_state["validated_data"]["invoice_number"], str)
        
        print(f"\n✅ Groq Schema Validation Test Passed")
    
    def test_groq_self_repair_mechanism(self):
        """Test self-repair mechanism with Groq when validation fails."""
        # Intentionally incomplete invoice
        incomplete_invoice = """
        Invoice Number: INV-INCOMPLETE
        Date: 2025-01-15
        """
        # Missing vendor_name and total_amount
        
        initial_state = DocState(
            raw_text=incomplete_invoice,
            file_path="repair_test.pdf",
            doc_type=None,
            extracted_data=None,
            validated_data=None,
            redacted_text=None,
            errors=[],
            trace_log=[],
            repair_attempts=0,
            llm_provider="groq",
            llm_model_name=None
        )
        
        final_state = langgraph_pipeline.invoke(initial_state)
        
        # Check if repair was attempted
        if len(final_state["errors"]) > 0:
            assert final_state["repair_attempts"] > 0, "Repair should have been attempted"
            assert final_state["repair_attempts"] <= 2, "Should not exceed max repair attempts"
        
        print(f"\n✅ Groq Self-Repair Test:")
        print(f"   Repair attempts: {final_state['repair_attempts']}")
        print(f"   Errors: {len(final_state['errors'])}")
    
    def test_groq_regex_validation(self):
        """Test regex rule enforcement with Groq."""
        invoice_with_patterns = """
        Invoice Number: INV-2025-001
        Date: 2025-01-15
        Vendor: Test Corp
        Total: $1,000.00
        Email: contact@testcorp.com
        Phone: +1-555-0123
        """
        
        initial_state = DocState(
            raw_text=invoice_with_patterns,
            file_path="regex_test.pdf",
            doc_type=None,
            extracted_data=None,
            validated_data=None,
            redacted_text=None,
            errors=[],
            trace_log=[],
            repair_attempts=0,
            llm_provider="groq",
            llm_model_name=None
        )
        
        final_state = langgraph_pipeline.invoke(initial_state)
        
        # Verify regex patterns were applied in redaction
        redacted = final_state["redacted_text"]
        assert "[EMAIL_REDACTED]" in redacted or "contact@testcorp.com" not in redacted
        assert "[PHONE_REDACTED]" in redacted or "+1-555-0123" not in redacted
        
        print(f"\n✅ Groq Regex Validation Test Passed")
    
    def test_groq_field_accuracy_threshold(self):
        """Test that field extraction accuracy meets ≥90% threshold with Groq."""
        complete_invoice = """
        TechCorp Solutions Inc.
        123 Business Street
        San Francisco, CA 94105
        
        INVOICE
        Invoice Number: INV-2025-555666
        Date: 2025-01-20
        
        Bill To: Customer Corp
        
        Description: Professional Services
        Total Amount: $25,000.00
        """
        
        initial_state = DocState(
            raw_text=complete_invoice,
            file_path="accuracy_test.pdf",
            doc_type=None,
            extracted_data=None,
            validated_data=None,
            redacted_text=None,
            errors=[],
            trace_log=[],
            repair_attempts=0,
            llm_provider="groq",
            llm_model_name=None
        )
        
        final_state = langgraph_pipeline.invoke(initial_state)
        
        # Calculate accuracy
        expected_fields = ["invoice_number", "vendor_name", "total_amount", "date"]
        validated_data = final_state["validated_data"] or {}
        extracted_fields = [k for k, v in validated_data.items() if v is not None]
        
        accuracy = (len(extracted_fields) / len(expected_fields)) * 100
        
        assert accuracy >= 90, f"Field accuracy {accuracy}% below 90% threshold"
        
        print(f"\n✅ Groq Field Accuracy Test:")
        print(f"   Accuracy: {accuracy:.1f}%")
        print(f"   Fields extracted: {extracted_fields}")


@pytest.mark.pii
@pytest.mark.groq
class TestGroqPIIRedaction:
    """PII redaction tests for Groq provider."""
    
    @pytest.fixture(autouse=True)
    def setup_groq(self):
        """Ensure Groq API key is available."""
        if not os.getenv("GROQ_API_KEY"):
            pytest.skip("GROQ_API_KEY not set in environment")
    
    def test_groq_pii_recall_threshold(self):
        """Test PII recall ≥95% with Groq."""
        text_with_known_pii = """
        Customer Information:
        Name: John Michael Doe
        Email: john.doe@example.com
        Phone: +1-555-123-4567
        SSN: 123-45-6789
        Address: 456 Privacy Lane, Secure City, SC 12345
        Account: ACC-9876543210
        Date of Birth: 1985-03-15
        """
        
        initial_state = DocState(
            raw_text=text_with_known_pii,
            file_path="pii_recall_test.pdf",
            doc_type=None,
            extracted_data=None,
            validated_data=None,
            redacted_text=None,
            errors=[],
            trace_log=[],
            repair_attempts=0,
            llm_provider="groq",
            llm_model_name=None
        )
        
        final_state = langgraph_pipeline.invoke(initial_state)
        redacted = final_state["redacted_text"]
        
        # Known PII that should be redacted
        pii_items = [
            "john.doe@example.com",
            "+1-555-123-4567",
            "123-45-6789",
            "ACC-9876543210"
        ]
        
        # Count how many PII items were redacted
        redacted_count = sum(1 for pii in pii_items if pii not in redacted)
        recall = (redacted_count / len(pii_items)) * 100
        
        assert recall >= 95, f"PII recall {recall}% below 95% threshold"
        
        print(f"\n✅ Groq PII Recall Test:")
        print(f"   Recall: {recall:.1f}%")
        print(f"   Redacted: {redacted_count}/{len(pii_items)} items")
    
    def test_groq_pii_precision_threshold(self):
        """Test PII precision ≥90% with Groq (no false positives)."""
        text_with_non_pii = """
        Company: TechCorp Solutions Inc.
        Invoice: INV-2025-001
        Product: Software License
        Quantity: 5 units
        Price: $1,000.00
        Total: $5,000.00
        Terms: Net 30
        """
        
        initial_state = DocState(
            raw_text=text_with_non_pii,
            file_path="pii_precision_test.pdf",
            doc_type=None,
            extracted_data=None,
            validated_data=None,
            redacted_text=None,
            errors=[],
            trace_log=[],
            repair_attempts=0,
            llm_provider="groq",
            llm_model_name=None
        )
        
        final_state = langgraph_pipeline.invoke(initial_state)
        redacted = final_state["redacted_text"]
        
        # These should NOT be redacted (not PII)
        non_pii_items = [
            "TechCorp Solutions",
            "INV-2025-001",
            "Software License",
            "$5,000.00"
        ]
        
        # Count how many non-PII items were preserved
        preserved_count = sum(1 for item in non_pii_items if item in redacted)
        precision = (preserved_count / len(non_pii_items)) * 100
        
        assert precision >= 90, f"PII precision {precision}% below 90% threshold"
        
        print(f"\n✅ Groq PII Precision Test:")
        print(f"   Precision: {precision:.1f}%")
        print(f"   Preserved: {preserved_count}/{len(non_pii_items)} non-PII items")
    
    def test_groq_multiple_pii_types(self):
        """Test Groq redaction of multiple PII types."""
        mixed_pii_text = """
        Customer: Jane Smith
        Email: jane.smith@email.com
        Phone: +1-555-9999
        ID: ID123456789
        IBAN: GB82WEST12345698765432
        Address: 123 Main St, City, ST 12345
        """
        
        initial_state = DocState(
            raw_text=mixed_pii_text,
            file_path="multi_pii_test.pdf",
            doc_type=None,
            extracted_data=None,
            validated_data=None,
            redacted_text=None,
            errors=[],
            trace_log=[],
            repair_attempts=0,
            llm_provider="groq",
            llm_model_name=None
        )
        
        final_state = langgraph_pipeline.invoke(initial_state)
        redacted = final_state["redacted_text"]
        
        # Check for various redaction tags
        expected_tags = ["[EMAIL_REDACTED]", "[PHONE_REDACTED]", "[ID_NUMBER_REDACTED]", "[NAME_REDACTED]", "[ADDRESS_REDACTED]"]
        tags_found = [tag for tag in expected_tags if tag in redacted]
        
        assert len(tags_found) >= 3, f"Only {len(tags_found)} PII types redacted"
        
        print(f"\n✅ Groq Multiple PII Types Test:")
        print(f"   Tags found: {tags_found}")
