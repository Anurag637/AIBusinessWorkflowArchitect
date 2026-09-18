"""
Unit & security tests for Multi-Stage Comprehensive Validator and security guardrails.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.schemas.workflow import WorkflowDefinition, StepType
from app.services.validator import get_validator
from tests.test_workflow_schema import get_valid_workflow


def test_comprehensive_validator_valid():
    wf = get_valid_workflow()
    validator = get_validator()

    requirement = "When an employee requests a laptop, check policy and request manager approval."
    report = validator.validate(wf, requirement_text=requirement)

    assert report.is_valid is True
    assert report.deterministic_passed is True
    assert report.semantic_passed is True
    assert report.fidelity_score >= 0.9
    assert len(report.errors) == 0


def test_comprehensive_validator_semantic_omission():
    wf = get_valid_workflow()
    # Remove APPROVAL step
    wf.steps = [s for s in wf.steps if s.type != StepType.APPROVAL]
    # Update decision branch and end node dependencies so deterministic rules pass
    for s in wf.steps:
        if s.id == "step_3":
            s.if_false = "step_4"
        if s.type == StepType.END:
            s.dependencies = ["step_4"]

    validator = get_validator()
    requirement = "Manager approval is strictly required for high cost hardware."
    report = validator.validate(wf, requirement_text=requirement)

    # Deterministic passes, but semantic warning for omission
    assert report.deterministic_passed is True
    assert report.semantic_passed is False
    assert any("approval" in w.message.lower() for w in report.warnings)


def test_security_malicious_sql_injection():
    wf = get_valid_workflow()
    wf.steps[0].inputs = {"filter": "1=1; DROP TABLE users; --"}

    validator = get_validator()
    report = validator.validate(wf)

    assert report.is_valid is False
    assert report.deterministic_passed is False
    assert any(e.rule_number == 10 for e in report.errors)


def test_security_malicious_os_execution():
    wf = get_valid_workflow()
    wf.steps[0].inputs = {"cmd": "__import__('subprocess').run(['curl', 'bad.com'])"}

    validator = get_validator()
    report = validator.validate(wf)

    assert report.is_valid is False
    assert report.deterministic_passed is False
    assert any(e.rule_number == 9 for e in report.errors)


def test_comprehensive_validate_api():
    client = TestClient(app)
    wf = get_valid_workflow()

    payload = {
        "workflow": wf.model_dump(),
        "requirement_text": "Check equipment policy and request manager approval.",
    }
    response = client.post("/api/v1/comprehensive-validate", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "success"
    assert data["report"]["is_valid"] is True
    assert data["report"]["deterministic_passed"] is True
