import pytest
from unittest.mock import Mock, patch
from src.core.agents.classifier import classify_doc
from src.core.agents.validator import validate_data
from src.core.state import DocState


@pytest.fixture
def mock_llm():
    with patch('src.core.agents.classifier.UnifiedLLMManager') as mock:
        yield mock


class TestClassifierAgent:
    def test_classify_prescription(self, mock_llm):
        # Setup mock return
        mock_instance = Mock()
        mock_response = Mock()
        mock_response.content = "prescription"
        mock_instance.invoke_with_fallback.return_value = mock_response
        mock_llm.return_value = mock_instance

        state = DocState(raw_text="Rx: Amoxicillin 500mg...", trace_log=[])
        result = classify_doc(state)

        assert result["doc_type"] == "prescription"

    def test_classify_lab_report(self, mock_llm):
        # Setup mock return
        mock_instance = Mock()
        mock_response = Mock()
        mock_response.content = "lab_report"
        mock_instance.invoke_with_fallback.return_value = mock_response
        mock_llm.return_value = mock_instance

        state = DocState(raw_text="Test Results: Hemoglobin...", trace_log=[])
        result = classify_doc(state)

        assert result["doc_type"] == "lab_report"


class TestValidatorAgent:
    def test_validate_prescription_flags(self):
        # Test that validator correctly generates flags for a prescription with issues
        data = {
            "doctor": {"name": "Dr. House", "license_number": "MD00"},
            "patient": {"name": "Kid", "age": 5},  # Pediatric
            "medications": [
                {"name": "Morphine", "dosage": "5mg",
                    "frequency": "QD"}  # Controlled
            ],
            "date": "2024-03-15"
        }
        state = DocState(
            doc_type="prescription",
            extracted_data=data,
            errors=[],
            trace_log=[]
        )

        result = validate_data(state)

        assert "validation_flags" in result
        flags = result["validation_flags"]

        # Should have 2 flags: Pediatric and Controlled Substance
        codes = [f["code"] for f in flags]
        assert "PEDIATRIC_DOSING" in codes
        assert "CONTROLLED_SUBSTANCE_NO_DEA" in codes

        # Verify severity
        for f in flags:
            if f["code"] == "CONTROLLED_SUBSTANCE_NO_DEA":
                assert f["severity"] == "CRITICAL"

    def test_validate_lab_critical(self):
        data = {
            "lab": {"name": "Lab", "has_pathologist_signature": True, "accreditation": "CLIA-123"},
            "report_id": "1",
            "collection_date": "2024-03-14",
            "report_date": "2024-03-15",
            "sample_type": "Whole Blood",  # Added to prevent MISSING_SAMPLE_TYPE flag
            "test_results": [
                {"test_name": "Hgb", "value": 5.0,
                    "unit": "g/dL", "status": "Critical",
                    "reference_range": "13.5-17.5 g/dL"}  # Added to prevent MISSING_REFERENCE_RANGE flag
            ]
        }
        state = DocState(
            doc_type="lab_report",
            extracted_data=data,
            errors=[],
            trace_log=[]
        )

        result = validate_data(state)

        # Should get 2 flags: CRITICAL_VALUE (from status) + OUT_OF_RANGE_LOW (from range check)
        assert len(result["validation_flags"]) == 2

        # Verify CRITICAL_VALUE flag exists
        critical_flags = [f for f in result["validation_flags"]
                          if f["code"] == "CRITICAL_VALUE"]
        assert len(critical_flags) == 1
        assert critical_flags[0]["severity"] == "CRITICAL"

        # Verify OUT_OF_RANGE_LOW flag exists
        range_flags = [f for f in result["validation_flags"]
                       if f["code"] == "OUT_OF_RANGE_LOW"]
        assert len(range_flags) == 1
        assert range_flags[0]["severity"] == "CRITICAL"
