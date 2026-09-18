"""
Unit & integration tests for Requirement Analyzer Agent and API endpoint.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.agents.requirement_analyzer import analyze_requirement
from app.schemas.requirement import RequirementAnalysis


SAMPLE_REQUIREMENT = (
    "When an employee requests a laptop, check the company policy. "
    "If the cost is below ₹25,000, IT can process it. "
    "If it is above ₹25,000, manager approval is required."
)


def test_analyze_requirement_agent_direct():
    analysis = analyze_requirement(SAMPLE_REQUIREMENT, domain_hint="equipment_procurement")
    assert isinstance(analysis, RequirementAnalysis)
    assert analysis.business_goal is not None
    assert len(analysis.inputs) >= 1
    assert len(analysis.actors) >= 2

    # Check for manager and it_team in actors
    roles = [actor.role for actor in analysis.actors]
    assert any("manager" in r for r in roles) or any("it" in r for r in roles)

    # Check approval requirement
    assert len(analysis.approval_requirements) >= 1
    assert "manager" in analysis.approval_requirements[0].role

    # Check business rules extracted
    assert len(analysis.business_rules) >= 1
    assert analysis.confidence_score > 0.0


def test_analyze_requirement_api_endpoint():
    client = TestClient(app)
    payload = {
        "requirement_text": SAMPLE_REQUIREMENT,
        "domain_hint": "it_procurement",
    }
    response = client.post("/api/v1/analyze-requirement", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "success"
    assert "analysis" in data
    analysis = data["analysis"]
    assert "business_goal" in analysis
    assert "approval_requirements" in analysis
    assert len(analysis["approval_requirements"]) >= 1


def test_analyze_requirement_validation_error():
    client = TestClient(app)
    # Requirement text too short (< 10 chars)
    payload = {"requirement_text": "too short"}
    response = client.post("/api/v1/analyze-requirement", json=payload)
    assert response.status_code == 422
