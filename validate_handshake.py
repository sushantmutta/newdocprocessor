# test_groq_setup.py
from app.agents.classifier import classify_doc
from app.state import DocState


def validate():
    # Simulate text from your PDF
    sample_text = "INVOICE #60475. Bill to: Felix Stehr. Total: 8.028,26 EUR."

    state: DocState = {
        "raw_text": sample_text,
        "doc_type": None,
        "trace_log": [],
        "errors": []
    }

    print("🚀 Sending request to Groq...")
    result = classify_doc(state)
    print(f"🎯 Classifier Result: {result['doc_type']}")

    if result["doc_type"] == "invoice":
        print("✅ SUCCESS: Groq is configured and classifying correctly!")


if __name__ == "__main__":
    validate()
