import pytest
import os
import csv
import json
from app.agents.reporter import generate_report
from app.state import DocState

class TestReporterAgent:
    def test_generate_csv_metrics(self, tmp_path):
        # Create a mock report directory
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        reports_dir = os.path.join(base_dir, "reports")
        os.makedirs(reports_dir, exist_ok=True)
        csv_path = os.path.join(reports_dir, "metrics_report.csv")
        
        # Clean up previous csv if exists
        if os.path.exists(csv_path):
            os.remove(csv_path)
            
        state = DocState(
            doc_type="prescription",
            file_path="test_rx.pdf",
            extracted_data={"doctor": "Dr. House"},
            validated_data={"doctor": "Dr. House"},
            errors=[],
            trace_log=[],
            redacted_text="[REDACTED]",
            raw_text="Dr. House wrote a script.",
            repair_attempts=0
        )
        
        new_state = generate_report(state)
        
        assert os.path.exists(csv_path)
        
        with open(csv_path, "r", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 1
            assert rows[0]["doc_type"] == "prescription"
            assert rows[0]["file_path"] == "test_rx.pdf"

    def test_generate_json_trace(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        reports_dir = os.path.join(base_dir, "reports")
        
        state = DocState(
            doc_type="lab_report",
            file_path="test_lab.pdf",
            extracted_data={"test": "WBC"},
            validated_data={"test": "WBC"},
            errors=["Some error"],
            trace_log=[{"agent": "classifier", "output": "lab_report"}],
            redacted_text="",
            raw_text="Lab report content",
            repair_attempts=0
        )
        
        new_state = generate_report(state)
        
        # Verify JSON file creation
        # Since filename has timestamp, we check directory for recent file
        files = os.listdir(reports_dir)
        json_files = [f for f in files if f.startswith("trace_lab_report_") and f.endswith(".json")]
        assert len(json_files) > 0
