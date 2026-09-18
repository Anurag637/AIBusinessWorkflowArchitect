"""
Unit tests for Tool Registry, BaseTool, and the 4 registered tools.
"""

import pytest
from app.tools.registry import get_tool_registry, ToolRegistry
from app.tools.database_tool import DatabaseTool
from app.tools.rag_tool import RAGTool
from app.tools.notification_tool import NotificationTool
from app.tools.approval_tool import HumanApprovalTool


def test_registry_initialization():
    registry = get_tool_registry()
    tools = registry.list_tools()
    assert len(tools) == 4

    names = {t["name"] for t in tools}
    assert names == {"database", "rag", "notification", "approval"}


def test_database_tool_actions():
    registry = get_tool_registry()

    # 1. get_employee
    res1 = registry.execute_tool("database", "get_employee", {"employee_id": "emp_101"})
    assert res1.success is True
    assert res1.data["employee"]["name"] == "Rahul Sharma"

    # 2. get_equipment_request
    res2 = registry.execute_tool("database", "get_equipment_request", {"request_id": "req_standard"})
    assert res2.success is True
    assert res2.data["request_details"]["cost"] == 18000

    # 3. record_decision
    res3 = registry.execute_tool("database", "record_decision", {"request_id": "req_1", "decision": "approved"})
    assert res3.success is True
    assert res3.data["decision_record"]["decision"] == "approved"


def test_rag_tool_action():
    registry = get_tool_registry()
    res = registry.execute_tool("rag", "search_knowledge", {"query": "laptop equipment spending limit"})
    assert res.success is True
    assert "policy_info" in res.data


def test_notification_tool_simulation_and_real():
    registry = get_tool_registry()

    # Simulation mode
    res_sim = registry.execute_tool(
        "notification",
        "create_notification",
        {"recipient": "it_team", "message": "Simulated message"},
        is_simulation=True,
    )
    assert res_sim.success is True
    assert res_sim.simulated is True
    assert res_sim.data["notification_result"]["status"] == "simulated_delivered"

    # Real mode
    res_real = registry.execute_tool(
        "notification",
        "create_notification",
        {"recipient": "it_team", "message": "Real message"},
        is_simulation=False,
    )
    assert res_real.success is True
    assert res_real.simulated is False
    assert res_real.data["notification_result"]["status"] == "delivered"


def test_approval_tool_simulation_and_real():
    registry = get_tool_registry()

    # Simulation mode auto-approves
    res_sim = registry.execute_tool(
        "approval",
        "request_approval",
        {"approver_role": "manager", "request_summary": "Laptop for ₹35,000"},
        is_simulation=True,
    )
    assert res_sim.success is True
    assert res_sim.simulated is True
    assert res_sim.data["approval_result"]["decision"] == "approved"

    # Real mode marks pending
    res_real = registry.execute_tool(
        "approval",
        "request_approval",
        {"approver_role": "manager", "request_summary": "Laptop for ₹35,000"},
        is_simulation=False,
    )
    assert res_real.success is True
    assert res_real.simulated is False
    assert res_real.data["approval_result"]["status"] == "pending_approval"


def test_permission_enforcement():
    registry = get_tool_registry()

    # Denied when required permission missing
    res_denied = registry.execute_tool(
        "database",
        "record_decision",
        {"request_id": "req_1", "decision": "approved"},
        user_permissions=["read:employee"],  # lacks write:decision
    )
    assert res_denied.success is False
    assert "Permission denied" in res_denied.error

    # Allowed when correct permission or admin
    res_allowed = registry.execute_tool(
        "database",
        "record_decision",
        {"request_id": "req_1", "decision": "approved"},
        user_permissions=["write:decision"],
    )
    assert res_allowed.success is True


def test_unregistered_tool_or_action():
    registry = get_tool_registry()

    res_tool = registry.execute_tool("unknown_tool", "do_something", {})
    assert res_tool.success is False
    assert "not registered" in res_tool.error

    res_act = registry.execute_tool("database", "drop_all_tables", {})
    assert res_act.success is False
    assert "not supported" in res_act.error
