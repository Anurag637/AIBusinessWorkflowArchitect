"""
Unit & integration tests for Workflow Architect Agent and API endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.agents.requirement_analyzer import analyze_requirement
from app.agents.process_decomposer import decompose_process
from app.agents.workflow_architect import generate_workflow
from app.schemas.workflow import WorkflowDefinition, StepType
from app.schemas.validator import DeterministicValidator


SAMPLE_REQUIREMENT = (
    "When an employee requests a laptop, check the company policy. "
    "If the cost is below ₹25,000, IT can process it. "
    "If it is above ₹25,000, manager approval is required."
)


def test_generate_workflow_direct():
    analysis = analyze_requirement(SAMPLE_REQUIREMENT)
    plan = decompose_process(analysis)
    wf = generate_workflow(analysis, plan)

    assert isinstance(wf, WorkflowDefinition)
    assert wf.trigger.id == "trigger_1"
    assert len(wf.steps) >= 5

    # DeterministicValidator check on synthesized workflow
    validator = DeterministicValidator()
    result = validator.validate(wf)
    assert result.is_valid is True
    assert len(result.errors) == 0

    # Ensure all step types are valid
    for s in wf.steps:
        assert s.type in [
            StepType.DATABASE,
            StepType.RAG,
            StepType.DECISION,
            StepType.NOTIFICATION,
            StepType.APPROVAL,
            StepType.TRANSFORM,
            StepType.END,
        ]

    # Ensure approval step exists and has approver_role
    approval_steps = [s for s in wf.steps if s.type == StepType.APPROVAL]
    assert len(approval_steps) == 1
    assert approval_steps[0].approver_role is not None


def test_generate_workflow_api_endpoint():
    client = TestClient(app)
    analysis = analyze_requirement(SAMPLE_REQUIREMENT)
    plan = decompose_process(analysis)

    payload = {
        "analysis": analysis.model_dump(),
        "process_plan": plan.model_dump(),
        "name": "Laptop Request Flow",
    }
    response = client.post("/api/v1/generate-workflow", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "success"
    assert "workflow" in data
    assert "validation_result" in data
    assert data["validation_result"]["is_valid"] is True
    assert data["workflow"]["name"] == "Laptop Request Flow"


def test_validate_workflow_api_endpoint():
    client = TestClient(app)
    analysis = analyze_requirement(SAMPLE_REQUIREMENT)
    plan = decompose_process(analysis)
    wf = generate_workflow(analysis, plan)

    response = client.post("/api/v1/validate-workflow", json={"workflow": wf.model_dump()})
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "success"
    assert data["validation_result"]["is_valid"] is True
