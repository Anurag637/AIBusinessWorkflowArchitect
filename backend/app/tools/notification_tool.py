"""
Notification Tool for sending team notifications, alerts, and operational messages.
"""

from typing import Dict, Any, Optional, List
import uuid
from app.tools.base import BaseTool, ToolActionSpec, ToolParameter, ToolExecutionResult

DISPATCHED_NOTIFICATIONS: List[Dict[str, Any]] = []


class NotificationTool(BaseTool):
    name = "notification"
    description = "Dispatches email, Slack, and in-app notifications"
    category = "communication"

    def get_supported_actions(self) -> Dict[str, ToolActionSpec]:
        return {
            "create_notification": ToolActionSpec(
                name="create_notification",
                description="Send a notification to a user or department channel",
                parameters={
                    "recipient": ToolParameter(name="recipient", type="string", required=True, description="User email or team alias (e.g. it_team)"),
                    "message": ToolParameter(name="message", type="string", required=True, description="Notification body"),
                    "subject": ToolParameter(name="subject", type="string", required=False, default="Workflow Notification", description="Subject line"),
                    "channel": ToolParameter(name="channel", type="string", required=False, default="in_app", description="Delivery channel"),
                },
                required_permissions=["send:notification"],
            )
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

        notification_id = f"notif_{uuid.uuid4().hex[:8]}"
        notification_payload = {
            "notification_id": notification_id,
            "recipient": inputs.get("recipient"),
            "subject": inputs.get("subject", "Workflow Notification"),
            "message": inputs.get("message"),
            "channel": inputs.get("channel", "in_app"),
            "simulated": is_simulation,
            "status": "delivered" if not is_simulation else "simulated_delivered",
        }

        if not is_simulation:
            DISPATCHED_NOTIFICATIONS.append(notification_payload)

        return ToolExecutionResult(
            success=True,
            data={"notification_result": notification_payload},
            simulated=is_simulation,
            metadata={"recipient": inputs.get("recipient")},
        )
