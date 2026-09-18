"""
End-to-End Integration Test for complete system workflow lifecycle:
1. Natural Language Requirement Analysis
2. Process Decomposition
3. Workflow Architecture Synthesis
4. Deterministic + Semantic Validation
5. Sandbox Simulation Dry-Run
6. Production Execution & Human Pause
7. Reviewer Approval & Resumption to Completion
8. Audit Trail Verification
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

REQUIREMENT_TEXT = (
    "When an employee requests a laptop, check the company policy. "
    "If the cost is below ₹25,000, IT can process it. "
    "If it is above ₹25,000, manager approval is required."
)


def test_full_system_lifecycle_e2e():
    client = TestClient(app)

    # 1. Analyze Requirement
    res_analyze = client.post(
        "/api/v1/analyze-requirement",
        json={"requirement_text": REQUIREMENT_TEXT, "domain_hint": "it_procurement"},
    )
    assert res_analyze.status_code == 200
    analysis = res_analyze.json()["analysis"]
    assert "business_goal" in analysis
    assert len(analysis["approval_requirements"]) >= 1

    # 2. Decompose Process
    res_decompose = client.post(
        "/api/v1/decompose-process",
        json={"analysis": analysis, "max_stages": 6},
    )
    assert res_decompose.status_code == 200
    plan = res_decompose.json()["plan"]
    assert len(plan["stages"]) >= 3
    assert len(plan["steps"]) >= 4

    # 3. Synthesize Workflow Definition
    res_generate = client.post(
        "/api/v1/generate-workflow",
        json={"analysis": analysis, "process_plan": plan, "name": "E2E Laptop Flow"},
    )
    assert res_generate.status_code == 200
    wf = res_generate.json()["workflow"]
    assert wf["trigger"]["id"] == "trigger_1"

    # 4. Multi-Stage Comprehensive Validation
    res_validate = client.post(
        "/api/v1/comprehensive-validate",
        json={"workflow": wf, "requirement_text": REQUIREMENT_TEXT},
    )
    assert res_validate.status_code == 200
    val_report = res_validate.json()["report"]
    assert val_report["is_valid"] is True
    assert val_report["deterministic_passed"] is True

    # 5. Simulation Dry-Run
    res_simulate = client.post(
        "/api/v1/simulate",
        json={"workflow": wf, "initial_inputs": {"request_id": "req_high_value", "cost": 85000}},
    )
    assert res_simulate.status_code == 200
    sim = res_simulate.json()["simulation"]
    assert sim["status"] == "completed"
    assert sim["approval_simulated"] is True

    # 6. Production Execution (High Value -> Pauses for Human Approval)
    res_start = client.post(
        "/api/v1/executions/start",
        json={"workflow": wf, "initial_inputs": {"request_id": "req_high_value", "cost": 85000}},
    )
    assert res_start.status_code == 201
    execution = res_start.json()["execution"]
    exec_id = execution["id"]
    assert execution["status"] == "paused"
    approval_id = execution["pending_approval_id"]
    assert approval_id is not None

    # 7. Check Pending Approval in Queue
    res_approvals = client.get("/api/v1/approvals/pending")
    assert res_approvals.status_code == 200
    pending_list = res_approvals.json()["approvals"]
    assert any(a["id"] == approval_id for a in pending_list)

    # 8. Human Reviewer Approves and Resumes Execution
    res_resume = client.post(
        f"/api/v1/executions/{exec_id}/resume",
        json={"reviewer_id": "manager_priya@techcorp.io", "decision": "approved", "comments": "Approved"},
    )
    assert res_resume.status_code == 200
    resumed_exec = res_resume.json()["execution"]
    assert resumed_exec["status"] == "completed"
    assert resumed_exec["completed_at"] is not None

    # 9. Audit Log
    res_audit = client.post(
        "/api/v1/audit/logs",
        json={
            "actor_type": "user",
            "actor_id": "manager_priya",
            "action": "WORKFLOW_EXECUTED_COMPLETED",
            "resource_type": "workflow_execution",
            "resource_id": exec_id,
        },
    )
    assert res_audit.status_code == 201

    res_logs = client.get("/api/v1/audit/logs")
    assert res_logs.status_code == 200
    assert any(l["resource_id"] == exec_id for l in res_logs.json()["logs"])
