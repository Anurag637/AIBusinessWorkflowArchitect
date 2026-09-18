"""
Schemas for Dynamic Manager-Specialist Orchestration.
Tracks agent thoughts, specialist delegations, tool observations, and session states.
"""

from typing import Dict, Any, List, Optional, Literal
from pydantic import BaseModel, Field
import uuid
from datetime import datetime, timezone


class AgentAction(BaseModel):
    """Action or sub-task to be executed by a specialist or tool."""
    specialist: Literal["policy", "data", "approval", "action", "manager"]
    action: str = Field(description="Action name supported by specialist or tool")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Parameters for the action")
    reasoning: str = Field(description="Why the manager agent chose this specialist/action")


class AgentObservation(BaseModel):
    """Observation returned after specialist or tool execution."""
    success: bool
    data: Dict[str, Any] = Field(default_factory=dict)
    summary: str = Field(description="Human-readable summary of what was found or done")
    error: Optional[str] = None
    requires_human: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentThoughtStep(BaseModel):
    """A single step in the Reason-Act-Observe loop."""
    step_number: int
    agent_role: str  # "manager", "policy_specialist", "data_specialist", "approval_specialist", "action_specialist"
    thought: str = Field(description="Internal reasoning of the agent at this step")
    action_taken: Optional[AgentAction] = None
    observation: Optional[AgentObservation] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class OrchestrationSession(BaseModel):
    """Full state of an autonomous orchestration session."""
    session_id: str = Field(default_factory=lambda: f"orch_{uuid.uuid4().hex[:10]}")
    goal: str = Field(description="The user's high-level business goal")
    domain_hint: Optional[str] = None
    status: Literal["in_progress", "awaiting_approval", "completed", "failed"] = "in_progress"
    steps: List[AgentThoughtStep] = Field(default_factory=list)
    accumulated_context: Dict[str, Any] = Field(default_factory=dict, description="Structured facts collected so far")
    pending_approval: Optional[Dict[str, Any]] = None
    final_outcome: Optional[Dict[str, Any]] = None
    summary_message: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class OrchestrateRequest(BaseModel):
    goal: str = Field(..., min_length=5, description="Business requirement or goal in natural language")
    initial_context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Initial parameters (e.g. employee_id, cost, item)")
    domain_hint: Optional[str] = None
    max_steps: Optional[int] = Field(default=8, ge=1, le=20)


class OrchestrateResponse(BaseModel):
    status: str = "success"
    session: OrchestrationSession


class ResumeSessionRequest(BaseModel):
    session_id: str
    approval_decision: Literal["approved", "rejected"]
    approver_comments: Optional[str] = "Approved via Agent Console"
    reviewer_role: Optional[str] = "manager"


class ResumeSessionResponse(BaseModel):
    status: str = "success"
    session: OrchestrationSession
