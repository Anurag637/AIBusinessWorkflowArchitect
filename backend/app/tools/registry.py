"""
Tool Registry for centralized registration, discovery, authorization, and execution.
"""

from typing import Dict, Any, List, Optional
import logging
from app.tools.base import BaseTool, ToolExecutionResult
from app.tools.database_tool import DatabaseTool
from app.tools.rag_tool import RAGTool
from app.tools.notification_tool import NotificationTool
from app.tools.approval_tool import HumanApprovalTool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry maintaining all approved workflow tools."""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._register_default_tools()

    def _register_default_tools(self):
        self.register(DatabaseTool())
        self.register(RAGTool())
        self.register(NotificationTool())
        self.register(HumanApprovalTool())

    def register(self, tool: BaseTool):
        self._tools[tool.name.lower()] = tool
        logger.info(f"Registered tool: '{tool.name}' ({tool.category})")

    def get_tool(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name.lower())

    def list_tools(self) -> List[Dict[str, Any]]:
        results = []
        for name, tool in self._tools.items():
            actions_spec = tool.get_supported_actions()
            results.append({
                "name": tool.name,
                "description": tool.description,
                "category": tool.category,
                "actions": {
                    act_name: act_spec.model_dump()
                    for act_name, act_spec in actions_spec.items()
                },
            })
        return results

    def execute_tool(
        self,
        tool_name: str,
        action: str,
        inputs: Dict[str, Any],
        is_simulation: bool = False,
        context: Optional[Dict[str, Any]] = None,
        user_permissions: Optional[List[str]] = None,
    ) -> ToolExecutionResult:
        tool = self.get_tool(tool_name)
        if not tool:
            return ToolExecutionResult(
                success=False,
                error=f"Tool '{tool_name}' is not registered in Tool Registry.",
                simulated=is_simulation,
            )

        actions = tool.get_supported_actions()
        if action not in actions:
            return ToolExecutionResult(
                success=False,
                error=f"Action '{action}' is not supported by tool '{tool_name}'. Available: {list(actions.keys())}",
                simulated=is_simulation,
            )

        spec = actions[action]
        # Permission check if permissions passed
        if user_permissions is not None:
            for req_perm in spec.required_permissions:
                if req_perm not in user_permissions and "admin" not in user_permissions:
                    return ToolExecutionResult(
                        success=False,
                        error=f"Permission denied: missing '{req_perm}' for action '{action}'",
                        simulated=is_simulation,
                    )

        return tool.execute(action, inputs, is_simulation=is_simulation, context=context)


# Global singleton instance
_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry
