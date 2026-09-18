"""
Workflow Execution Engine for production execution.
Supports DAG step dependency resolution, retry policies, pauses for human approval, and resume on sign-off.
"""

import time
import uuid
import logging
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timezone
from pydantic import BaseModel, Field

from app.schemas.workflow import WorkflowDefinition, WorkflowStep, StepType
from app.tools.registry import get_tool_registry, ToolRegistry
from app.services.simulation import interpolate_variables, evaluate_condition_safely
from app.services.approval import get_approval_service, ApprovalService
from app.models.entities import ExecutionStatus, StepStatus, ApprovalStatus

logger = logging.getLogger(__name__)


class ExecutionStepState(BaseModel):
    step_id: str
    step_name: str
    step_type: str
    status: StepStatus = StepStatus.PENDING
    inputs: Dict[str, Any] = Field(default_factory=dict)
    outputs: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    retry_count: int = 0
    duration_ms: int = 0


class WorkflowExecutionState(BaseModel):
    id: str
    workflow_id: str
    workflow_name: str
    status: ExecutionStatus = ExecutionStatus.PENDING
    started_at: str
    completed_at: Optional[str] = None
    total_duration_ms: int = 0
    steps: List[ExecutionStepState] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict)
    pending_approval_id: Optional[str] = None
    error_message: Optional[str] = None


class ExecutionEngine:
    """Production execution engine for workflow graphs."""

    def __init__(
        self,
        registry: Optional[ToolRegistry] = None,
        approval_service: Optional[ApprovalService] = None,
    ):
        self.registry = registry or get_tool_registry()
        self.approval_service = approval_service or get_approval_service()
        self._active_executions: Dict[str, WorkflowExecutionState] = {}
        self._workflow_definitions: Dict[str, WorkflowDefinition] = {}

    def start_execution(
        self,
        workflow: WorkflowDefinition,
        initial_inputs: Optional[Dict[str, Any]] = None,
        actor_id: str = "system",
    ) -> WorkflowExecutionState:
        exec_id = f"exec_{uuid.uuid4().hex[:8]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        initial_context = {
            "trigger": initial_inputs or {
                "request_id": f"req_{uuid.uuid4().hex[:6]}",
                "employee_id": actor_id,
            }
        }

        # Initialize steps
        step_states = [
            ExecutionStepState(
                step_id=s.id,
                step_name=s.name,
                step_type=s.type.value if hasattr(s.type, "value") else str(s.type),
                status=StepStatus.PENDING,
            )
            for s in workflow.steps
        ]

        state = WorkflowExecutionState(
            id=exec_id,
            workflow_id=workflow.workflow_id,
            workflow_name=workflow.name,
            status=ExecutionStatus.RUNNING,
            started_at=now_iso,
            steps=step_states,
            context=initial_context,
        )

        self._active_executions[exec_id] = state
        self._workflow_definitions[exec_id] = workflow

        try:
            from app.api.audit import add_audit_log
            add_audit_log(
                action="EXECUTION_STARTED",
                resource_type="execution",
                resource_id=exec_id,
                actor_type="user",
                actor_id=actor_id,
                metadata={"workflow_id": workflow.workflow_id, "workflow_name": workflow.name, "inputs": initial_inputs},
            )
        except Exception as e:
            logger.warning(f"Audit log failed: {e}")

        # Run steps until completion or pause
        self._advance_execution(exec_id)
        return self._active_executions[exec_id]

    def get_execution(self, execution_id: str) -> Optional[WorkflowExecutionState]:
        return self._active_executions.get(execution_id)

    def list_executions(self) -> List[WorkflowExecutionState]:
        return sorted(
            list(self._active_executions.values()),
            key=lambda x: x.started_at,
            reverse=True,
        )


    def resume_execution(
        self, execution_id: str, reviewer_id: str, decision: ApprovalStatus, comments: Optional[str] = None
    ) -> Optional[WorkflowExecutionState]:
        state = self.get_execution(execution_id)
        if not state or state.status != ExecutionStatus.PAUSED:
            return None

        # Resolve pending approval
        if state.pending_approval_id:
            self.approval_service.submit_decision(
                approval_id=state.pending_approval_id,
                reviewer_id=reviewer_id,
                decision=decision,
                comments=comments,
            )

        if decision == ApprovalStatus.APPROVED:
            state.status = ExecutionStatus.RUNNING
            # Mark the approval step completed
            for s in state.steps:
                if s.step_type == StepType.APPROVAL.value and s.status == StepStatus.RUNNING:
                    s.status = StepStatus.COMPLETED
                    s.outputs = {"approval_result": {"status": "approved", "reviewer": reviewer_id}}
                    state.context[s.step_id] = s.outputs
                    state.context["approval_result"] = s.outputs["approval_result"]

            state.pending_approval_id = None
            self._advance_execution(execution_id)
        else:
            state.status = ExecutionStatus.FAILED
            state.error_message = f"Execution stopped: Human approval rejected by {reviewer_id}"
            state.completed_at = datetime.now(timezone.utc).isoformat()

        return state

    def cancel_execution(self, execution_id: str) -> Optional[WorkflowExecutionState]:
        state = self.get_execution(execution_id)
        if not state:
            return None
        state.status = ExecutionStatus.CANCELLED
        state.completed_at = datetime.now(timezone.utc).isoformat()
        return state

    def _advance_execution(self, execution_id: str):
        state = self._active_executions[execution_id]
        workflow = self._workflow_definitions[execution_id]

        step_map = {s.id: s for s in workflow.steps}
        step_state_map = {s.step_id: s for s in state.steps}

        completed_step_ids = {"trigger_1"}
        skipped_step_ids = set()

        for s in state.steps:
            if s.status == StepStatus.COMPLETED:
                completed_step_ids.add(s.step_id)
            elif s.status == StepStatus.SKIPPED:
                skipped_step_ids.add(s.step_id)

        start_time = time.perf_counter()

        while state.status == ExecutionStatus.RUNNING:
            candidate: Optional[WorkflowStep] = None
            for s in workflow.steps:
                cur_state = step_state_map[s.id]
                if cur_state.status != StepStatus.PENDING:
                    continue

                deps = s.dependencies or []
                if all(d in completed_step_ids or d in skipped_step_ids for d in deps):
                    candidate = s
                    break

            if candidate is None:
                # No more runnable steps
                break

            step = candidate
            step_record = step_state_map[step.id]
            step_record.status = StepStatus.RUNNING
            step_record.started_at = datetime.now(timezone.utc).isoformat()
            step_start = time.perf_counter()

            # Skip check for branches
            if any(d in skipped_step_ids for d in step.dependencies) and not any(d in completed_step_ids for d in step.dependencies):
                step_record.status = StepStatus.SKIPPED
                skipped_step_ids.add(step.id)
                continue

            interpolated_inputs = interpolate_variables(step.inputs or {}, state.context)
            step_record.inputs = interpolated_inputs
            s_type = step.type.value if hasattr(step.type, "value") else str(step.type)

            # Handle step types
            if s_type == StepType.DECISION.value:
                cond_ctx = dict(state.context)
                for k, v in state.context.items():
                    if isinstance(v, dict):
                        cond_ctx.update(v)

                cond_val = evaluate_condition_safely(step.condition or "True", cond_ctx)
                step_record.outputs = {"condition_result": cond_val}
                step_record.status = StepStatus.COMPLETED
                completed_step_ids.add(step.id)

                if cond_val:
                    if step.if_false and step.if_false in step_map:
                        step_state_map[step.if_false].status = StepStatus.SKIPPED
                        skipped_step_ids.add(step.if_false)
                else:
                    if step.if_true and step.if_true in step_map:
                        step_state_map[step.if_true].status = StepStatus.SKIPPED
                        skipped_step_ids.add(step.if_true)

            elif s_type == StepType.APPROVAL.value:
                # PAUSE execution and create real approval request
                approver_role = step.approver_role or "manager"
                summary = interpolated_inputs.get("request_summary") or step.description or "Review required"

                req = self.approval_service.create_request(
                    workflow_execution_id=execution_id,
                    step_id=step.id,
                    approver_role=approver_role,
                    requested_by="Workflow Engine",
                    context_data={"inputs": interpolated_inputs, "context": state.context},
                )

                state.pending_approval_id = req.id
                state.status = ExecutionStatus.PAUSED
                step_record.duration_ms = int((time.perf_counter() - step_start) * 1000)
                logger.info(f"Execution '{execution_id}' PAUSED for human approval (id: {req.id})")
                try:
                    from app.api.audit import add_audit_log
                    add_audit_log(
                        action="EXECUTION_PAUSED",
                        resource_type="execution",
                        resource_id=execution_id,
                        actor_type="system",
                        actor_id="executor",
                        metadata={"step_id": step.id, "approval_id": req.id, "approver_role": approver_role},
                    )
                except Exception:
                    pass
                return


            elif s_type in (StepType.DATABASE.value, StepType.RAG.value, StepType.NOTIFICATION.value):
                tool_name = step.tool or s_type.lower()
                action = step.action or (
                    "search_knowledge" if tool_name == "rag"
                    else "create_notification" if tool_name == "notification"
                    else "get_equipment_request"
                )

                # Retry loop
                max_retries = step.retry_config.max_retries if step.retry_config else 1
                success = False
                res_data = {}
                last_err = None

                for attempt in range(max_retries + 1):
                    res = self.registry.execute_tool(
                        tool_name=tool_name,
                        action=action,
                        inputs=interpolated_inputs,
                        is_simulation=False,
                        context=state.context,
                    )
                    if res.success:
                        success = True
                        res_data = res.data
                        break
                    else:
                        last_err = res.error
                        step_record.retry_count = attempt + 1

                if success:
                    step_record.status = StepStatus.COMPLETED
                    step_record.outputs = res_data
                    completed_step_ids.add(step.id)
                    state.context[step.id] = res_data
                    for k, v in res_data.items():
                        state.context[k] = v
                else:
                    step_record.status = StepStatus.FAILED
                    step_record.error = last_err
                    state.status = ExecutionStatus.FAILED
                    state.error_message = f"Step '{step.id}' failed after {step_record.retry_count} attempts: {last_err}"
                    break

            elif s_type == StepType.TRANSFORM.value:
                step_record.status = StepStatus.COMPLETED
                step_record.outputs = {"transformed_data": interpolated_inputs}
                completed_step_ids.add(step.id)
                state.context[step.id] = step_record.outputs

            elif s_type == StepType.END.value:
                step_record.status = StepStatus.COMPLETED
                step_record.outputs = {"status": "workflow_completed"}
                completed_step_ids.add(step.id)

            step_record.completed_at = datetime.now(timezone.utc).isoformat()
            step_record.duration_ms = int((time.perf_counter() - step_start) * 1000)

        # Finalize if not paused
        if state.status == ExecutionStatus.RUNNING:
            all_done = all(
                s.status in (StepStatus.COMPLETED, StepStatus.SKIPPED)
                for s in state.steps
            )
            if all_done:
                state.status = ExecutionStatus.COMPLETED
                state.completed_at = datetime.now(timezone.utc).isoformat()
                state.total_duration_ms = int((time.perf_counter() - start_time) * 1000)
                try:
                    from app.api.audit import add_audit_log
                    add_audit_log(
                        action="EXECUTION_COMPLETED",
                        resource_type="execution",
                        resource_id=execution_id,
                        actor_type="system",
                        actor_id="executor",
                        metadata={"duration_ms": state.total_duration_ms, "steps_count": len(state.steps)},
                    )
                except Exception:
                    pass



_executor: Optional[ExecutionEngine] = None


def get_executor() -> ExecutionEngine:
    global _executor
    if _executor is None:
        _executor = ExecutionEngine()
    return _executor
