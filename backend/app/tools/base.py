"""
Base Tool class and data structures for Tool Registry.
Enforces execution safety, parameter validation, simulation mode, and audit tracing.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field


class ToolParameter(BaseModel):
    name: str
    type: str  # string, integer, number, boolean, object
    required: bool = True
    description: str = ""
    default: Optional[Any] = None


class ToolActionSpec(BaseModel):
    name: str
    description: str
    parameters: Dict[str, ToolParameter]
    required_permissions: List[str] = Field(default_factory=list)


class ToolExecutionResult(BaseModel):
    success: bool
    data: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    simulated: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BaseTool(ABC):
    """Abstract base class for all workflow executable tools."""

    name: str
    description: str
    category: str

    @abstractmethod
    def get_supported_actions(self) -> Dict[str, ToolActionSpec]:
        """Return schema definitions for all supported actions."""
        pass

    def validate_action(self, action_name: str, inputs: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        actions = self.get_supported_actions()
        if action_name not in actions:
            return False, f"Action '{action_name}' is not supported by tool '{self.name}'. Supported: {list(actions.keys())}"

        spec = actions[action_name]
        for param_name, param_def in spec.parameters.items():
            if param_def.required and param_name not in inputs:
                return False, f"Missing required parameter '{param_name}' for action '{action_name}'"

        return True, None

    @abstractmethod
    def execute(
        self,
        action: str,
        inputs: Dict[str, Any],
        is_simulation: bool = False,
        context: Optional[Dict[str, Any]] = None,
    ) -> ToolExecutionResult:
        """Execute the tool action in real or simulated mode."""
        pass
