from langgraph.graph import StateGraph, END
from typing import Literal

from app.graph.state import ClaimsState
from app.agents.retrieval_agent import retrieval_agent
from app.agents.fraud_detection_agent import fraud_detection_agent
from app.agents.guidance_agent import guidance_agent, reviewer_support_agent


def route_after_retrieval(state: ClaimsState) -> Literal["fraud_detection_agent", "reviewer_support_agent", "end"]:
    """
    Route to the next agent based on intent after retrieval is complete.

    For claim_submission, proceed to fraud detection.
    For other intents, proceed to reviewer support.
    """
    intent = state.get("intent")

    if intent == "claim_submission":
        return "fraud_detection_agent"

    if intent in {
        "policy_question",
        "coverage_question",
        "required_documents_question",
        "general_information",
    }:
        return "reviewer_support_agent"

    if intent == "claim_status":
        return "reviewer_support_agent"

    return "end"


def create_claims_workflow():
    """Create and compile the multi-agent insurance claims workflow."""

    # Initialize the graph with our shared state
    graph = StateGraph(ClaimsState)

    # Add agent nodes
    graph.add_node("retrieval_agent", retrieval_agent)
    graph.add_node("fraud_detection_agent", fraud_detection_agent)
    graph.add_node("reviewer_support_agent", reviewer_support_agent)

    # Entry point
    graph.set_entry_point("retrieval_agent")

    # Conditional routing after retrieval
    graph.add_conditional_edges(
        "retrieval_agent",
        route_after_retrieval,
        {
            "fraud_detection_agent": "fraud_detection_agent",
            "reviewer_support_agent": "reviewer_support_agent",
            "end": END,
        },
    )

    # Fraud detection routes to reviewer support
    graph.add_edge("fraud_detection_agent", "reviewer_support_agent")
    graph.add_edge("reviewer_support_agent", END)

    return graph.compile()


# Alternative: If the orchestrator is the entry point and we just want to show
# how retrieval connects to the existing flow:
def add_retrieval_to_existing_graph(graph: StateGraph) -> StateGraph:
    """
    Add retrieval agent to an existing graph that already has orchestrator,
    fraud detection, and reviewer support agents.

    This shows how you would integrate the retrieval agent into an existing workflow.
    """
    # Add retrieval agent node
    graph.add_node("retrieval_agent", retrieval_agent)

    # Connect orchestrator -> retrieval_agent -> fraud_detection_agent
    # (assuming these nodes already exist in the graph)
    graph.add_edge("orchestrator", "retrieval_agent")
    graph.add_edge("retrieval_agent", "fraud_detection_agent")

    return graph