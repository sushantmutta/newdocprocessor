import pytest
from unittest.mock import Mock, patch
from src.core.state import DocState
from src.core.agents.classifier import classify_doc
from src.core.agents.extractor import extract_data
from src.core.agents.validator import validate_data
from src.core.agents.redactor import redact_pii
from src.core.agents.reporter import generate_report
import json


@pytest.fixture
def mock_llm():
    # Patch the class in all modules where it's imported
    with patch('src.core.agents.classifier.UnifiedLLMManager') as m1, \
            patch('src.core.agents.extractor.UnifiedLLMManager') as m2, \
            patch('src.core.agents.redactor.UnifiedLLMManager') as m3, \
            patch('src.core.agents.repair.UnifiedLLMManager') as m4:
        mock_instance = Mock()
        # Ensure metadata values are strings to avoid JSON serialization errors
        mock_instance.provider_name = "groq"
        mock_instance.provider = "groq"
        mock_instance.model_name = "llama-3.1-8b-instant"
        m1.return_value = mock_instance
        m2.return_value = mock_instance
        m3.return_value = mock_instance
        m4.return_value = mock_instance
        yield mock_instance


@pytest.mark.integration
class TestE2EScenarios:

    def test_happy_path_prescription(self, mock_llm):
        """Standard prescription processing."""
        # 1. Mock Classifier
        mock_llm.invoke_with_fallback.side_effect = [
            Mock(content="PRESCRIPTION"),  # Classifier
            Mock(content=json.dumps({     # Extractor
                "document_type": "PRESCRIPTION",
                "confidence_score": 0.95,
                "data": {
                    "date": "2024-03-20",
                    "doctor": {"name": "Dr. Smith", "license_number": "MH-12345"},
                    "patient": {"name": "John Doe", "age": 45, "gender": "Male"},
                    "medications": [{"name": "Amoxicillin", "dosage": "500mg", "frequency": "BID", "duration": "7 days"}]
                }
            })),
            Mock(content="Pre-redacted text with [NAME_REDACTED]")  # Redactor
        ]

        state = DocState(
            raw_text="Rx: Amoxicillin for John Doe from Dr. Smith. License: MH-12345",
            file_path="prescription.txt",
            doc_type=None,
            extracted_data=None,
            validated_data=None,
            validation_flags=[],
            redacted_text=None,
            trace_log=[],
            errors=[],
            repair_attempts=0,
            repair_summary=None,
            llm_provider="groq",
            llm_model_name=None,
            confidence_score=0.0,
            start_time=None
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
        assert len(state["validation_flags"]) == 0  # Happy path

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

        state = DocState(
            raw_text="Rx: LupusMed 6000mg",
            file_path="lethal.txt",
            doc_type=None,
            extracted_data=None,
            validated_data=None,
            validation_flags=[],
            redacted_text=None,
            trace_log=[],
            errors=[],
            repair_attempts=0,
            repair_summary=None,
            llm_provider="groq",
            llm_model_name=None,
            confidence_score=0.0,
            start_time=None
        )
        state = classify_doc(state)
        state = extract_data(state)
        state = validate_data(state)

        flags = [f["code"] for f in state["validation_flags"]]
        assert "EXTREME_DOSAGE" in flags
        assert any(f["severity"] ==
                   "CRITICAL" for f in state["validation_flags"])

    def test_missing_fields_resilience(self, mock_llm):
        """Test how the pipeline handles partial extraction."""
        mock_llm.invoke_with_fallback.side_effect = [
            Mock(content="PRESCRIPTION"),  # Classifier
            Mock(content=json.dumps({     # Extractor (Missing doctor license)
                "document_type": "PRESCRIPTION",
                "confidence_score": 0.7,
                "data": {
                    "doctor": {"name": "Dr. Anonymous", "license_number": "null"},
                    "patient": {"name": "Jane Doe", "age": 30},
                    "medications": []
                }
            })),
            Mock(content="Redacted text")  # Redactor
        ]

        state = DocState(
            raw_text="Partial prescription text...",
            file_path="partial.txt",
            doc_type=None,
            extracted_data=None,
            validated_data=None,
            validation_flags=[],
            redacted_text=None,
            trace_log=[],
            errors=[],
            repair_attempts=0,
            repair_summary=None,
            llm_provider="groq",
            llm_model_name=None,
            confidence_score=0.0,
            start_time=None
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
                    "lab": {"name": "Emergency Lab", "has_pathologist_signature": True, "accreditation": "CLIA-123"},
                    "report_id": "LAB000001",
                    "collection_date": "2024-03-20",
                    "report_date": "2024-03-20",
                    "test_results": [{"test_name": "Potassium", "value": 7.2, "unit": "mmol/L", "reference_range": "3.5 - 5.0", "status": "CRITICAL"}]
                }
            })),
            Mock(content="Redacted")
        ]

        state = DocState(
            raw_text="K+ 7.2 CRITICAL",
            file_path="lab.txt",
            doc_type=None,
            extracted_data=None,
            validated_data=None,
            validation_flags=[],
            redacted_text=None,
            trace_log=[],
            errors=[],
            repair_attempts=0,
            repair_summary=None,
            llm_provider="groq",
            llm_model_name=None,
            confidence_score=0.0,
            start_time=None
        )
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
                Mock(content=doc_type),  # Classifier
                Mock(content=json.dumps({
                    "document_type": doc_type,
                    "confidence_score": 0.9,
                    "data": {"field": "value"}
                })),  # Extractor
                Mock(content="Redacted")  # Redactor
            ]

            state = DocState(
                raw_text=text,
                file_path="synth.txt",
                doc_type=None,
                extracted_data=None,
                validated_data=None,
                validation_flags=[],
                redacted_text=None,
                trace_log=[],
                errors=[],
                repair_attempts=0,
                repair_summary=None,
                llm_provider="groq",
                llm_model_name=None,
                confidence_score=0.0,
                start_time=None
            )
            state = classify_doc(state)
            assert state["doc_type"] == doc_type.lower()

            if doc_type in ["PRESCRIPTION", "LAB_REPORT"]:
                state = extract_data(state)
                # Validation might fail due to "field": "value" not matching schema, but we check pipeline completion
                state = validate_data(state)

            state = redact_pii(state)
            state = generate_report(state)
            assert state["trace_log"][-1]["status"] == "completed"

    def test_repair_agent_unit_correction(self, mock_llm):
        """Test repair agent fixing NON_STANDARD_UNIT errors."""
        # Step 1: Classification
        # Step 2: Extraction with bad units
        # Step 3: Validation flags NON_STANDARD_UNIT
        # Step 4: Repair corrects the unit
        mock_llm.invoke_with_fallback.side_effect = [
            Mock(content="PRESCRIPTION"),  # Classifier
            Mock(content=json.dumps({     # Extractor (with bad unit)
                "document_type": "PRESCRIPTION",
                "confidence_score": 0.92,
                "data": {
                    "doctor": {"name": "Dr. Johnson", "license_number": "CA-54321"},
                    "patient": {"name": "Alice Smith", "age": 35},
                    "medications": [{"name": "Aspirin", "dosage": "500 liters daily", "frequency": "once daily"}]
                }
            })),
            Mock(content=json.dumps({     # Repair agent (corrects to mg)
                "doctor": {"name": "Dr. Johnson", "license_number": "CA-54321"},
                "patient": {"name": "Alice Smith", "age": 35},
                "medications": [{"name": "Aspirin", "dosage": "500 mg", "frequency": "once daily"}]
            })),
            Mock(content="Redacted prescription")  # Redactor
        ]

        state = DocState(
            raw_text="Rx: Aspirin 500mg for Alice Smith from Dr. Johnson",
            file_path="repair_test.txt",
            doc_type=None,
            extracted_data=None,
            validated_data=None,
            validation_flags=[],
            redacted_text=None,
            trace_log=[],
            errors=[],
            repair_attempts=0,
            repair_summary=None,
            llm_provider="groq",
            llm_model_name=None,
            confidence_score=0.0,
            start_time=None
        )

        # Execute pipeline
        state = classify_doc(state)
        assert state["doc_type"] == "prescription"

        state = extract_data(state)
        assert state["extracted_data"]["medications"][0]["dosage"] == "500 liters daily"

        state = validate_data(state)
        # Should flag NON_STANDARD_UNIT or INVALID_DOSAGE_UNIT
        flags = [f["code"] for f in state["validation_flags"]]
        assert any(code in flags for code in [
                   "NON_STANDARD_UNIT", "INVALID_DOSAGE_UNIT"])

        # Import repair functions
        from src.core.agents.repair import repair_data, should_repair

        # Check if repair is needed
        assert should_repair(state) == "repair"

        # Execute repair
        state = repair_data(state)
        assert state["repair_attempts"] == 1
        assert state["repair_summary"] is not None

        # Re-validate after repair
        state = validate_data(state)
        # After repair, the unit should be fixed
        assert "mg" in state["extracted_data"]["medications"][0]["dosage"]

    def test_repair_max_attempts(self, mock_llm):
        """Test that repair agent aborts after max attempts."""
        from src.core.agents.repair import repair_data

        mock_llm.invoke_with_fallback.return_value = Mock(
            content=json.dumps({
                "medications": [{"name": "Drug", "dosage": "bad unit"}]
            })
        )

        state = DocState(
            raw_text="Test doc",
            file_path="test.txt",
            doc_type="prescription",
            extracted_data={"medications": [
                {"name": "Drug", "dosage": "500 liters"}]},
            validated_data=None,
            validation_flags=[
                {"code": "NON_STANDARD_UNIT", "severity": "MEDIUM"}],
            repair_flag_attempts={"NON_STANDARD_UNIT": 3},
            redacted_text=None,
            trace_log=[],
            errors=[],
            repair_attempts=3,  # Already at max
            repair_summary=None,
            llm_provider="groq",
            llm_model_name=None,
            confidence_score=0.0,
            start_time=None
        )

        # Should skip repair due to per-flag max attempts exhaustion
        state = repair_data(state)
        assert any(log.get("action") == "skip" for log in state["trace_log"])

    def test_no_repair_needed(self, mock_llm):
        """Test that repair is skipped when no unit errors exist."""
        from src.core.agents.repair import repair_data, should_repair

        state = DocState(
            raw_text="Test doc",
            file_path="test.txt",
            doc_type="prescription",
            extracted_data={
                "doctor": {"name": "Dr. Test"},
                "medications": [{"name": "Aspirin", "dosage": "500 mg"}]
            },
            validated_data=None,
            validation_flags=[
                {"code": "MISSING_PATIENT_ID", "severity": "LOW"}],
            redacted_text=None,
            trace_log=[],
            errors=[],
            repair_attempts=0,
            repair_summary=None,
            llm_provider="groq",
            llm_model_name=None,
            confidence_score=0.0,
            start_time=None
        )

        # Should route to redactor, not repair
        assert should_repair(state) == "redactor"

        # If repair is called anyway, it should skip
        state = repair_data(state)
        assert any(log.get("action") == "skip" for log in state["trace_log"])
