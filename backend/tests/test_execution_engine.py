"""
Unit & integration tests for Execution Engine, pauses, and resumption.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.executor import ExecutionEngine, get_executor
from app.models.entities import ExecutionStatus, ApprovalStatus
from tests.test_workflow_schema import get_valid_workflow


def test_standard_execution_runs_to_completion():
    wf = get_valid_workflow()
    engine = ExecutionEngine()

    state = engine.start_execution(
        wf, initial_inputs={"request_id": "req_standard", "cost": 18000}
    )
    assert state.status == ExecutionStatus.COMPLETED
    assert state.completed_at is not None
    assert len(state.steps) >= 5


def test_high_value_execution_pauses_and_resumes():
    wf = get_valid_workflow()
    engine = ExecutionEngine()

    # 1. Start execution requiring manager approval (> 25k)
    state = engine.start_execution(
        wf, initial_inputs={"request_id": "req_high_value", "cost": 85000}
    )
    assert state.status == ExecutionStatus.PAUSED
    assert state.pending_approval_id is not None

    # 2. Resume with approval
    resumed = engine.resume_execution(
        execution_id=state.id,
        reviewer_id="manager_bob",
        decision=ApprovalStatus.APPROVED,
        comments="Approved laptop for Q3",
    )
    assert resumed is not None
    assert resumed.status == ExecutionStatus.COMPLETED
    assert resumed.completed_at is not None


def test_high_value_execution_rejection():
    wf = get_valid_workflow()
    engine = ExecutionEngine()

    state = engine.start_execution(
        wf, initial_inputs={"request_id": "req_high_value", "cost": 85000}
    )
    assert state.status == ExecutionStatus.PAUSED

    # Reject
    resumed = engine.resume_execution(
        execution_id=state.id,
        reviewer_id="manager_bob",
        decision=ApprovalStatus.REJECTED,
        comments="Over budget",
    )
    assert resumed.status == ExecutionStatus.FAILED
    assert "rejected" in resumed.error_message.lower()


def test_execution_api_endpoints():
    client = TestClient(app)
    wf = get_valid_workflow()

    # Start
    start_payload = {
        "workflow": wf.model_dump(),
        "initial_inputs": {"request_id": "req_high_value", "cost": 85000},
    }
    res_start = client.post("/api/v1/executions/start", json=start_payload)
    assert res_start.status_code == 201
    data = res_start.json()["execution"]
    exec_id = data["id"]
    assert data["status"] == "paused"

    # Get details
    res_get = client.get(f"/api/v1/executions/{exec_id}")
    assert res_get.status_code == 200
    assert res_get.json()["execution"]["id"] == exec_id

    # Resume
    resume_payload = {
        "reviewer_id": "vp_susan",
        "decision": "approved",
        "comments": "Approved via API",
    }
    res_resume = client.post(f"/api/v1/executions/{exec_id}/resume", json=resume_payload)
    assert res_resume.status_code == 200
    assert res_resume.json()["execution"]["status"] == "completed"
