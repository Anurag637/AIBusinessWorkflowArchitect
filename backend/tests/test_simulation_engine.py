"""
Unit & integration tests for Simulation Engine.
Tests variable interpolation, condition evaluation, branching, and simulation API.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.simulation import SimulationEngine, evaluate_condition_safely, interpolate_variables
from tests.test_workflow_schema import get_valid_workflow


def test_evaluate_condition_safely():
    ctx = {"request_details": {"cost": 18000, "item": "Monitor"}}
    assert evaluate_condition_safely("request_details.cost < 25000", ctx) is True
    assert evaluate_condition_safely("request_details.cost >= 25000", ctx) is False

    ctx_high = {"request_details": {"cost": 55000}}
    assert evaluate_condition_safely("request_details.cost < 25000", ctx_high) is False


def test_interpolate_variables():
    ctx = {
        "trigger": {"request_id": "req_123"},
        "step_1": {"request_details": {"item": "MacBook Pro", "cost": 90000}},
    }
    inputs = {
        "req": "{{trigger.request_id}}",
        "msg": "Item {{step_1.request_details.item}} costs ₹{{step_1.request_details.cost}}",
    }
    res = interpolate_variables(inputs, ctx)
    assert res["req"] == "req_123"
    assert res["msg"] == "Item MacBook Pro costs ₹90000"


def test_simulation_engine_standard_branch():
    wf = get_valid_workflow()
    engine = SimulationEngine()

    result = engine.simulate(wf, initial_inputs={"request_id": "req_standard", "cost": 18000})

    assert result.status == "completed"
    assert len(result.steps_executed) >= 4

    step_ids = [s.step_id for s in result.steps_executed]
    assert "step_1" in step_ids
    assert "step_2" in step_ids
    assert "step_3" in step_ids
    assert "step_4" in step_ids  # direct IT notification branch

    # High value approval should not have executed on standard request
    executed_approval = [s for s in result.steps_executed if s.step_id == "step_5"]
    assert len(executed_approval) == 0


def test_simulation_engine_high_value_branch():
    wf = get_valid_workflow()
    engine = SimulationEngine()

    # Pass high value request
    result = engine.simulate(wf, initial_inputs={"request_id": "req_high_value", "cost": 85000})

    assert result.status == "completed"
    step_ids = [s.step_id for s in result.steps_executed]
    assert "step_1" in step_ids
    assert "step_3" in step_ids
    assert "step_5" in step_ids  # manager approval branch was taken!
    assert result.approval_simulated is True


def test_simulate_api_endpoint():
    client = TestClient(app)
    wf = get_valid_workflow()

    payload = {
        "workflow": wf.model_dump(),
        "initial_inputs": {"request_id": "req_standard", "cost": 18000},
    }
    response = client.post("/api/v1/simulate", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "success"
    assert "simulation" in data
    assert data["simulation"]["status"] == "completed"
    assert len(data["simulation"]["steps_executed"]) >= 4
