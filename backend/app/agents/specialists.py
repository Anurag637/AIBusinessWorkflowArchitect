"""
Specialist Sub-Agents for Dynamic Orchestration.
Each specialist operates under strict boundaries, calling the Tool Registry
to perform deterministic lookups, RAG policy checks, approvals, and mutations.
"""

import logging
from typing import Dict, Any, Optional
from app.tools.registry import get_tool_registry
from app.schemas.orchestrator import AgentAction, AgentObservation

logger = logging.getLogger(__name__)


class PolicySpecialist:
    """Specialist agent responsible for corporate policy, compliance rules, and threshold checks."""

    def __init__(self):
        self.tool_registry = get_tool_registry()

    def execute(self, action: AgentAction, context: Dict[str, Any]) -> AgentObservation:
        action_name = action.action
        params = action.parameters

        if action_name == "search_policy":
            query = params.get("query", "equipment laptop purchase spending limits")
            category = params.get("category", "equipment")
            res = self.tool_registry.execute_tool(
                tool_name="rag",
                action="search_knowledge",
                inputs={"query": query, "category": category, "top_k": 3},
                context=context,
            )

            if not res.success:
                return AgentObservation(
                    success=False,
                    summary=f"Policy search failed: {res.error}",
                    error=res.error,
                )

            policy_info = res.data.get("policy_info", {})
            matched = policy_info.get("matched_policies", [])
            summary_text = (
                f"Policy matched from {policy_info.get('source', 'handbook')}: {policy_info.get('summary', 'Standard policy applies.')}"
            )
            return AgentObservation(
                success=True,
                data={"policy_info": policy_info, "matched_count": len(matched)},
                summary=summary_text,
                metadata={"source": policy_info.get("source")},
            )

        elif action_name == "evaluate_compliance":
            cost = params.get("cost") or context.get("cost") or 25000
            threshold = params.get("threshold", 25000)
            requires_approval = cost > threshold

            return AgentObservation(
                success=True,
                data={
                    "cost": cost,
                    "threshold": threshold,
                    "requires_approval": requires_approval,
                    "rule": f"Purchases exceeding ₹{threshold:,} require managerial sign-off.",
                },
                summary=(
                    f"Cost ₹{cost:,} exceeds ₹{threshold:,} limit. Manager approval required."
                    if requires_approval
                    else f"Cost ₹{cost:,} is within ₹{threshold:,} limit. Direct IT fulfillment permitted."
                ),
            )

        return AgentObservation(
            success=False,
            summary=f"Unsupported policy action: {action_name}",
            error=f"Action '{action_name}' not implemented in PolicySpecialist",
        )


class DataSpecialist:
    """Specialist agent responsible for retrieving and formatting database records."""

    def __init__(self):
        self.tool_registry = get_tool_registry()

    def execute(self, action: AgentAction, context: Dict[str, Any]) -> AgentObservation:
        action_name = action.action
        params = action.parameters

        if action_name == "get_employee":
            emp_id = params.get("employee_id") or context.get("employee_id", "emp_101")
            res = self.tool_registry.execute_tool(
                tool_name="database",
                action="get_employee",
                inputs={"employee_id": emp_id},
                context=context,
            )
            if not res.success:
                return AgentObservation(success=False, summary=f"Failed to fetch employee: {res.error}", error=res.error)

            emp = res.data.get("employee", {})
            return AgentObservation(
                success=True,
                data={"employee": emp},
                summary=f"Retrieved employee {emp.get('name', emp_id)} ({emp.get('role', 'Staff')} in {emp.get('department', 'General')}).",
            )

        elif action_name == "get_request_details":
            req_id = params.get("request_id") or context.get("request_id", "req_standard")
            res = self.tool_registry.execute_tool(
                tool_name="database",
                action="get_equipment_request",
                inputs={"request_id": req_id},
                context=context,
            )
            if not res.success:
                return AgentObservation(success=False, summary=f"Failed to fetch request: {res.error}", error=res.error)

            req = res.data.get("request_details", {})
            return AgentObservation(
                success=True,
                data={"request_details": req},
                summary=f"Retrieved request '{req.get('item', 'Item')}' with estimated cost ₹{req.get('cost', 0):,}.",
            )

        return AgentObservation(
            success=False,
            summary=f"Unsupported data action: {action_name}",
            error=f"Action '{action_name}' not implemented in DataSpecialist",
        )


class ApprovalSpecialist:
    """Specialist agent responsible for Human-in-the-loop sign-offs and reviews."""

    def __init__(self):
        self.tool_registry = get_tool_registry()

    def execute(self, action: AgentAction, context: Dict[str, Any]) -> AgentObservation:
        action_name = action.action
        params = action.parameters

        if action_name == "request_human_approval":
            role = params.get("approver_role", "manager")
            summary = params.get("summary") or context.get("approval_summary", "Request requires managerial review")
            res = self.tool_registry.execute_tool(
                tool_name="approval",
                action="request_approval",
                inputs={"approver_role": role, "request_summary": summary},
                context=context,
            )
            if not res.success:
                return AgentObservation(success=False, summary=f"Approval dispatch failed: {res.error}", error=res.error)

            appr_res = res.data.get("approval_result", {})
            is_sim = appr_res.get("simulated", False)
            status = appr_res.get("status", "pending_approval")

            return AgentObservation(
                success=True,
                data={"approval_request": appr_res},
                summary=f"Approval request created for '{role}'. Current status: {status}.",
                requires_human=not is_sim and status == "pending_approval",
            )

        elif action_name == "check_approval_status":
            app_id = params.get("approval_id") or context.get("approval_id", "appr_101")
            res = self.tool_registry.execute_tool(
                tool_name="approval",
                action="check_approval",
                inputs={"approval_id": app_id},
                context=context,
            )
            if not res.success:
                return AgentObservation(success=False, summary=f"Approval check failed: {res.error}", error=res.error)

            status_data = res.data.get("approval_status", {})
            return AgentObservation(
                success=True,
                data={"approval_status": status_data},
                summary=f"Approval '{app_id}' status is: {status_data.get('status', 'unknown')}.",
            )

        return AgentObservation(
            success=False,
            summary=f"Unsupported approval action: {action_name}",
            error=f"Action '{action_name}' not implemented in ApprovalSpecialist",
        )


class ActionSpecialist:
    """Specialist agent responsible for notifications, tickets, and state updates."""

    def __init__(self):
        self.tool_registry = get_tool_registry()

    def execute(self, action: AgentAction, context: Dict[str, Any]) -> AgentObservation:
        action_name = action.action
        params = action.parameters

        if action_name == "send_notification":
            recipient = params.get("recipient", "it_team@techcorp.io")
            message = params.get("message", "Request has been processed.")
            subject = params.get("subject", "Workflow Notification")

            res = self.tool_registry.execute_tool(
                tool_name="notification",
                action="create_notification",
                inputs={"recipient": recipient, "message": message, "subject": subject},
                context=context,
            )
            if not res.success:
                return AgentObservation(success=False, summary=f"Notification failed: {res.error}", error=res.error)

            return AgentObservation(
                success=True,
                data={"notification": res.data.get("notification_result")},
                summary=f"Notification successfully sent to {recipient} with subject '{subject}'.",
            )

        elif action_name == "record_decision":
            req_id = params.get("request_id") or context.get("request_id", "req_standard")
            decision = params.get("decision", "approved")
            policy_ref = params.get("policy_reference", "equipment_policy.md")

            res = self.tool_registry.execute_tool(
                tool_name="database",
                action="record_decision",
                inputs={"request_id": req_id, "decision": decision, "policy_reference": policy_ref},
                context=context,
            )
            if not res.success:
                return AgentObservation(success=False, summary=f"Failed to record decision: {res.error}", error=res.error)

            return AgentObservation(
                success=True,
                data={"decision_record": res.data.get("decision_record")},
                summary=f"Final decision '{decision}' recorded in database for request {req_id}.",
            )

        return AgentObservation(
            success=False,
            summary=f"Unsupported action specialist action: {action_name}",
            error=f"Action '{action_name}' not implemented in ActionSpecialist",
        )
