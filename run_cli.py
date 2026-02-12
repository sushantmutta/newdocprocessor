import argparse
import os
import time
import glob
from app.graph import app as langgraph_pipeline
from app.state import DocState
from pypdf import PdfReader

def process_file(file_path: str, provider: str = "groq"):
    start_time = time.time()
    print(f"\n📄 Processing: {file_path}")
    
    try:
        # Extract text from PDF
        if file_path.lower().endswith('.pdf'):
            reader = PdfReader(file_path)
            raw_text = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
        else:
            with open(file_path, 'r', encoding='utf-8') as f:
                raw_text = f.read()
                
        if not raw_text.strip():
            print("❌ Error: Empty text extracted.")
            return

        # Initialize State
        initial_state = DocState(
            raw_text=raw_text,
            file_path=os.path.basename(file_path),
            doc_type=None,
            extracted_data={},
            validated_data={},
            redacted_text="",
            validation_flags=[], # Added for medical schema support
            errors=[],
            trace_log=[],
            repair_attempts=0,
            llm_provider=provider,
            llm_model_name=None
        )

        # Run Graph
        final_state = langgraph_pipeline.invoke(initial_state)
        
        latency = time.time() - start_time
        doc_type = final_state.get("doc_type", "unknown")
        success = final_state.get("metrics", {}).get("pipeline_success", False) # Reporter adds this to trace usually, check manually
        
        # Check actual success
        errors = final_state.get("errors", [])
        is_successful = len(errors) == 0
        
        print(f"✅ Completed in {latency:.2f}s")
        print(f"   Type: {doc_type}")
        print(f"   Status: {'Success' if is_successful else 'Failed'}")
        if errors:
            print(f"   Errors: {len(errors)}")

    except Exception as e:
        print(f"❌ Critical Error: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description="Agentic Document Processor CLI")
    parser.add_argument("input", help="Input file path or directory")
    parser.add_argument("--provider", default="groq", choices=["groq", "ollama", "bedrock"], help="LLM Provider")
    
    args = parser.parse_args()
    
    if os.path.isdir(args.input):
        files = glob.glob(os.path.join(args.input, "*.pdf")) + glob.glob(os.path.join(args.input, "*.txt"))
        print(f"Found {len(files)} documents in {args.input}")
        for f in files:
            process_file(f, args.provider)
    elif os.path.isfile(args.input):
        process_file(args.input, args.provider)
    else:
        print(f"❌ Error: Input path '{args.input}' not found.")

if __name__ == "__main__":
    main()
