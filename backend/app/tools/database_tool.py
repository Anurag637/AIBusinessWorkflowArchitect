"""
Database Tool for controlled queries and mutations.
Strictly disallows raw SQL and only exposes pre-approved parametrized actions.
"""

from typing import Dict, Any, Optional
from app.tools.base import BaseTool, ToolActionSpec, ToolParameter, ToolExecutionResult


# In-memory mock database store for demo & simulation
MOCK_EMPLOYEES = {
    "emp_101": {"id": "emp_101", "name": "Rahul Sharma", "email": "rahul@techcorp.io", "department": "Engineering", "role": "Software Engineer"},
    "emp_102": {"id": "emp_102", "name": "Priya Patel", "email": "priya@techcorp.io", "department": "Design", "role": "Product Designer"},
    "emp_103": {"id": "emp_103", "name": "Amit Kumar", "email": "amit@techcorp.io", "department": "Sales", "role": "Account Executive"},
}

MOCK_EQUIPMENT_REQUESTS = {
    "req_standard": {
        "request_id": "req_standard",
        "employee_id": "emp_101",
        "item": "Dell UltraSharp Monitor 27-inch",
        "category": "peripherals",
        "cost": 18000,
        "urgency": "medium",
        "status": "pending_review",
    },
    "req_high_value": {
        "request_id": "req_high_value",
        "employee_id": "emp_101",
        "item": "Apple MacBook Pro 16 M3 Max",
        "category": "laptop",
        "cost": 85000,
        "urgency": "high",
        "status": "pending_review",
    },
}

DECISION_RECORDS: Dict[str, Dict[str, Any]] = {}


class DatabaseTool(BaseTool):
    name = "database"
    description = "Secure business database operations (strictly parameterized)"
    category = "storage"

    def get_supported_actions(self) -> Dict[str, ToolActionSpec]:
        return {
            "get_employee": ToolActionSpec(
                name="get_employee",
                description="Retrieve employee profile by ID",
                parameters={
                    "employee_id": ToolParameter(name="employee_id", type="string", required=True, description="Employee identifier"),
                },
                required_permissions=["read:employee"],
            ),
            "get_equipment_request": ToolActionSpec(
                name="get_equipment_request",
                description="Retrieve equipment request details by request ID",
                parameters={
                    "request_id": ToolParameter(name="request_id", type="string", required=True, description="Equipment request ID"),
                },
                required_permissions=["read:equipment_request"],
            ),
            "record_decision": ToolActionSpec(
                name="record_decision",
                description="Record the final approval or fulfillment decision",
                parameters={
                    "request_id": ToolParameter(name="request_id", type="string", required=True, description="Request ID to update"),
                    "decision": ToolParameter(name="decision", type="string", required=True, description="approved, rejected, or fulfilled"),
                    "policy_reference": ToolParameter(name="policy_reference", type="string", required=False, description="Source policy doc"),
                },
                required_permissions=["write:decision"],
            ),
        }

    def execute(
        self,
        action: str,
        inputs: Dict[str, Any],
        is_simulation: bool = False,
        context: Optional[Dict[str, Any]] = None,
    ) -> ToolExecutionResult:
        valid, err = self.validate_action(action, inputs)
        if not valid:
            return ToolExecutionResult(success=False, error=err, simulated=is_simulation)

        if action == "get_employee":
            emp_id = inputs.get("employee_id")
            emp = MOCK_EMPLOYEES.get(emp_id, {
                "id": emp_id,
                "name": f"Employee {emp_id}",
                "email": f"{emp_id}@example.com",
                "department": "Engineering",
                "role": "Team Member"
            })
            return ToolExecutionResult(
                success=True,
                data={"employee": emp},
                simulated=is_simulation,
            )

        elif action == "get_equipment_request":
            req_id = inputs.get("request_id")
            # Return high value if requested or matching, else standard
            if req_id == "req_high_value" or "high" in str(req_id):
                req = dict(MOCK_EQUIPMENT_REQUESTS["req_high_value"])
            elif req_id in MOCK_EQUIPMENT_REQUESTS:
                req = dict(MOCK_EQUIPMENT_REQUESTS[req_id])
            else:
                # Default fallback request
                req = {
                    "request_id": req_id,
                    "employee_id": "emp_101",
                    "item": "Dell Latitude 5540 Laptop",
                    "category": "laptop",
                    "cost": 22000,
                    "status": "pending_review",
                }

            # Merge cost from trigger/initial_inputs if provided by the user
            # This ensures DECISION conditions evaluate the user's actual cost
            if context and isinstance(context, dict):
                trigger_data = context.get("trigger", {})
                if isinstance(trigger_data, dict) and "cost" in trigger_data:
                    req["cost"] = trigger_data["cost"]
                # Also check top-level context for cost override
                if "cost" in context and context["cost"] != req["cost"]:
                    req["cost"] = context["cost"]

            return ToolExecutionResult(
                success=True,
                data={"request_details": req},
                simulated=is_simulation,
            )

        elif action == "record_decision":
            req_id = inputs.get("request_id")
            decision = inputs.get("decision")
            policy_ref = inputs.get("policy_reference", "standard_policy")

            record = {
                "request_id": req_id,
                "decision": decision,
                "policy_reference": policy_ref,
                "timestamp": "2026-09-18T12:00:00Z",
                "status": "recorded",
            }
            if not is_simulation:
                DECISION_RECORDS[str(req_id)] = record

            return ToolExecutionResult(
                success=True,
                data={"decision_record": record},
                simulated=is_simulation,
            )

        return ToolExecutionResult(success=False, error=f"Unhandled action: {action}")
