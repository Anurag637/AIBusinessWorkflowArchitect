"""
Human Approval Tool for workflow intervention, pauses, and reviewer sign-offs.
"""

from typing import Dict, Any, Optional
import uuid
from app.tools.base import BaseTool, ToolActionSpec, ToolParameter, ToolExecutionResult

ACTIVE_APPROVAL_REQUESTS: Dict[str, Dict[str, Any]] = {}


class HumanApprovalTool(BaseTool):
    name = "approval"
    description = "Handles asynchronous human approval requests and reviewer decisions"
    category = "governance"

    def get_supported_actions(self) -> Dict[str, ToolActionSpec]:
        return {
            "request_approval": ToolActionSpec(
                name="request_approval",
                description="Request manual sign-off from designated role",
                parameters={
                    "approver_role": ToolParameter(name="approver_role", type="string", required=True, description="Role permitted to approve (manager, director, etc.)"),
                    "request_summary": ToolParameter(name="request_summary", type="string", required=True, description="Summary details for the reviewer"),
                    "workflow_id": ToolParameter(name="workflow_id", type="string", required=False, description="Associated workflow ID"),
                },
                required_permissions=["request:approval"],
            ),
            "check_approval": ToolActionSpec(
                name="check_approval",
                description="Check status of a pending approval",
                parameters={
                    "approval_id": ToolParameter(name="approval_id", type="string", required=True, description="Approval request identifier"),
                },
                required_permissions=["check:approval"],
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

        if action == "request_approval":
            role = inputs.get("approver_role", "manager")
            summary = inputs.get("request_summary", "")
            app_id = f"appr_{uuid.uuid4().hex[:8]}"

            if is_simulation:
                # In simulation mode, mock auto-approval
                result_payload = {
                    "approval_id": app_id,
                    "status": "approved",
                    "approver_role": role,
                    "reviewed_by": f"simulated_{role}",
                    "comments": "Auto-approved in simulation dry run",
                    "decision": "approved",
                    "simulated": True,
                }
            else:
                # Real mode: state becomes pending approval
                result_payload = {
                    "approval_id": app_id,
                    "status": "pending_approval",
                    "approver_role": role,
                    "request_summary": summary,
                    "workflow_id": inputs.get("workflow_id"),
                    "decision": None,
                    "simulated": False,
                }
                ACTIVE_APPROVAL_REQUESTS[app_id] = result_payload

            return ToolExecutionResult(
                success=True,
                data={"approval_result": result_payload},
                simulated=is_simulation,
            )

        elif action == "check_approval":
            app_id = inputs.get("approval_id")
            rec = ACTIVE_APPROVAL_REQUESTS.get(app_id, {
                "approval_id": app_id,
                "status": "approved" if is_simulation else "pending_approval",
                "simulated": is_simulation,
            })
            return ToolExecutionResult(
                success=True,
                data={"approval_status": rec},
                simulated=is_simulation,
            )

        return ToolExecutionResult(success=False, error=f"Unhandled action: {action}")
