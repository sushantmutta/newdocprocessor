from fastapi.testclient import TestClient

from src.api.main import api


class _FakePage:
    def extract_text(self):
        return "PRESCRIPTION\nDoctor: Dr Test\nPatient: Jane Doe"


class _FakePdfReader:
    def __init__(self, *_args, **_kwargs):
        self.pages = [_FakePage()]


class _FakeStateSnapshot:
    def __init__(self, next_nodes=None, values=None):
        self.next = next_nodes or []
        self.values = values or {}


class _FakeReviewGraphInterrupted:
    def invoke(self, _state, _config):
        return {
            "doc_type": "prescription",
            "validation_flags": [{"code": "EXTREME_DOSAGE", "severity": "CRITICAL"}],
            "repair_attempts": 0,
            "review_required": True,
            "review_reason": "critical validation flags",
            "supervisor_decision": "human_review",
            "repair_summary": {
                "reasoning": "critical validation flags",
                "flags_repaired": [{"code": "EXTREME_DOSAGE", "severity": "CRITICAL"}],
                "original_data": {"medications": []},
                "repaired_data": {"medications": []},
            },
        }

    def get_state(self, _config):
        return _FakeStateSnapshot(next_nodes=["human_review"], values={})


class _FakeReviewGraphCompleted:
    def invoke(self, _state, _config):
        return {
            "doc_type": "prescription",
            "validated_data": {"doctor": {"name": "Dr Test"}},
            "validation_flags": [],
            "review_required": False,
            "review_reason": None,
            "supervisor_decision": "redactor",
        }

    def get_state(self, _config):
        return _FakeStateSnapshot(next_nodes=[], values={})


client = TestClient(api)


def _multipart_file():
    return {"file": ("sample.pdf", b"%PDF-1.4 fake", "application/pdf")}


def test_process_with_review_interrupted_at_human_review(monkeypatch):
    monkeypatch.setattr("src.api.main.PdfReader", _FakePdfReader)
    monkeypatch.setattr(
        "src.api.main.langgraph_pipeline_with_review", _FakeReviewGraphInterrupted()
    )

    response = client.post(
        "/process/with-review?llm_provider=groq", files=_multipart_file())
    assert response.status_code == 200

    payload = response.json()
    assert payload["status"] == "interrupted"
    assert payload["interrupted_at"] == "human_review"
    assert payload["current_state"]["review_reason"] == "critical validation flags"
    assert payload["current_state"]["supervisor_decision"] == "human_review"


def test_process_with_review_completed_without_interrupt(monkeypatch):
    monkeypatch.setattr("src.api.main.PdfReader", _FakePdfReader)
    monkeypatch.setattr(
        "src.api.main.langgraph_pipeline_with_review", _FakeReviewGraphCompleted()
    )

    response = client.post(
        "/process/with-review?llm_provider=groq", files=_multipart_file())
    assert response.status_code == 200

    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["interrupted_at"] is None
    assert payload["current_state"]["supervisor_decision"] == "redactor"
