"""
Unit & integration tests for Human Approval System and API endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.approval import ApprovalService, get_approval_service
from app.models.entities import ApprovalStatus


def test_approval_service_lifecycle():
    service = ApprovalService()

    # 1. Create request
    req = service.create_request(
        workflow_execution_id="exec_100",
        step_id="step_5",
        approver_role="manager",
        context_data={"cost": 85000, "employee": "Rahul"},
    )
    assert req.id is not None
    assert req.status == ApprovalStatus.PENDING

    # 2. List pending
    pending_mgr = service.list_pending(approver_role="manager")
    assert len(pending_mgr) == 1
    assert pending_mgr[0].id == req.id

    pending_dir = service.list_pending(approver_role="director")
    assert len(pending_dir) == 0

    # 3. Submit decision
    decided = service.submit_decision(
        approval_id=req.id,
        reviewer_id="manager_priya",
        decision=ApprovalStatus.APPROVED,
        comments="Approved for Q3 engineering deliverable",
    )
    assert decided is not None
    assert decided.status == ApprovalStatus.APPROVED
    assert decided.reviewed_by == "manager_priya"
    assert decided.reviewed_at is not None

    # 4. Now list pending should be empty
    assert len(service.list_pending(approver_role="manager")) == 0


def test_approval_api_endpoints():
    client = TestClient(app)

    # 1. Create via API
    create_payload = {
        "workflow_execution_id": "exec_api_200",
        "step_id": "step_approval",
        "approver_role": "director",
        "context_data": {"item": "GPU Cluster Access", "cost": 150000},
    }
    res_create = client.post("/api/v1/approvals", json=create_payload)
    assert res_create.status_code == 201
    data_create = res_create.json()
    approval_id = data_create["approval"]["id"]

    # 2. List pending
    res_pending = client.get("/api/v1/approvals/pending?role=director")
    assert res_pending.status_code == 200
    assert any(a["id"] == approval_id for a in res_pending.json()["approvals"])

    # 3. Get single
    res_get = client.get(f"/api/v1/approvals/{approval_id}")
    assert res_get.status_code == 200
    assert res_get.json()["approval"]["id"] == approval_id

    # 4. Decide
    decide_payload = {
        "reviewer_id": "director_alex",
        "decision": "approved",
        "comments": "Signed off on hardware budget",
    }
    res_decide = client.post(f"/api/v1/approvals/{approval_id}/decide", json=decide_payload)
    assert res_decide.status_code == 200
    assert res_decide.json()["approval"]["status"] == "approved"
