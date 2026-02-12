from langgraph.graph import StateGraph, END
from app.state import DocState
from app.agents.classifier import classify_doc
from app.agents.extractor import extract_data
from app.agents.validator import validate_data
from app.agents.redactor import redact_pii
from app.agents.reporter import generate_report


def router(state: DocState):
    doc_type = (state.get("doc_type") or "").lower().strip()
    if doc_type in ["prescription", "lab_report"]:
        return "extractor"
    return "redactor"


workflow = StateGraph(DocState)

workflow.add_node("classifier", classify_doc)
workflow.add_node("extractor", extract_data)
workflow.add_node("validator", validate_data)
workflow.add_node("redactor", redact_pii)
workflow.add_node("reporter", generate_report)

workflow.set_entry_point("classifier")

workflow.add_conditional_edges("classifier", router, {
    "extractor": "extractor",
    "redactor": "redactor"
})

workflow.add_edge("extractor", "validator")
workflow.add_edge("validator", "redactor")
workflow.add_edge("redactor", "reporter")
workflow.add_edge("reporter", END)

app = workflow.compile()
