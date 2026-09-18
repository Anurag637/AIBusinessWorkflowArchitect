"""
Unit and integration tests for Dynamic Manager Agent and Specialist sub-agents.
"""

import pytest
from app.agents.manager_agent import ManagerAgent
from app.agents.specialists import (
    PolicySpecialist,
    DataSpecialist,
    ApprovalSpecialist,
    ActionSpecialist,
)
from app.schemas.orchestrator import AgentAction


def test_specialists_execution():
    policy = PolicySpecialist()
    data = DataSpecialist()
    approval = ApprovalSpecialist()
    action = ActionSpecialist()

    # 1. Test Policy Specialist RAG search & compliance
    pol_obs = policy.execute(
        AgentAction(specialist="policy", action="search_policy", parameters={"query": "laptop purchase limit"}, reasoning="test"),
        context={},
    )
    assert pol_obs.success is True
    assert "policy_info" in pol_obs.data

    comp_obs = policy.execute(
        AgentAction(specialist="policy", action="evaluate_compliance", parameters={"cost": 75000, "threshold": 25000}, reasoning="test"),
        context={},
    )
    assert comp_obs.success is True
    assert comp_obs.data["requires_approval"] is True

    # 2. Test Data Specialist
    data_obs = data.execute(
        AgentAction(specialist="data", action="get_employee", parameters={"employee_id": "emp_101"}, reasoning="test"),
        context={},
    )
    assert data_obs.success is True
    assert "Rahul" in data_obs.data["employee"]["name"]

    req_obs = data.execute(
        AgentAction(specialist="data", action="get_request_details", parameters={"request_id": "req_standard"}, reasoning="test"),
        context={},
    )
    assert req_obs.success is True
    assert "request_details" in req_obs.data

    # 3. Test Action Specialist
    notif_obs = action.execute(
        AgentAction(
            specialist="action",
            action="send_notification",
            parameters={"recipient": "it@techcorp.io", "subject": "Test", "message": "Test message"},
            reasoning="test",
        ),
        context={},
    )
    assert notif_obs.success is True


def test_manager_agent_standard_request_autonomous_lifecycle():
    manager = ManagerAgent()
    goal = "I want to purchase a standard keyboard for Rahul. Check policy and fulfill if valid."
    session = manager.orchestrate(
        goal=goal,
        initial_context={"request_id": "req_standard", "cost": 18000},
    )

    assert session.session_id.startswith("orch_")
    assert len(session.steps) >= 3
    # Standard request <= 25000 should complete without pausing for approval
    assert session.status == "completed"
    assert session.final_outcome is not None
    assert "completed" in session.final_outcome.get("status", "")


def test_manager_agent_high_value_request_approval_lifecycle():
    manager = ManagerAgent()
    goal = "I want to purchase a high-end MacBook Pro for Rahul (Cost ₹85,000). Check policy and get manager signoff."
    
    # Run first phase -> should pause for human approval
    session = manager.orchestrate(
        goal=goal,
        initial_context={"request_id": "req_high_value", "cost": 85000},
    )

    assert session.status == "awaiting_approval"
    assert session.pending_approval is not None
    assert "manager" in session.pending_approval.get("approver_role", "")

    # Human Approver approves the request -> Resume workflow
    resumed_session = manager.resume(
        session_id=session.session_id,
        approval_decision="approved",
        approver_comments="Budget cleared by IT Director",
        reviewer_role="Director",
    )

    assert resumed_session.status == "completed"
    assert resumed_session.accumulated_context.get("approval_status") == "approved"
    # Ensure IT notification and decision record were executed post-approval
    step_roles = [s.agent_role for s in resumed_session.steps]
    assert "human_approver" in step_roles
    assert any("action" in r for r in step_roles)
