import asyncio
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from src.api.main import api
import src.api.main as api_main


class _FakeSnapshot:
    def __init__(self, next_nodes=None, values=None):
        self.next = next_nodes or []
        self.values = values or {}


class _FakeGraph:
    def __init__(self):
        self.state = {
            "doc_type": "prescription",
            "validated_data": {"doctor": {"name": "Dr Test"}},
            "extracted_data": {"doctor": {"name": "Dr Test"}},
            "validation_flags": [],
            "review_required": True,
            "review_reason": ["manual review requested"],
            "trace_log": [],
            "trace_events": [
                {
                    "thread_id": "thread_test",
                    "correlation_id": "thread_test",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "agent": "supervisor",
                    "action": "human_review",
                    "status": "success",
                    "input_hash": "a",
                    "output_hash": "b",
                    "model": None,
                    "fallback_used": False,
                    "duration_ms": 1.0,
                    "metadata_json": "{}",
                }
            ],
            "trace_correlation_id": "thread_test",
            "repair_attempts": 0,
            "errors": [],
            "repair_summary": {"reasoning": "manual review requested"},
            "paused_since": datetime.now(timezone.utc).isoformat(),
            "review_deadline": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            "responsible_ai_log": [],
        }

    def get_state(self, _config):
        if self.state.get("review_required"):
            return _FakeSnapshot(next_nodes=["human_review"], values=self.state)
        return _FakeSnapshot(next_nodes=[], values=self.state)

    def update_state(self, _config, state):
        self.state = state

    def invoke(self, _state, _config):
        decision = str(self.state.get("human_decision") or "approve")
        if decision == "re_extract":
            self.state["review_required"] = True
            self.state["review_reason"] = ["manual review requested"]
        elif decision == "escalate":
            self.state["review_required"] = True
        else:
            self.state["review_required"] = False
            self.state["review_reason"] = []
        return self.state


client = TestClient(api)


def test_decision_branches_and_audit_trace_endpoints(monkeypatch):
    fake_graph = _FakeGraph()
    monkeypatch.setattr(
        "src.api.main.langgraph_pipeline_with_review", fake_graph)

    thread_id = "thread_test"
    decisions = ["approve", "reject", "override", "re_extract", "escalate"]

    for decision in decisions:
        payload = {
            "decision": decision,
            "modified_data": {"doctor": {"name": "Dr Human"}} if decision == "override" else None,
            "hint_prompt": "extract again" if decision == "re_extract" else None,
            "reviewer_id": "qa-user",
            "reviewer_notes": f"decision={decision}",
        }
        resp = client.post(f"/review/{thread_id}/decision", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["thread_id"] == thread_id
        if decision == "escalate":
            assert body["status"] == "escalated"
        elif decision == "re_extract":
            assert body["status"] in {"interrupted", "completed"}
        else:
            assert body["status"] in {"completed", "interrupted"}

    trace_resp = client.get(f"/trace/{thread_id}")
    assert trace_resp.status_code == 200
    assert isinstance(trace_resp.json(), list)

    audit_resp = client.get(f"/audit/{thread_id}")
    assert audit_resp.status_code == 200
    audit_items = audit_resp.json()
    assert isinstance(audit_items, list)
    assert any(item.get("action") in decisions for item in audit_items)


class _FakeRows:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _FakeConn:
    def __init__(self, rows):
        self.rows = rows
        self.row_factory = None

    def execute(self, _query, _params=None):
        return _FakeRows(self.rows)

    def commit(self):
        return None

    def close(self):
        return None


class _ProcCfg:
    def __init__(self, timeout_action):
        self.review_poll_interval_seconds = 1
        self.timeout_action = timeout_action


class _Settings:
    def __init__(self, timeout_action):
        self.processing = _ProcCfg(timeout_action)


def test_timeout_worker_auto_approve_edge(monkeypatch):
    now = datetime.now(timezone.utc)
    rows = [{"thread_id": "t_auto", "review_deadline": (
        now - timedelta(minutes=5)).isoformat()}]

    monkeypatch.setattr("src.api.main.get_settings",
                        lambda: _Settings("auto_approve"))
    monkeypatch.setattr("src.api.main._connect_db", lambda: _FakeConn(rows))

    called = {"count": 0}

    def _fake_apply_decision(*_args, **_kwargs):
        called["count"] += 1
        return {}

    monkeypatch.setattr("src.api.main._apply_decision", _fake_apply_decision)

    async def _stop_sleep(_interval):
        raise RuntimeError("stop-loop")

    monkeypatch.setattr("src.api.main.asyncio.sleep", _stop_sleep)

    try:
        asyncio.run(api_main._timeout_worker())
    except RuntimeError as exc:
        assert "stop-loop" in str(exc)

    assert called["count"] == 1


def test_timeout_worker_escalate_edge(monkeypatch):
    now = datetime.now(timezone.utc)
    rows = [{"thread_id": "t_escalate", "review_deadline": (
        now - timedelta(minutes=5)).isoformat()}]

    monkeypatch.setattr("src.api.main.get_settings",
                        lambda: _Settings("escalate"))
    monkeypatch.setattr("src.api.main._connect_db", lambda: _FakeConn(rows))

    fake_graph = _FakeGraph()
    monkeypatch.setattr(
        "src.api.main.langgraph_pipeline_with_review", fake_graph)

    async def _stop_sleep(_interval):
        raise RuntimeError("stop-loop")

    monkeypatch.setattr("src.api.main.asyncio.sleep", _stop_sleep)

    try:
        asyncio.run(api_main._timeout_worker())
    except RuntimeError as exc:
        assert "stop-loop" in str(exc)

    assert fake_graph.state.get("escalated") is True
