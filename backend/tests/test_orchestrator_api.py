"""
API integration tests for Autonomous Orchestration endpoints.
"""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_api_orchestrate_endpoint_standard_goal():
    payload = {
        "goal": "Procure a monitor for emp_101. Verify company policy and notify IT team.",
        "initial_context": {"request_id": "req_standard", "cost": 18000},
    }
    response = client.post("/api/v1/orchestrate", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "success"
    session = data["session"]
    assert session["status"] == "completed"
    assert len(session["steps"]) >= 2
    assert "summary_message" in session


def test_api_orchestrate_approval_and_resume_flow():
    # 1. Orchestrate high-value request requiring approval
    init_payload = {
        "goal": "Purchase expensive developer workstation ₹85,000 for Rahul Sharma. Check policy limits and get approval.",
        "initial_context": {"request_id": "req_high_value", "cost": 85000},
    }
    response = client.post("/api/v1/orchestrate", json=init_payload)
    assert response.status_code == 200

    session = response.json()["session"]
    session_id = session["session_id"]
    assert session["status"] == "awaiting_approval"

    # 2. Get session trace
    trace_resp = client.get(f"/api/v1/orchestrate/{session_id}")
    assert trace_resp.status_code == 200
    assert trace_resp.json()["session_id"] == session_id

    # 3. Resume with approval
    resume_payload = {
        "session_id": session_id,
        "approval_decision": "approved",
        "approver_comments": "Approved for Q3 tech upgrade.",
        "reviewer_role": "Engineering Manager",
    }
    resume_resp = client.post("/api/v1/orchestrate/resume", json=resume_payload)
    assert resume_resp.status_code == 200

    final_session = resume_resp.json()["session"]
    assert final_session["status"] == "completed"
    assert any("action" in step["agent_role"] for step in final_session["steps"])

    # 4. List sessions
    list_resp = client.get("/api/v1/orchestrate/sessions")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 1
