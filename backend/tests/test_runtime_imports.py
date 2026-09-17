"""Major backend modules must import through the project-root package path."""

import importlib

import pytest


@pytest.mark.parametrize(
    "module_name",
    [
        "backend.app.main",
        "backend.app.agents.claim_intake_agent",
        "backend.app.agents.retrieval_agent",
        "backend.app.agents.fraud_detection_agent",
        "backend.app.agents.guidance_agent",
        "backend.app.graph.workflow",
    ],
)
def test_major_runtime_module_imports_from_project_root(module_name: str) -> None:
    assert importlib.import_module(module_name) is not None


def test_optional_graph_reports_missing_langgraph_at_use_time() -> None:
    workflow = importlib.import_module("backend.app.graph.workflow")
    if workflow.StateGraph is not None:
        pytest.skip("LangGraph is installed in this environment")
    with pytest.raises(RuntimeError, match="LangGraph is required"):
        workflow.create_claims_workflow()
