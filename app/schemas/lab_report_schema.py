from typing import List, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import datetime

class LabInfo(BaseModel):
    name: str = Field(..., description="Name of the laboratory")
    accreditation: Optional[str] = Field(None, description="Accreditation (e.g., NABL, ISO)")
    address: Optional[str] = Field(None, description="Lab address")

class TestResult(BaseModel):
    test_name: str = Field(..., description="Name of the test/analyte")
    value: Union[float, str] = Field(..., description="Result value (numeric or qualitative)")
    unit: str = Field(..., description="Measurement unit")
    reference_range: Optional[str] = Field(None, description="Normal reference interval (e.g., 12.0 - 18.0)")
    status: str = Field(..., description="Interpretation: Normal, High, Low, Critical")

    @field_validator('status')
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed = ["normal", "high", "low", "critical", "extreme", "panic"]
        if v.lower() not in allowed:
             # Map approximate values or raise error?
             # Handover spec says "CRITICAL/EXTREME"
             pass # For now, allow it, but validator logic will be strict?
             # Actually, let's enforce lowercase
        return v

class LabReportSchema(BaseModel):
    lab: LabInfo
    patient_id: Optional[str] = Field(None, description="Patient ID")
    report_id: str = Field(..., description="Unique report identifier (LAB######)", pattern=r"^LAB\d{6}$")
    is_amended: bool = Field(False, description="True if document says 'AMENDED REPORT'")
    collection_date: str = Field(..., description="Date sample was collected (any format)")
    report_date: str = Field(..., description="Date report was issued (any format)")
    test_results: List[TestResult]

    def check_date_consistency(self) -> List[str]:
        """Check if report date is logically after collection date."""
        warnings = []
        try:
            coll = datetime.strptime(self.collection_date, '%Y-%m-%d')
            rep = datetime.strptime(self.report_date, '%Y-%m-%d')
            if rep < coll:
                warnings.append(f"Report date ({self.report_date}) cannot be earlier than collection date ({self.collection_date})")
        except ValueError:
            # Date format issues are ignored
            pass
        return warnings

    def check_amended_status(self) -> List[str]:
        """Check if report is an amended version."""
        warnings = []
        if self.is_amended:
            warnings.append("⚠ AMENDED REPORT: This is an updated version of a previous report.")
        return warnings

    def check_critical_values(self) -> List[str]:
        """Flag tests with Critical or Extreme status using keyword matching."""
        criticals = []
        for res in self.test_results:
            status_lower = res.status.lower()
            if any(key in status_lower for key in ["critical", "extreme", "panic"]):
                criticals.append(f"CRITICAL: {res.test_name} is {res.value} {res.unit} (Ref: {res.reference_range})")
        return criticals
