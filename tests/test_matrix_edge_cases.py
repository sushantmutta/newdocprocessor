import pytest
from unittest.mock import Mock, patch
from src.core.state import DocState
from src.core.agents.classifier import classify_doc
from src.core.agents.extractor import extract_data
from src.core.agents.validator import validate_data
import json


@pytest.fixture
def mock_llm():
    with patch('src.core.agents.classifier.UnifiedLLMManager') as m1, \
            patch('src.core.agents.extractor.UnifiedLLMManager') as m2:
        mock_instance = Mock()
        mock_instance.provider = "groq"
        m1.return_value = mock_instance
        m2.return_value = mock_instance
        yield mock_instance


@pytest.mark.integration
class TestMatrixEdgeCases:

    def test_geriatric_polypharmacy_risk(self, mock_llm):
        """Verify polypharmacy flag for elderly patients with many meds."""
        mock_llm.invoke_with_fallback.side_effect = [
            Mock(content="PRESCRIPTION"),
            Mock(content=json.dumps({
                "document_type": "PRESCRIPTION",
                "confidence_score": 0.95,
                "data": {
                    "doctor": {"name": "Dr. Grant", "license_number": "MD-12345"},
                    "patient": {"name": "Elderly Patient", "age": 72},
                    "medications": [
                        {"name": "Med A", "dosage": "10mg"},
                        {"name": "Med B", "dosage": "20mg"},
                        {"name": "Med C", "dosage": "30mg"},
                        {"name": "Med D", "dosage": "40mg"},
                        {"name": "Med E", "dosage": "50mg"},
                        {"name": "Med F", "dosage": "60mg"}
                    ]
                }
            }))
        ]
        state = DocState(raw_text="Geriatric 6 meds", file_path="geriatric.txt", trace_log=[
        ], errors=[], llm_provider="groq")
        state = classify_doc(state)
        state = extract_data(state)
        state = validate_data(state)
        flags = [f["code"] for f in state["validation_flags"]]
        assert "GERIATRIC_POLYPHARMACY_RISK" in flags

    def test_pathologist_signature_missing(self, mock_llm):
        """Verify flag when lab report lacks pathologist signature."""
        mock_llm.invoke_with_fallback.side_effect = [
            Mock(content="LAB_REPORT"),
            Mock(content=json.dumps({
                "document_type": "LAB_REPORT",
                "confidence_score": 0.9,
                "data": {
                    "lab": {"name": "No Sign Lab", "has_pathologist_signature": False},
                    "collection_date": "2024-03-20",
                    "report_date": "2024-03-21",
                    "test_results": [{"test_name": "Test", "value": 5.0}]
                }
            }))
        ]
        state = DocState(raw_text="Lab report without signature",
                         file_path="nosig.txt", trace_log=[], errors=[], llm_provider="groq")
        state = classify_doc(state)
        state = extract_data(state)
        state = validate_data(state)
        flags = [f["code"] for f in state["validation_flags"]]
        assert "MISSING_PATHOLOGIST_SIGNATURE" in flags

    def test_pending_lab_results_graceful(self, mock_llm):
        """Verify 'Pending' results don't trigger numeric errors."""
        mock_llm.invoke_with_fallback.side_effect = [
            Mock(content="LAB_REPORT"),
            Mock(content=json.dumps({
                "document_type": "LAB_REPORT",
                "confidence_score": 0.95,
                "data": {
                    "lab": {"name": "Future Lab", "has_pathologist_signature": True, "accreditation": "CLIA-123"},
                    "collection_date": "2024-03-20",
                    "report_date": "2024-03-21",
                    "test_results": [{"test_name": "Culture", "value": "Pending"}]
                }
            }))
        ]
        state = DocState(raw_text="Culture: Pending", file_path="pending.txt", trace_log=[
        ], errors=[], llm_provider="groq")
        state = classify_doc(state)
        state = extract_data(state)
        state = validate_data(state)
        flags = [f["code"] for f in state["validation_flags"]]
        assert "EXTREME_VALUES" not in flags
        assert len(state["errors"]) == 0

    def test_non_standard_unit_warning(self, mock_llm):
        """Verify warning for non-standard medical units in prescription."""
        mock_llm.invoke_with_fallback.side_effect = [
            Mock(content="PRESCRIPTION"),
            Mock(content=json.dumps({
                "document_type": "PRESCRIPTION",
                "confidence_score": 0.95,
                "data": {
                    "doctor": {"name": "Dr. Test", "license_number": "MD-12345"},
                    "patient": {"name": "Test Patient", "age": 30},
                    "medications": [{"name": "Liquid Med", "dosage": "2 Liters"}]
                }
            }))
        ]
        state = DocState(raw_text="Rx: Liquid Med 2 Liters", file_path="unit.txt", trace_log=[
        ], errors=[], llm_provider="groq")
        state = classify_doc(state)
        state = extract_data(state)
        state = validate_data(state)
        flags = [f["code"] for f in state["validation_flags"]]
        # Validator may emit either high-level medication error or specific unit error.
        assert (
            "INVALID_MEDICATIONS" in flags
            or "NON_STANDARD_UNIT" in flags
            or "INVALID_DOSAGE_UNIT" in flags
        )

    def test_missing_dosage_alert(self, mock_llm):
        """Verify alert for missing medication dosage."""
        mock_llm.invoke_with_fallback.side_effect = [
            Mock(content="PRESCRIPTION"),
            Mock(content=json.dumps({
                "document_type": "PRESCRIPTION",
                "confidence_score": 0.9,
                "data": {
                    "doctor": {"name": "Dr. Test", "license_number": "MD-12345"},
                    "patient": {"name": "Test Patient", "age": 30},
                    "medications": [{"name": "Missing Dose Med", "dosage": ""}]
                }
            }))
        ]
        state = DocState(raw_text="Rx: Missing Dose Med", file_path="missing_dose.txt", trace_log=[
        ], errors=[], llm_provider="groq")
        state = validate_data(extract_data(classify_doc(state)))
        flags = [f["code"] for f in state["validation_flags"]]
        assert "MISSING_DOSAGE" in flags

    def test_missing_lab_license_alert(self, mock_llm):
        """Verify alert for missing lab accreditation."""
        mock_llm.invoke_with_fallback.side_effect = [
            Mock(content="LAB_REPORT"),
            Mock(content=json.dumps({
                "document_type": "LAB_REPORT",
                "confidence_score": 0.95,
                "data": {
                    "lab": {"name": "No License Lab", "accreditation": ""},
                    "collection_date": "2024-03-20",
                    "report_date": "2024-03-21",
                    "test_results": [{"test_name": "Test", "value": 5.0}]
                }
            }))
        ]
        state = DocState(raw_text="Lab report without accreditation",
                         file_path="nolicense.txt", trace_log=[], errors=[], llm_provider="groq")
        state = validate_data(extract_data(classify_doc(state)))
        flags = [f["code"] for f in state["validation_flags"]]
        assert "MISSING_LAB_LICENSE" in flags
