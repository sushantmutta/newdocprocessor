from typing import List, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import datetime
import re

class LabInfo(BaseModel):
    name: Optional[str] = Field(None, description="Name of the laboratory")
    accreditation: Optional[str] = Field(None, description="Lab accreditation (e.g., CLIA)")
    address: Optional[str] = Field(None, description="Lab address")
    has_pathologist_signature: bool = Field(False, description="Whether a digital or physical signature is present")

class TestResult(BaseModel):
    test_name: Optional[str] = Field(None, description="Name of the test/analyte")
    value: Optional[Union[float, str]] = Field(None, description="Result value")
    unit: Optional[str] = Field(None, description="Measurement unit")
    reference_range: Optional[str] = Field(None, description="Normal reference interval (e.g., 12.0 - 18.0)")
    status: Optional[str] = Field(None, description="Interpretation: Normal, High, Low, Critical")

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

class DatesInfo(BaseModel):
    collection_date: Optional[str] = Field(None, description="Date sample collected (any format)")
    report_date: Optional[str] = Field(None, description="Date report issued (any format)")

class LabReportSchema(BaseModel):
    lab: LabInfo = Field(default_factory=LabInfo)
    report_id: Optional[str] = Field(None, description="Unique report identifier (LAB######)")
    dates: DatesInfo = Field(default_factory=DatesInfo)
    test_results: List[TestResult] = Field(default_factory=list)
    is_amended: bool = Field(False, description="Whether this is a corrected or amended report")

    def check_date_consistency(self) -> List[dict]:
        """Check if report date is logically after collection date."""
        flags = []
        
        def parse_any_date(date_str: Optional[str]) -> Optional[datetime]:
            if not date_str:
                return None
            # Common formats to try
            formats = ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d', '%b %d, %Y', '%d %b %Y']
            for fmt in formats:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
            return None

        coll = parse_any_date(self.dates.collection_date)
        rep = parse_any_date(self.dates.report_date)
        
        if coll and rep and rep < coll:
            flags.append({
                "code": "DATE_INCONSISTENCY",
                "message": f"Logical Contradiction: Report date ({self.dates.report_date}) earlier than collection ({self.dates.collection_date}).",
                "severity": "MEDIUM"
            })
        return flags

    def check_amended_status(self) -> List[dict]:
        """Check if report is an amended version."""
        flags = []
        if self.is_amended:
            flags.append({
                "code": "AMENDED_REPORT",
                "message": "Corrected Version: This is an amended report of a previous result.",
                "severity": "LOW"
            })
        return flags

    def check_critical_values(self) -> List[dict]:
        """Flag tests in Red/Panic range as IMMEDIATE ALERT."""
        flags = []
        for res in self.test_results:
            status_lower = res.status.lower() if res.status else ""
            if any(key in status_lower for key in ["critical", "panic", "immediate"]):
                flags.append({
                    "code": "CRITICAL_VALUE",
                    "message": f"IMMEDIATE ALERT: {res.test_name} is in critical range ({res.value}).",
                    "severity": "CRITICAL"
                })
        return flags

    def check_pathologist_signature(self) -> List[dict]:
        """Flag missing pathologist signature for liability."""
        flags = []
        if not self.lab.has_pathologist_signature:
            flags.append({
                "code": "MISSING_PATHOLOGIST_SIGNATURE",
                "message": "Clinical Validation Error: Lab report missing pathologist signature/validation stamp.",
                "severity": "MEDIUM"
            })
        return flags

    def check_unit_standards(self) -> List[dict]:
        """Flag non-standard medical units in lab results."""
        flags = []
        # Common valid lab units
        standard_units = ["mg/dl", "g/dl", "u/l", "iu/l", "mmol/l", "meq/l", "cells/mcL", "%", "ratio", "pg", "ng/ml", "ug/dl"]
        for res in self.test_results:
            if not res.unit or not res.value:
                continue
            
            unit_lower = res.unit.lower().replace(" ", "")
            if unit_lower not in standard_units:
                flags.append({
                    "code": "NON_STANDARD_UNIT",
                    "message": f"Non-standard lab unit '{res.unit}' detected for {res.test_name}.",
                    "severity": "LOW"
                })
        return flags

    def check_extreme_values(self) -> List[dict]:
        """Flag values > 3x normal as LAB ERROR/RETEST REQUIRED."""
        flags = []
        for res in self.test_results:
            if not res.reference_range or res.value is None:
                continue
            
            # Support pending results gracefully
            val_str = str(res.value).lower()
            if "pending" in val_str or "tbd" in val_str:
                continue

            try:
                # Ensure value is numeric for comparison
                val_num = float(res.value) if isinstance(res.value, (int, float, str)) else 0.0
                
                # Extract upper bound of reference range (e.g., "12.0 - 18.0" -> 18.0)
                ranges = re.findall(r"(\d+(\.\d+)?)", str(res.reference_range))
                if len(ranges) >= 2:
                    upper_bound = float(ranges[-1][0])
                    if val_num > (3 * upper_bound):
                        flags.append({
                            "code": "EXTREME_VALUE",
                            "message": f"LAB ERROR/RETEST REQUIRED: {res.test_name} value ({val_num}) is >3x normal.",
                            "severity": "HIGH"
                        })
            except (ValueError, TypeError):
                continue
        return flags
    def check_mandatory_fields(self) -> List[dict]:
        """Flag missing lab accreditation/compliance info."""
        flags = []
        acc = self.lab.accreditation
        if not acc or acc.lower() == "null" or acc == "":
            flags.append({
                "code": "MISSING_LAB_LICENSE",
                "message": "Clinical Liability Warning: Lab accreditation (CLIA/CAP) is missing from report.",
                "severity": "MEDIUM"
            })
        return flags
