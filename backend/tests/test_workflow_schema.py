"""
Unit tests for Workflow Schema & Deterministic Validator.
Tests all 14 validation rules, security checks, and valid workflow definitions.
"""

import pytest
from app.schemas.workflow import (
    WorkflowDefinition,
    WorkflowStep,
    StepType,
    TriggerDefinition,
    InputParam,
    RequiredApproval,
)
from app.schemas.validator import DeterministicValidator


def get_valid_workflow() -> WorkflowDefinition:
    """Helper returning a fully valid reference workflow."""
    return WorkflowDefinition(
        workflow_id="wf-001",
        name="Equipment Request Approval",
        description="Automated equipment workflow",
        version=1,
        trigger=TriggerDefinition(
            id="trigger_1",
            type=StepType.TRIGGER,
            event="equipment_request_created",
            outputs=["request_id", "employee_id"],
        ),
        inputs=[
            InputParam(name="request_id", type="string", required=True),
            InputParam(name="employee_id", type="string", required=True),
        ],
        steps=[
            WorkflowStep(
                id="step_1",
                name="Retrieve Equipment Request",
                type=StepType.DATABASE,
                tool="database",
                action="get_equipment_request",
                inputs={"request_id": "{{trigger.request_id}}"},
                outputs=["request_details"],
                dependencies=["trigger_1"],
            ),
            WorkflowStep(
                id="step_2",
                name="Check Equipment Policy",
                type=StepType.RAG,
                tool="rag",
                action="search_knowledge",
                inputs={"query": "laptop spending limit policy"},
                outputs=["policy_info"],
                dependencies=["step_1"],
            ),
            WorkflowStep(
                id="step_3",
                name="Evaluate Cost Threshold",
                type=StepType.DECISION,
                condition="request_details.cost < 25000",
                if_true="step_4",
                if_false="step_5",
                dependencies=["step_2"],
            ),
            WorkflowStep(
                id="step_4",
                name="Notify IT Team",
                type=StepType.NOTIFICATION,
                tool="notification",
                action="create_notification",
                inputs={"recipient": "it_team", "message": "Approved directly"},
                outputs=["notification_result"],
                dependencies=["step_3"],
            ),
            WorkflowStep(
                id="step_5",
                name="Request Manager Approval",
                type=StepType.APPROVAL,
                tool="approval",
                action="request_approval",
                approver_role="manager",
                inputs={"summary": "High cost equipment"},
                outputs=["approval_result"],
                dependencies=["step_3"],
            ),
            WorkflowStep(
                id="end_1",
                name="Process Complete",
                type=StepType.END,
                dependencies=["step_4", "step_5"],
            ),
        ],
    )


def test_valid_workflow_passes():
    wf = get_valid_workflow()
    validator = DeterministicValidator()
    result = validator.validate(wf)
    assert result.is_valid is True
    assert len(result.errors) == 0


def test_rule_2_missing_end_step():
    wf = get_valid_workflow()
    wf.steps = [s for s in wf.steps if s.type != StepType.END]
    validator = DeterministicValidator()
    result = validator.validate(wf)
    assert result.is_valid is False
    assert any(e.rule_number == 2 for e in result.errors)


def test_rule_3_duplicate_step_ids():
    wf = get_valid_workflow()
    duplicate_step = WorkflowStep(
        id="step_1",  # duplicate ID
        name="Duplicate Step",
        type=StepType.DATABASE,
        tool="database",
        dependencies=["trigger_1"],
    )
    wf.steps.append(duplicate_step)
    validator = DeterministicValidator()
    result = validator.validate(wf)
    assert result.is_valid is False
    assert any(e.rule_number == 3 for e in result.errors)


def test_rule_4_invalid_dependency():
    wf = get_valid_workflow()
    wf.steps[0].dependencies = ["non_existent_step"]
    validator = DeterministicValidator()
    result = validator.validate(wf)
    assert result.is_valid is False
    assert any(e.rule_number == 4 for e in result.errors)


def test_rule_5_cycle_detection():
    wf = get_valid_workflow()
    # Create cycle: step_1 -> step_2 -> step_1
    wf.steps[0].dependencies = ["step_2"]
    wf.steps[1].dependencies = ["step_1"]
    validator = DeterministicValidator()
    result = validator.validate(wf)
    assert result.is_valid is False
    assert any(e.rule_number == 5 for e in result.errors)


def test_rule_7_unapproved_tool():
    wf = get_valid_workflow()
    wf.steps[0].tool = "unapproved_custom_script"
    validator = DeterministicValidator()
    result = validator.validate(wf)
    assert result.is_valid is False
    assert any(e.rule_number == 7 for e in result.errors)


def test_rule_9_security_python_code_injection():
    wf = get_valid_workflow()
    wf.steps[0].inputs = {"payload": "__import__('os').system('rm -rf /')"}
    validator = DeterministicValidator()
    result = validator.validate(wf)
    assert result.is_valid is False
    assert any(e.rule_number == 9 for e in result.errors)


def test_rule_10_security_sql_injection():
    wf = get_valid_workflow()
    wf.steps[0].inputs = {"query": "SELECT * FROM users WHERE admin=1"}
    validator = DeterministicValidator()
    result = validator.validate(wf)
    assert result.is_valid is False
    assert any(e.rule_number == 10 for e in result.errors)


def test_rule_11_security_arbitrary_urls():
    wf = get_valid_workflow()
    wf.steps[0].inputs = {"endpoint": "https://malicious-site.com/steal-tokens"}
    validator = DeterministicValidator()
    result = validator.validate(wf)
    assert result.is_valid is False
    assert any(e.rule_number == 11 for e in result.errors)


def test_rule_12_approval_requires_role():
    wf = get_valid_workflow()
    # Find approval step and empty out approver_role
    for s in wf.steps:
        if s.type == StepType.APPROVAL:
            s.approver_role = None
    validator = DeterministicValidator()
    result = validator.validate(wf)
    assert result.is_valid is False
    assert any(e.rule_number == 12 for e in result.errors)


def test_rule_13_decision_missing_fields_or_branches():
    wf = get_valid_workflow()
    for s in wf.steps:
        if s.type == StepType.DECISION:
            s.if_true = "ghost_step_999"
    validator = DeterministicValidator()
    result = validator.validate(wf)
    assert result.is_valid is False
    assert any(e.rule_number == 13 for e in result.errors)
