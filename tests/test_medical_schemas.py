import pytest
from app.schemas.prescription_schema import PrescriptionSchema, Medication, DoctorInfo, PatientInfo
from app.schemas.lab_report_schema import LabReportSchema, LabInfo, TestResult
from pydantic import ValidationError

# --- Prescription Schema Tests ---

class TestPrescriptionSchema:
    def test_valid_prescription(self):
        data = {
            "doctor": {"name": "Dr. Smith", "license_number": "MH-12345", "dea_number": "AB1234567"},
            "patient": {"name": "John Doe", "id": "PT12345", "age": 30, "gender": "Male"},
            "medications": [
                {"name": "Amoxicillin", "dosage": "500mg", "frequency": "3 times daily", "duration": "7 days"}
            ],
            "date": "2024-03-15"
        }
        prescription = PrescriptionSchema(**data)
        assert prescription.doctor.license_number == "MH-12345"
        assert prescription.patient.id == "PT12345"
        assert prescription.medications[0].dosage == "500mg"

    def test_invalid_dosage_format(self):
        data = {
            "doctor": {"name": "Dr. Smith", "license_number": "MH-12345"},
            "patient": {"name": "John Doe"},
            "medications": [
                {"name": "Pill", "dosage": "500 liters", "frequency": "daily"} 
            ],
            "date": "2024-03-15"
        }
        # "500 liters" is invalid as per Handover Spec
        with pytest.raises(ValidationError) as exc:
            PrescriptionSchema(**data)
        assert "Invalid dosage format or unit" in str(exc.value)

    def test_pediatric_missing_weight(self):
        data = {
            "doctor": {"name": "Dr. Kim", "license_number": "MH-99999"},
            "patient": {"name": "Baby Doe", "age": 5}, # < 12 years, but weight missing
            "medications": [
                {"name": "Tylenol", "dosage": "100mg", "frequency": "PRN"}
            ],
            "date": "2024-03-15"
        }
        prescription = PrescriptionSchema(**data)
        warnings = prescription.check_pediatric_dosing()
        assert len(warnings) == 1
        assert "MISSING WEIGHT" in warnings[0]

    def test_controlled_substance_missing_dea(self):
        data = {
            "doctor": {"name": "Dr. House", "license_number": "MH-00000"}, # DEA missing
            "patient": {"name": "Greg", "age": 50},
            "medications": [
                {"name": "Morphine Sulfate", "dosage": "10mg", "frequency": "Q4H"}
            ],
            "date": "2024-03-15"
        }
        prescription = PrescriptionSchema(**data)
        warnings = prescription.check_controlled_substances()
        assert len(warnings) == 1
        assert "DEA Number is MISSING" in warnings[0]


# --- Lab Report Schema Tests ---

class TestLabReportSchema:
    def test_valid_lab_report(self):
        data = {
            "lab": {"name": "City Lab", "address": "123 Main St"},
            "report_id": "LAB123456",
            "collection_date": "2024-03-14",
            "report_date": "2024-03-15",
            "test_results": [
                {"test_name": "WBC", "value": 7.5, "unit": "k/cumm", "status": "Normal"}
            ]
        }
        report = LabReportSchema(**data)
        assert report.report_id == "LAB123456"
        assert report.test_results[0].status == "Normal"

    def test_date_inconsistency(self):
        data = {
            "lab": {"name": "City Lab"},
            "report_id": "LAB654321",
            "collection_date": "2024-03-15",
            "report_date": "2024-03-14", # Report before collection!
            "test_results": []
        }
        # Should NOT raise ValidationError now
        report = LabReportSchema(**data)
        
        # Should produce warnings from check method
        warnings = report.check_date_consistency()
        assert len(warnings) == 1
        assert "cannot be earlier than collection date" in warnings[0]

    def test_critical_value_flag(self):
        data = {
            "lab": {"name": "City Lab"},
            "report_id": "LAB000003",
            "collection_date": "2024-03-14",
            "report_date": "2024-03-15",
            "test_results": [
                {"test_name": "Potassium", "value": 7.0, "unit": "mmol/L", "status": "Critical", "reference_range": "3.5 - 5.1"}
            ]
        }
        report = LabReportSchema(**data)
        flags = report.check_critical_values()
        assert len(flags) == 1
        assert "CRITICAL: Potassium" in flags[0]

    def test_amended_report_flag(self):
        data = {
            "lab": {"name": "City Lab"},
            "report_id": "LAB999999",
            "is_amended": True,
            "collection_date": "2024-03-14",
            "report_date": "2024-03-15",
            "test_results": []
        }
        report = LabReportSchema(**data)
        warnings = report.check_amended_status()
        assert len(warnings) == 1
        assert "AMENDED REPORT" in warnings[0]
