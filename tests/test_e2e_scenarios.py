import pytest
from unittest.mock import Mock, patch
from app.state import DocState
from app.agents.classifier import classify_doc
from app.agents.extractor import extract_data
from app.agents.validator import validate_data
from app.agents.redactor import redact_pii
from app.agents.reporter import generate_report
import json

@pytest.fixture
def mock_llm():
    # Patch the class in all modules where it's imported
    with patch('app.agents.classifier.UnifiedLLMManager') as m1, \
         patch('app.agents.extractor.UnifiedLLMManager') as m2, \
         patch('app.agents.redactor.UnifiedLLMManager') as m3:
        mock_instance = Mock()
        # Ensure metadata values are strings to avoid JSON serialization errors
        mock_instance.provider_name = "groq"
        mock_instance.provider = "groq"
        mock_instance.model_name = "llama-3.1-8b-instant"
        m1.return_value = mock_instance
        m2.return_value = mock_instance
        m3.return_value = mock_instance
        yield mock_instance

@pytest.mark.integration
class TestE2EScenarios:
    
    def test_happy_path_prescription(self, mock_llm):
        """Standard prescription processing."""
        # 1. Mock Classifier
        mock_llm.invoke_with_fallback.side_effect = [
            Mock(content="PRESCRIPTION"), # Classifier
            Mock(content=json.dumps({     # Extractor
                "document_type": "PRESCRIPTION",
                "confidence_score": 0.95,
                "data": {
                    "doctor": {"name": "Dr. Smith", "license_number": "MH-12345"},
                    "patient": {"name": "John Doe", "age": 45, "gender": "Male"},
                    "medications": [{"name": "Amoxicillin", "dosage": "500mg", "frequency": "BID", "duration": "7 days"}]
                }
            })),
            Mock(content="Pre-redacted text with [NAME_REDACTED]") # Redactor
        ]
        
        state = DocState(
            raw_text="Rx: Amoxicillin for John Doe from Dr. Smith. License: MH-12345",
            file_path="prescription.txt",
            trace_log=[],
            errors=[],
            llm_provider="groq"
        )
        
        # Step 1: Classify
        state = classify_doc(state)
        assert state["doc_type"] == "prescription"
        
        # Step 2: Extract
        state = extract_data(state)
        assert state["extracted_data"]["doctor"]["name"] == "Dr. Smith"
        assert state["confidence_score"] == 0.95
        
        # Step 3: Validate
        state = validate_data(state)
        assert len(state["validation_flags"]) == 0 # Happy path
        
        # Step 4: Redact
        state = redact_pii(state)
        assert "redacted_text" in state
        
        # Step 5: Report
        state = generate_report(state)
        assert state["trace_log"][-1]["agent"] == "reporter"

    def test_extreme_dosage_alert(self, mock_llm):
        """Verify LIFE THREATENING alert for extreme dosage."""
        mock_llm.invoke_with_fallback.side_effect = [
            Mock(content="PRESCRIPTION"),
            Mock(content=json.dumps({
                "document_type": "PRESCRIPTION",
                "confidence_score": 0.98,
                "data": {
                    "doctor": {"name": "Dr. House", "license_number": "NJ-99999"},
                    "patient": {"name": "Poor Patient", "age": 30},
                    "medications": [{"name": "LupusMed", "dosage": "6000mg"}]
                }
            })),
            Mock(content="Redacted")
        ]
        
        state = DocState(raw_text="Rx: LupusMed 6000mg", file_path="lethal.txt", trace_log=[], errors=[], llm_provider="groq")
        state = classify_doc(state)
        state = extract_data(state)
        state = validate_data(state)
        
        flags = [f["code"] for f in state["validation_flags"]]
        assert "EXTREME_DOSAGE" in flags
        assert any(f["severity"] == "CRITICAL" for f in state["validation_flags"])

    def test_missing_fields_resilience(self, mock_llm):
        """Test how the pipeline handles partial extraction."""
        mock_llm.invoke_with_fallback.side_effect = [
            Mock(content="PRESCRIPTION"), # Classifier
            Mock(content=json.dumps({     # Extractor (Missing doctor license)
                "document_type": "PRESCRIPTION",
                "confidence_score": 0.7,
                "data": {
                    "doctor": {"name": "Dr. Anonymous", "license_number": "null"},
                    "patient": {"name": "Jane Doe", "age": 30},
                    "medications": []
                }
            })),
            Mock(content="Redacted text") # Redactor
        ]
        
        state = DocState(
            raw_text="Partial prescription text...",
            file_path="partial.txt",
            trace_log=[],
            errors=[],
            llm_provider="groq"
        )
        
        state = classify_doc(state)
        state = extract_data(state)
        state = validate_data(state)
        
        flags = [f["code"] for f in state["validation_flags"]]
        assert "MISSING_DOCTOR_LICENSE" in flags
        
        state = redact_pii(state)
        state = generate_report(state)
        assert state["trace_log"][-1]["status"] == "completed"

    def test_critical_lab_value(self, mock_llm):
        """Verify lab report critical value flagging."""
        mock_llm.invoke_with_fallback.side_effect = [
            Mock(content="LAB_REPORT"),
            Mock(content=json.dumps({
                "document_type": "LAB_REPORT",
                "confidence_score": 0.99,
                "data": {
                    "lab": {"name": "Emergency Lab", "report_id": "LAB000001"},
                    "dates": {"collection_date": "2024-03-20", "report_date": "2024-03-20"},
                    "test_results": [{"test_name": "Potassium", "value": 7.2, "unit": "mmol/L", "reference_range": "3.5 - 5.0", "status": "CRITICAL"}]
                }
            })),
            Mock(content="Redacted")
        ]
        
        state = DocState(raw_text="K+ 7.2 CRITICAL", file_path="lab.txt", trace_log=[], errors=[], llm_provider="groq")
        state = classify_doc(state)
        state = extract_data(state)
        state = validate_data(state)
        
        flags = [f["code"] for f in state["validation_flags"]]
        assert "CRITICAL_VALUE" in flags

    def test_synthetic_sample_set(self, mock_llm):
        """Verify overall flow for multiple synthetic doc types."""
        samples = [
            ("PRESCRIPTION", "Rx: Aspirin 100mg"),
            ("LAB_REPORT", "Lab Result: WBC 5000/uL"),
            ("UNKNOWN", "Random text")
        ]
        
        for doc_type, text in samples:
            mock_llm.invoke_with_fallback.side_effect = [
                Mock(content=doc_type), # Classifier
                Mock(content=json.dumps({
                    "document_type": doc_type,
                    "confidence_score": 0.9,
                    "data": {"field": "value"}
                })), # Extractor
                Mock(content="Redacted") # Redactor
            ]
            
            state = DocState(raw_text=text, file_path="synth.txt", trace_log=[], errors=[], llm_provider="groq")
            state = classify_doc(state)
            assert state["doc_type"] == doc_type.lower()
            
            if doc_type in ["PRESCRIPTION", "LAB_REPORT"]:
                state = extract_data(state)
                # Validation might fail due to "field": "value" not matching schema, but we check pipeline completion
                state = validate_data(state)
            
            state = redact_pii(state)
            state = generate_report(state)
            assert state["trace_log"][-1]["status"] == "completed"
