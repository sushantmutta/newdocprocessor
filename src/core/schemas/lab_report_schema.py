from typing import List, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import datetime
import re


class LabInfo(BaseModel):
    name: Optional[str] = Field(None, description="Name of the laboratory")
    accreditation: Optional[str] = Field(
        None, description="Lab accreditation (e.g., CLIA)")
    address: Optional[str] = Field(None, description="Lab address")
    pathologist_name: Optional[str] = Field(
        None, description="Name of the pathologist who validated the report")
    has_pathologist_signature: bool = Field(
        False, description="Whether a digital or physical signature is present")


class TestResult(BaseModel):
    test_name: Optional[str] = Field(
        None, description="Name of the test/analyte")
    value: Optional[Union[float, str]] = Field(
        None, description="Result value")
    unit: Optional[str] = Field(None, description="Measurement unit")
    reference_range: Optional[str] = Field(
        None, description="Normal reference interval (e.g., 12.0 - 18.0)")
    status: Optional[str] = Field(
        None, description="Interpretation: Normal, High, Low, Critical")

    @field_validator('status')
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v is None:
            return v
        allowed = ["normal", "high", "low", "critical", "extreme", "panic"]
        if v.lower() not in allowed:
            # Map approximate values or raise error?
            # Handover spec says "CRITICAL/EXTREME"
            pass  # For now, allow it, but validator logic will be strict?
            # Actually, let's enforce lowercase
        return v


class LabReportSchema(BaseModel):
    lab: LabInfo = Field(default_factory=LabInfo)
    report_id: Optional[str] = Field(
        None, description="Unique report identifier (LAB######)")
    sample_type: Optional[str] = Field(
        None, description="Type of specimen collected (e.g., Serum, Plasma, Whole Blood, Urine)")
    collection_date: Optional[str] = Field(
        None, description="Date sample collected (any format)")
    report_date: Optional[str] = Field(
        None, description="Date report issued (any format)")
    test_results: List[TestResult] = Field(default_factory=list)
    is_amended: bool = Field(
        False, description="Whether this is a corrected or amended report")

    def check_date_consistency(self) -> List[dict]:
        """Check if report date is logically after collection date."""
        flags = []

        def parse_any_date(date_str: Optional[str]) -> Optional[datetime]:
            if not date_str:
                return None
            # Common formats to try
            formats = ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y',
                       '%Y/%m/%d', '%b %d, %Y', '%d %b %Y']
            for fmt in formats:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
            return None

        coll = parse_any_date(self.collection_date)
        rep = parse_any_date(self.report_date)

        if coll and rep and rep < coll:
            flags.append({
                "code": "DATE_INCONSISTENCY",
                "message": f"Report date {self.report_date} cannot be earlier than collection date {self.collection_date}",
                "severity": "MEDIUM",
                "field": "collection_date",
                "value": self.collection_date
            })
        return flags

    def check_amended_status(self) -> List[dict]:
        """Check if report is an amended version."""
        flags = []
        if self.is_amended:
            flags.append({
                "code": "AMENDED_REPORT",
                "message": "AMENDED REPORT: This is a corrected version of a previous result.",
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
                    "message": f"CRITICAL: {res.test_name} is in critical range ({res.value}).",
                    "severity": "CRITICAL"
                })
        return flags

    def check_pathologist_signature(self) -> List[dict]:
        """Flag missing pathologist signature for liability.

        Signature is considered PRESENT if:
        - Pathologist name is valid (not N/A, null, etc.) OR
        - has_pathologist_signature flag is True

        Signature is considered MISSING if:
        - Pathologist name is N/A/null/missing AND
        - has_pathologist_signature flag is False
        """
        flags = []
        # Only check if test results exist
        if len(self.test_results) > 0:
            # Define invalid pathologist names
            invalid_names = ["n/a", "na", "null", "none", "-",
                             "not available", "pending", ""]

            # Check if pathologist name is valid
            pathologist_name_valid = False
            if self.lab.pathologist_name:
                name_lower = self.lab.pathologist_name.lower().strip()
                pathologist_name_valid = name_lower not in invalid_names

            # Signature is present if EITHER:
            # 1. Pathologist name is valid (a real name like "Dr. Kumar")
            # 2. has_pathologist_signature flag is True
            signature_present = pathologist_name_valid or self.lab.has_pathologist_signature

            # Flag only if signature is MISSING (both checks fail)
            if not signature_present:
                flags.append({
                    "code": "MISSING_PATHOLOGIST_SIGNATURE",
                    "message": "Liability risk: Lab report lacks pathologist signature or validation.",
                    "severity": "MEDIUM"
                })

        return flags

    def check_unit_standards(self) -> List[dict]:
        """Flag non-standard medical units in lab results."""
        flags = []
        # Common valid lab units (normalized to lowercase for comparison)
        standard_units = [
            "mg/dl", "g/dl", "u/l", "iu/l", "mmol/l", "meq/l",
            "cells/mcl", "cells/μl", "10^3/μl", "10^6/μl",
            "%", "ratio", "fl", "pg", "pg/ml", "ng/ml", "μg/dl", "ug/dl",
            "miu/l", "ng/dl", "pmol/l", "nmol/l", "μg/l"
        ]
        for i, res in enumerate(self.test_results):
            if not res.unit or not res.value:
                continue

            unit_lower = res.unit.lower().replace(" ", "")
            if unit_lower not in standard_units:
                flags.append({
                    "code": "NON_STANDARD_UNIT",
                    "message": f"Non-standard lab unit '{res.unit}' detected for {res.test_name}.",
                    "severity": "LOW",
                    "field": f"test_results[{i}].unit",
                    "value": res.unit
                })
        return flags

    def check_missing_reference_ranges(self) -> List[dict]:
        """Flag test results with missing or invalid reference ranges."""
        flags = []

        # Invalid reference range values that should be flagged
        invalid_ranges = ["n/a", "na", "null", "none",
                          "", "-", "not available", "pending"]

        for res in self.test_results:
            ref_range = res.reference_range

            # Check if reference range is missing or invalid
            if not ref_range or ref_range.lower().strip() in invalid_ranges:
                flags.append({
                    "code": "MISSING_REFERENCE_RANGE",
                    "message": f"Clinical interpretation limited: Test '{res.test_name}' is missing a reference range. Cannot determine if value is normal without comparative range.",
                    "severity": "MEDIUM"
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
                val_num = float(res.value) if isinstance(
                    res.value, (int, float, str)) else 0.0

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

    def check_out_of_range_values(self) -> List[dict]:
        """Flag test results that are outside reference ranges with severity based on deviation."""
        flags = []

        for res in self.test_results:
            if not res.reference_range or res.value is None:
                continue

            # Skip pending/TBD results
            val_str = str(res.value).lower()
            if "pending" in val_str or "tbd" in val_str or "n/a" in val_str:
                continue

            try:
                # Parse numeric value
                val_num = float(res.value) if isinstance(
                    res.value, (int, float, str)) else None
                if val_num is None:
                    continue

                # Extract lower and upper bounds from reference range
                # Handles formats: "12.0 - 18.0", "70-100", "< 5.0", "> 10"
                ranges = re.findall(r"(\d+\.?\d*)", str(res.reference_range))

                if len(ranges) >= 2:
                    lower_bound = float(ranges[0])
                    upper_bound = float(ranges[-1])

                    # Check if value is out of range
                    if val_num < lower_bound or val_num > upper_bound:
                        # Calculate percentage deviation from normal range
                        if val_num < lower_bound:
                            # Out of range LOW
                            deviation_pct = (
                                (lower_bound - val_num) / lower_bound) * 100
                            direction = "Low"

                            # Severity based on how far below normal
                            if deviation_pct >= 50:
                                # More than 50% below lower limit
                                severity = "CRITICAL"
                                message = f"CRITICAL LOW: {res.test_name} is {val_num} {res.unit} (reference: {res.reference_range}). Value is {deviation_pct:.1f}% below normal range - immediate medical attention required."
                            elif deviation_pct >= 30:
                                # 30-50% below lower limit
                                severity = "HIGH"
                                message = f"Significantly Low: {res.test_name} is {val_num} {res.unit} (reference: {res.reference_range}). {deviation_pct:.1f}% below normal - urgent clinical review recommended."
                            elif deviation_pct >= 15:
                                # 15-30% below lower limit
                                severity = "MEDIUM"
                                message = f"Moderately Low: {res.test_name} is {val_num} {res.unit} (reference: {res.reference_range}). {deviation_pct:.1f}% below normal range - clinical attention advised."
                            else:
                                # Less than 15% below
                                severity = "LOW"
                                message = f"Slightly Low: {res.test_name} is {val_num} {res.unit} (reference: {res.reference_range}). Borderline low result - monitor trend."

                        else:
                            # Out of range HIGH
                            deviation_pct = (
                                (val_num - upper_bound) / upper_bound) * 100
                            direction = "High"

                            # Severity based on how far above normal
                            if deviation_pct >= 100:
                                # More than 2x upper limit (100%+ above)
                                severity = "CRITICAL"
                                message = f"CRITICAL HIGH: {res.test_name} is {val_num} {res.unit} (reference: {res.reference_range}). Value is {deviation_pct:.1f}% above normal range - immediate medical attention required."
                            elif deviation_pct >= 40:
                                # 40-100% above upper limit
                                severity = "HIGH"
                                message = f"Significantly High: {res.test_name} is {val_num} {res.unit} (reference: {res.reference_range}). {deviation_pct:.1f}% above normal - urgent clinical review recommended."
                            elif deviation_pct >= 15:
                                # 15-40% above upper limit
                                severity = "MEDIUM"
                                message = f"Moderately High: {res.test_name} is {val_num} {res.unit} (reference: {res.reference_range}). {deviation_pct:.1f}% above normal range - clinical attention advised."
                            else:
                                # Less than 15% above
                                severity = "LOW"
                                message = f"Slightly High: {res.test_name} is {val_num} {res.unit} (reference: {res.reference_range}). Borderline high result - monitor trend."

                        flags.append({
                            "code": f"OUT_OF_RANGE_{direction.upper()}",
                            "message": message,
                            "severity": severity
                        })

                elif len(ranges) == 1:
                    # Single value range (e.g., "< 5.0" or "> 10")
                    ref_val = float(ranges[0])
                    # Check for < or > in reference range
                    if "<" in res.reference_range and val_num >= ref_val:
                        flags.append({
                            "code": "OUT_OF_RANGE_HIGH",
                            "message": f"Above threshold: {res.test_name} is {val_num} {res.unit} (should be < {ref_val}).",
                            "severity": "MEDIUM"
                        })
                    elif ">" in res.reference_range and val_num <= ref_val:
                        flags.append({
                            "code": "OUT_OF_RANGE_LOW",
                            "message": f"Below threshold: {res.test_name} is {val_num} {res.unit} (should be > {ref_val}).",
                            "severity": "MEDIUM"
                        })

            except (ValueError, TypeError):
                continue

        return flags

    def check_sample_type(self) -> List[dict]:
        """Flag missing sample type field."""
        flags = []
        # Only flag if test results exist (finalized report)
        if len(self.test_results) > 0:
            if not self.sample_type or self.sample_type.lower().strip() in ["n/a", "na", "null", "none", "-", ""]:
                flags.append({
                    "code": "MISSING_SAMPLE_TYPE",
                    "message": "Clinical quality issue: Sample type not specified. Critical for test interpretation (Serum, Plasma, Whole Blood, etc.).",
                    "severity": "MEDIUM"
                })
        return flags

    def check_mandatory_fields(self) -> List[dict]:
        """Flag missing lab accreditation/compliance info and required fields."""
        flags = []
        # Only flag if this appears to be a finalized report with actual results
        if len(self.test_results) > 0:
            acc = self.lab.accreditation
            if not acc or acc.lower() == "null" or acc == "":
                flags.append({
                    "code": "MISSING_LAB_LICENSE",
                    "message": "Regulatory risk: Lab report missing accreditation/CLIA number.",
                    "severity": "MEDIUM",
                    "field": "lab.accreditation",
                    "value": acc
                })
        if not self.lab.name:
            flags.append({
                "code": "MISSING_REQUIRED_FIELD",
                "message": "Required field missing: Laboratory name is absent.",
                "severity": "HIGH",
                "field": "lab.name",
                "value": None
            })
        if not self.report_id:
            flags.append({
                "code": "MISSING_REQUIRED_FIELD",
                "message": "Required field missing: Report ID is absent.",
                "severity": "HIGH",
                "field": "report_id",
                "value": None
            })
        if not self.collection_date:
            flags.append({
                "code": "MISSING_REQUIRED_FIELD",
                "message": "Required field missing: Sample collection date is absent.",
                "severity": "HIGH",
                "field": "collection_date",
                "value": None
            })
        if not self.test_results:
            flags.append({
                "code": "MISSING_REQUIRED_FIELD",
                "message": "Required field missing: No test results in report.",
                "severity": "HIGH",
                "field": "test_results",
                "value": None
            })
        return flags

    def check_date_formats(self) -> List[dict]:
        """Flag date fields that don't use ISO 8601 (YYYY-MM-DD) format."""
        flags = []
        iso_re = re.compile(r"^\d{4}-\d{2}-\d{2}$")
        date_fields = [
            ("collection_date", self.collection_date),
            ("report_date", self.report_date),
        ]
        for field_name, value in date_fields:
            if value and not iso_re.match(str(value)):
                flags.append({
                    "code": "INVALID_DATE_FORMAT",
                    "message": f"Date field '{field_name}' has non-ISO format: '{value}'. Expected YYYY-MM-DD.",
                    "severity": "MEDIUM",
                    "field": field_name,
                    "value": value
                })
        return flags

    def check_ambiguous_values(self) -> List[dict]:
        """Flag fields containing ambiguous placeholder text."""
        flags = []
        AMBIGUOUS_TOKENS = {"n/a", "na", "?", "unknown",
                            "tbd", "none", "pending", "not specified", "xxx"}

        def _is_ambiguous(val) -> bool:
            if not val or not isinstance(val, str):
                return False
            return val.strip().lower() in AMBIGUOUS_TOKENS

        top_fields = [
            ("report_id", self.report_id),
            ("sample_type", self.sample_type),
            ("collection_date", self.collection_date),
            ("report_date", self.report_date),
            ("lab.name", self.lab.name),
        ]
        for field_name, value in top_fields:
            if _is_ambiguous(value):
                flags.append({
                    "code": "AMBIGUOUS_VALUE",
                    "message": f"Field '{field_name}' contains ambiguous placeholder value: '{value}'.",
                    "severity": "MEDIUM",
                    "field": field_name,
                    "value": value
                })
        for i, res in enumerate(self.test_results):
            result_fields = [
                (f"test_results[{i}].test_name", res.test_name),
                (f"test_results[{i}].unit", res.unit),
            ]
            for field_name, value in result_fields:
                if _is_ambiguous(value):
                    flags.append({
                        "code": "AMBIGUOUS_VALUE",
                        "message": f"Field '{field_name}' contains ambiguous placeholder value: '{value}'.",
                        "severity": "MEDIUM",
                        "field": field_name,
                        "value": value
                    })
        return flags
