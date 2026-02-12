"""
Test runner script for Groq-based document processing tests.
Run this script to execute the comprehensive test suite.
"""
import subprocess
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def check_groq_api_key():
    """Check if GROQ_API_KEY is set."""
    if not os.getenv("GROQ_API_KEY"):
        print("❌ ERROR: GROQ_API_KEY not found in environment")
        print("   Please set your Groq API key in .env file:")
        print("   GROQ_API_KEY=your_key_here")
        return False
    print("✅ GROQ_API_KEY found")
    return True


def run_tests(test_type="all"):
    """Run pytest tests based on type."""
    
    if not check_groq_api_key():
        sys.exit(1)
    
    base_cmd = ["pytest", "-v", "--tb=short"]
    
    if test_type == "all":
        print("\n🧪 Running ALL Groq tests...\n")
        cmd = base_cmd + ["-m", "groq"]
    
    elif test_type == "integration":
        print("\n🧪 Running Groq INTEGRATION tests...\n")
        cmd = base_cmd + ["-m", "groq and integration"]
    
    elif test_type == "validation":
        print("\n🧪 Running Groq VALIDATION tests...\n")
        cmd = base_cmd + ["-m", "groq and validation"]
    
    elif test_type == "pii":
        print("\n🧪 Running Groq PII REDACTION tests...\n")
        cmd = base_cmd + ["-m", "groq and pii"]
    
    elif test_type == "performance":
        print("\n🧪 Running Groq PERFORMANCE tests...\n")
        cmd = base_cmd + ["-m", "groq and performance"]
    
    elif test_type == "quick":
        print("\n🧪 Running QUICK Groq tests (excluding performance)...\n")
        cmd = base_cmd + ["-m", "groq and not performance"]
    
    else:
        print(f"❌ Unknown test type: {test_type}")
        print("   Valid types: all, integration, validation, pii, performance, quick")
        sys.exit(1)
    
    # Run tests
    result = subprocess.run(cmd, cwd=Path(__file__).parent)
    
    return result.returncode


def main():
    """Main test runner."""
    print("=" * 60)
    print("  Agentic Document Processor - Groq Test Suite")
    print("=" * 60)
    
    # Parse command line arguments
    test_type = sys.argv[1] if len(sys.argv) > 1 else "all"
    
    # Run tests
    exit_code = run_tests(test_type)
    
    if exit_code == 0:
        print("\n" + "=" * 60)
        print("  ✅ ALL TESTS PASSED!")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("  ❌ SOME TESTS FAILED")
        print("=" * 60)
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
