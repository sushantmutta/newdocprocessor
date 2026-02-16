from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from app.state import DocState
from app.agents.classifier import classify_doc
from app.agents.extractor import extract_data
from app.agents.validator import validate_data
from app.agents.repair import repair_data, should_repair
from app.agents.redactor import redact_pii
from app.agents.reporter import generate_report


def router(state: DocState):
    """Route to extractor for structured docs, redactor for other docs."""
    doc_type = (state.get("doc_type") or "").lower().strip()
    if doc_type in ["prescription", "lab_report"]:
        return "extractor"
    return "redactor"


workflow = StateGraph(DocState)

# Add all agent nodes
workflow.add_node("classifier", classify_doc)
workflow.add_node("extractor", extract_data)
workflow.add_node("validator", validate_data)
workflow.add_node("repair", repair_data)
workflow.add_node("redactor", redact_pii)
workflow.add_node("reporter", generate_report)

workflow.set_entry_point("classifier")

# Classifier → Extractor or Redactor
workflow.add_conditional_edges("classifier", router, {
    "extractor": "extractor",
    "redactor": "redactor"
})

# Extractor → Validator
workflow.add_edge("extractor", "validator")

# Validator → Repair (if unit errors) or Redactor (if no errors)
workflow.add_conditional_edges("validator", should_repair, {
    "repair": "repair",
    "redactor": "redactor"
})

# Repair → Validator (re-validate after repair)
workflow.add_edge("repair", "validator")

# Redactor → Reporter → END
workflow.add_edge("redactor", "reporter")
workflow.add_edge("reporter", END)

# Compile TWO versions of the graph:

# 1. Standard graph (no interrupts) for normal processing
app = workflow.compile()

# 2. Graph with human-in-the-loop (with interrupts) for review mode
checkpointer = MemorySaver()
app_with_review = workflow.compile(
    checkpointer=checkpointer,
    interrupt_after=["repair"]
)
