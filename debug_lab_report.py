from app.agents.extractor import extract_data
from app.agents.validator import validate_data
from app.state import DocState
from langchain_core.messages import HumanMessage

def test_lab_report():
    print("🧪 Simulating User Lab Report Processing...")
    
    # 1. Mock Input Text (from User Image)
    # Report Date: 2026-02-07, Collection Date: 2026-02-10 -> This should FAIL consistency check!
    raw_text = """
    LABORATORY REPORT
    NABL Accredited Laboratory | ISO 9001:2015 Certified

    Report ID: LAB219220
    Collection Date: 2026-02-10
    Sample Type: Serum
    Report Date: 2026-02-07

    Patient Information
    Patient Name: Anil Sharma
    Patient ID: PT94341
    Age: 66
    Gender: Female

    Test Results
    Test Name           Value       Unit        Reference Range     Status
    WBC Count           7107.86     cells/mcL   4000 - 11000        Normal
    Creatinine          0.81        mg/dL       0.6 - 1.2           Normal
    HbA1c               4.05        %           4.0 - 5.6           Normal
    HDL Cholesterol     56.11       mg/dL       40 - 60             Normal
    Triglycerides       42.04       mg/dL       0 - 150             Normal
    Blood Glucose (Random) 124.98   mg/dL       70 - 140            Normal
    Thyroid TSH         2.58        mIU/L       0.4 - 4.0           Normal
    Blood Urea Nitrogen 13.94       mg/dL       7 - 20              Normal
    Vitamin B12         729.02      pg/mL       200 - 900           Normal
    ALT (SGPT)          34.44       U/L         7 - 56              Normal

    Dr. Singh
    Pathologist
    Date: 2026-02-07
    """
    
    state = DocState(
        raw_text=raw_text,
        doc_type="lab_report",
        llm_provider="groq", # Mocking provider
        extracted_data={},
        validated_data={},
        errors=[],
        trace_log=[]
    )

    # 2. Run Extractor
    print("\n📝 Running Extractor...")
    state = extract_data(state)
    print(f"Extracted Keys: {list(state['extracted_data'].keys())}")
    
    # 3. Run Validator
    print("\n✅ Running Validator...")
    state = validate_data(state)
    
    # 4. Results
    print("\n📊 Results:")
    if state["errors"]:
        print("❌ Errors found:")
        for e in state["errors"]:
            print(f"  - {e}")
    else:
        print("✅ Validation Success!")
        
    if state.get("validation_flags"):
        print("\n⚠️ Validation Flags:")
        for f in state["validation_flags"]:
            print(f"  - {f}")

if __name__ == "__main__":
    test_lab_report()
