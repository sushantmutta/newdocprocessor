"""
Unit tests for individual agents in the document processing pipeline.
Tests each agent in isolation with mocked dependencies.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from app.state import DocState
from app.agents.classifier import classify_doc
from app.agents.extractor import extract_data
from app.agents.validator import validate_data
from app.agents.repair import repair_data
from app.agents.redactor import redact_pii
from app.agents.reporter import generate_report


@pytest.mark.unit
class TestClassifierAgent:
    """Tests for the Classifier Agent."""
    
    def test_classify_invoice_success(self, sample_invoice_state):
        """Test successful invoice classification."""
        with patch('app.agents.classifier.UnifiedLLMManager') as mock_llm:
            mock_instance = Mock()
            mock_response = Mock()
            mock_response.content = "invoice"
            mock_instance.invoke_with_fallback.return_value = mock_response
            mock_llm.return_value = mock_instance
            
            result = classify_doc(sample_invoice_state)
            
            assert result["doc_type"] == "invoice"
            assert len(result["trace_log"]) > 0
            assert result["trace_log"][0]["agent"] == "classifier"
    
    def test_classify_id_card_success(self, sample_id_card_state):
        """Test successful ID card classification."""
        with patch('app.agents.classifier.UnifiedLLMManager') as mock_llm:
            mock_instance = Mock()
            mock_response = Mock()
            mock_response.content = "id_card"
            mock_instance.invoke_with_fallback.return_value = mock_response
            mock_llm.return_value = mock_instance
            
            result = classify_doc(sample_id_card_state)
            
            assert result["doc_type"] == "id_card"
            assert result["trace_log"][0]["output"] == "id_card"
    
    def test_classify_unknown_document(self, sample_invoice_state):
        """Test classification of unknown document type."""
        sample_invoice_state["raw_text"] = "Random unstructured text"
        
        with patch('app.agents.classifier.UnifiedLLMManager') as mock_llm:
            mock_instance = Mock()
            mock_response = Mock()
            mock_response.content = "other"
            mock_instance.invoke_with_fallback.return_value = mock_response
            mock_llm.return_value = mock_instance
            
            result = classify_doc(sample_invoice_state)
            
            assert result["doc_type"] == "other"
    
    def test_classifier_with_different_providers(self, sample_invoice_state):
        """Test classifier works with different LLM providers."""
        providers = ["ollama", "groq", "bedrock"]
        
        for provider in providers:
            sample_invoice_state["llm_provider"] = provider
            
            with patch('app.agents.classifier.UnifiedLLMManager') as mock_llm:
                mock_instance = Mock()
                mock_response = Mock()
                mock_response.content = "invoice"
                mock_instance.invoke_with_fallback.return_value = mock_response
                mock_llm.return_value = mock_instance
                
                result = classify_doc(sample_invoice_state)
                
                assert result["doc_type"] == "invoice"
                mock_llm.assert_called_with(provider=provider)


@pytest.mark.unit
class TestExtractorAgent:
    """Tests for the Extractor Agent."""
    
    def test_extract_invoice_data_success(self, sample_invoice_state):
        """Test successful invoice data extraction."""
        sample_invoice_state["doc_type"] = "invoice"
        
        with patch('app.agents.extractor.UnifiedLLMManager') as mock_llm:
            mock_instance = Mock()
            mock_response = Mock()
            mock_response.content = """{
                "invoice_number": "INV-2025-001",
                "vendor_name": "TechCorp Solutions",
                "total_amount": 5000.00,
                "date": "2025-01-15"
            }"""
            mock_instance.invoke_with_fallback.return_value = mock_response
            mock_llm.return_value = mock_instance
            
            result = extract_data(sample_invoice_state)
            
            assert result["extracted_data"] is not None
            assert "invoice_number" in result["extracted_data"]
            assert result["extracted_data"]["invoice_number"] == "INV-2025-001"
    
    def test_extract_id_card_data_success(self, sample_id_card_state):
        """Test successful ID card data extraction."""
        sample_id_card_state["doc_type"] = "id_card"
        
        with patch('app.agents.extractor.UnifiedLLMManager') as mock_llm:
            mock_instance = Mock()
            mock_response = Mock()
            mock_response.content = """{
                "full_name": "John Doe",
                "id_number": "ABC123456",
                "date_of_birth": "1990-01-01",
                "expiry_date": "2030-01-01"
            }"""
            mock_instance.invoke_with_fallback.return_value = mock_response
            mock_llm.return_value = mock_instance
            
            result = extract_data(sample_id_card_state)
            
            assert result["extracted_data"] is not None
            assert "full_name" in result["extracted_data"]
            assert result["extracted_data"]["full_name"] == "John Doe"
    
    def test_extract_malformed_json(self, sample_invoice_state):
        """Test extraction with malformed JSON response."""
        sample_invoice_state["doc_type"] = "invoice"
        
        with patch('app.agents.extractor.UnifiedLLMManager') as mock_llm:
            mock_instance = Mock()
            mock_response = Mock()
            mock_response.content = "Not a valid JSON"
            mock_instance.invoke_with_fallback.return_value = mock_response
            mock_llm.return_value = mock_instance
            
            result = extract_data(sample_invoice_state)
            
            # Should handle gracefully
            assert "extracted_data" in result


@pytest.mark.unit
class TestValidatorAgent:
    """Tests for the Validator Agent."""
    
    def test_validate_invoice_success(self, sample_invoice_state):
        """Test successful invoice validation."""
        sample_invoice_state["doc_type"] = "invoice"
        sample_invoice_state["extracted_data"] = {
            "invoice_number": "INV-2025-001",
            "vendor_name": "TechCorp Solutions",
            "total_amount": 5000.00,
            "date": "2025-01-15"
        }
        
        result = validate_data(sample_invoice_state)
        
        assert result["validated_data"] is not None
        assert len(result["errors"]) == 0
        assert result["trace_log"][-1]["status"] == "passed"
    
    def test_validate_missing_fields(self, sample_invoice_state):
        """Test validation with missing required fields."""
        sample_invoice_state["doc_type"] = "invoice"
        sample_invoice_state["extracted_data"] = {
            "invoice_number": "INV-2025-001",
            # Missing vendor_name, total_amount, date
        }
        
        result = validate_data(sample_invoice_state)
        
        assert len(result["errors"]) > 0
        assert result["trace_log"][-1]["status"] == "failed"
    
    def test_validate_invalid_data_types(self, sample_invoice_state):
        """Test validation with invalid data types."""
        sample_invoice_state["doc_type"] = "invoice"
        sample_invoice_state["extracted_data"] = {
            "invoice_number": "INV-2025-001",
            "vendor_name": "TechCorp",
            "total_amount": "not a number",  # Should be float
            "date": "2025-01-15"
        }
        
        result = validate_data(sample_invoice_state)
        
        assert len(result["errors"]) > 0


@pytest.mark.unit
class TestRedactorAgent:
    """Tests for the Redactor Agent."""
    
    def test_redact_pii_success(self, sample_invoice_state):
        """Test successful PII redaction."""
        sample_invoice_state["doc_type"] = "invoice"
        sample_invoice_state["raw_text"] = """
        John Doe
        john.doe@email.com
        +1-555-0123
        123 Main Street
        """
        
        with patch('app.agents.redactor.UnifiedLLMManager') as mock_llm:
            mock_instance = Mock()
            mock_response = Mock()
            mock_response.content = """
            [NAME_REDACTED]
            [EMAIL_REDACTED]
            [PHONE_REDACTED]
            [ADDRESS_REDACTED]
            """
            mock_instance.invoke_with_fallback.return_value = mock_response
            mock_llm.return_value = mock_instance
            
            result = redact_pii(sample_invoice_state)
            
            assert result["redacted_text"] is not None
            assert "[NAME_REDACTED]" in result["redacted_text"] or "[EMAIL_REDACTED]" in result["redacted_text"]
    
    def test_redact_email_regex(self, sample_invoice_state):
        """Test email redaction using regex."""
        sample_invoice_state["raw_text"] = "Contact: john.doe@example.com"
        
        with patch('app.agents.redactor.UnifiedLLMManager') as mock_llm:
            mock_instance = Mock()
            mock_response = Mock()
            mock_response.content = "Contact: john.doe@example.com"  # LLM didn't redact
            mock_instance.invoke_with_fallback.return_value = mock_response
            mock_llm.return_value = mock_instance
            
            result = redact_pii(sample_invoice_state)
            
            # Regex layer should catch it
            assert "[EMAIL_REDACTED]" in result["redacted_text"]


@pytest.mark.unit
class TestReporterAgent:
    """Tests for the Reporter Agent."""
    
    def test_generate_report_success(self, sample_invoice_state, clean_reports_dir):
        """Test successful report generation."""
        sample_invoice_state["doc_type"] = "invoice"
        sample_invoice_state["extracted_data"] = {
            "invoice_number": "INV-001",
            "vendor_name": "Test",
            "total_amount": 100.0,
            "date": "2025-01-01"
        }
        sample_invoice_state["validated_data"] = sample_invoice_state["extracted_data"]
        sample_invoice_state["redacted_text"] = "Redacted content"
        sample_invoice_state["trace_log"] = [
            {"agent": "classifier", "status": "completed"},
            {"agent": "extractor", "status": "success"},
            {"agent": "validator", "status": "passed"},
            {"agent": "redactor", "status": "completed"}
        ]
        
        result = generate_report(sample_invoice_state)
        
        assert len(result["trace_log"]) == 5  # Original 4 + reporter
        assert result["trace_log"][-1]["agent"] == "reporter"
        
        # Check report file was created
        import os
        reports = list(clean_reports_dir.glob("report_*.json"))
        assert len(reports) > 0
