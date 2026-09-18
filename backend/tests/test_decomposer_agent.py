"""
Unit & integration tests for Process Decomposer Agent and API endpoint.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.agents.requirement_analyzer import analyze_requirement
from app.agents.process_decomposer import decompose_process
from app.schemas.process import ProcessPlan


SAMPLE_REQUIREMENT = (
    "When an employee requests a laptop, check the company policy. "
    "If the cost is below ₹25,000, IT can process it. "
    "If it is above ₹25,000, manager approval is required."
)


def test_decompose_process_direct():
    analysis = analyze_requirement(SAMPLE_REQUIREMENT)
    plan = decompose_process(analysis, max_stages=6)

    assert isinstance(plan, ProcessPlan)
    assert len(plan.stages) >= 3
    assert len(plan.steps) >= 4
    assert len(plan.tool_requirements) >= 3

    # Check for approval step because our scenario has manager approval
    approval_steps = [s for s in plan.steps if s.category == "approval"]
    assert len(approval_steps) == 1
    assert approval_steps[0].requires_human is True

    # Check for terminal step
    end_steps = [s for s in plan.steps if s.category == "end"]
    assert len(end_steps) == 1

    # Check data flow map
    assert len(plan.data_flow_summary) >= 3


def test_decompose_process_api_endpoint():
    client = TestClient(app)
    analysis = analyze_requirement(SAMPLE_REQUIREMENT)

    payload = {
        "analysis": analysis.model_dump(),
        "max_stages": 6,
    }
    response = client.post("/api/v1/decompose-process", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "success"
    assert "plan" in data
    plan = data["plan"]
    assert "process_name" in plan
    assert len(plan["steps"]) >= 4
    assert len(plan["stages"]) >= 3
