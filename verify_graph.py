import sys
import traceback

try:
    from app.graph import create_graph
    from app.state import DocState
except Exception as e:
    print("❌ Critical ImportError:")
    traceback.print_exc()
    sys.exit(1)

def verify_graph():
    print("🚀 Verifying Graph Execution...")
    
    workflow = create_graph()
    
    # Mock Document: Prescription
    initial_state = DocState(
        raw_text="Rx: Amoxicillin 500mg, Take 1 tablet by mouth twice daily for 7 days. Dr. Gregory House.",
        file_path="mock_prescription.txt",
        llm_provider="groq", # Mock
        extracted_data={},
        validated_data={},
        errors=[],
        trace_log=[]
    )
    
    print(f"Input Text: {initial_state['raw_text']}")
    
    # Run Graph
    final_state = workflow.invoke(initial_state)
    
    # Check Steps
    agents_run = [entry['agent'] for entry in final_state['trace_log']]
    print(f"Agents Executed: {agents_run}")
    
    expected_agents = ['classifier', 'extractor_prescription', 'validator', 'redactor', 'reporter']
    
    missing = [agent for agent in expected_agents if agent not in agents_run]
    
    if not missing:
        print("✅ Graph Verification PASSED: All expected agents ran.")
    else:
        print(f"❌ Graph Verification FAILED: Missing agents: {missing}")
        # Note: Extractor agent name might be just 'extractor' if doc_type wasn't set correctly?
        # But extractor logs 'extractor_{doc_type}' on success.
        
    print(f"Final Doc Type: {final_state.get('doc_type')}")

if __name__ == "__main__":
    verify_graph()
