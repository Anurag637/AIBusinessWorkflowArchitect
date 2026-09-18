"""
Pydantic schemas for Workflow Definitions, Steps, and validation contracts.
Strict data contract adhering to docs/workflow-schema.md.
"""

from typing import Optional, List, Dict, Any, Union
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict, model_validator


class StepType(str, Enum):
    TRIGGER = "TRIGGER"
    DATABASE = "DATABASE"
    RAG = "RAG"
    DECISION = "DECISION"
    NOTIFICATION = "NOTIFICATION"
    APPROVAL = "APPROVAL"
    TRANSFORM = "TRANSFORM"
    END = "END"


class AllowedTool(str, Enum):
    DATABASE = "database"
    RAG = "rag"
    NOTIFICATION = "notification"
    APPROVAL = "approval"


class RetryConfig(BaseModel):
    max_retries: int = Field(default=2, ge=0, le=5)
    retry_delay_seconds: int = Field(default=5, ge=1, le=300)


class TransformConfig(BaseModel):
    operation: str = Field(..., description="E.g. merge, filter, map")
    fields: List[str] = Field(default_factory=list)


class InputParam(BaseModel):
    name: str
    type: str = "string"
    required: bool = True
    description: Optional[str] = None
    default: Optional[Any] = None


class TriggerDefinition(BaseModel):
    id: str = "trigger_1"
    type: StepType = StepType.TRIGGER
    event: str
    description: Optional[str] = None
    outputs: List[str] = Field(default_factory=list)


class RequiredApproval(BaseModel):
    step_id: str
    approver_role: str = "manager"
    condition: Optional[str] = None


class WorkflowMetadata(BaseModel):
    created_by: str = "workflow_architect_agent"
    domain: Optional[str] = None
    estimated_duration_seconds: Optional[int] = None
    tags: List[str] = Field(default_factory=list)


class WorkflowStep(BaseModel):
    """Represents a single step in a workflow graph."""
    model_config = ConfigDict(extra="allow")

    id: str = Field(..., description="Unique step identifier")
    name: str = Field(..., description="Human-readable step name")
    type: StepType = Field(..., description="Step type from allowlist")
    description: Optional[str] = None

    # Tool execution details
    tool: Optional[str] = None
    action: Optional[str] = None

    # Step inputs and outputs
    inputs: Dict[str, Any] = Field(default_factory=dict)
    outputs: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)

    # Specific step types
    condition: Optional[str] = None  # For DECISION
    if_true: Optional[str] = None    # For DECISION
    if_false: Optional[str] = None   # For DECISION
    approver_role: Optional[str] = None  # For APPROVAL
    transform: Optional[Union[TransformConfig, Dict[str, Any]]] = None  # For TRANSFORM

    # Execution controls
    timeout_seconds: int = Field(default=30, ge=1, le=600)
    retry_config: Optional[RetryConfig] = None


class WorkflowDefinition(BaseModel):
    """Complete workflow definition object."""
    model_config = ConfigDict(extra="allow")

    workflow_id: str
    name: str
    description: Optional[str] = None
    version: int = Field(default=1, ge=1)
    trigger: TriggerDefinition
    inputs: List[InputParam] = Field(default_factory=list)
    steps: List[WorkflowStep] = Field(default_factory=list)
    metadata: Optional[WorkflowMetadata] = None
    required_approvals: List[RequiredApproval] = Field(default_factory=list)
