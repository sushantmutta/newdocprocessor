import pytest
import sys

if __name__ == "__main__":
    print("🏥 Running Medical Document Processing Tests...")
    
    # Run tests for schemas and agents
    args = [
        "tests/test_medical_schemas.py",
        "tests/test_medical_agents.py",
        "tests/test_reporting.py",
        "-v"
    ]
    
    exit_code = pytest.main(args)
    
    if exit_code == 0:
        print("\n✅ All medical tests PASSED!")
    else:
        print("\n❌ Some tests FAILED.")
    
    sys.exit(exit_code)
