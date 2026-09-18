"""
Workflow Execution API endpoints.
- POST /api/v1/executions/start: Start production workflow execution
- GET /api/v1/executions/{execution_id}: Get live execution state & step progress
- POST /api/v1/executions/{execution_id}/resume: Resume a paused execution with approval decision
- POST /api/v1/executions/{execution_id}/cancel: Cancel an ongoing execution
"""

from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.schemas.workflow import WorkflowDefinition
from app.services.executor import get_executor, WorkflowExecutionState
from app.models.entities import ApprovalStatus
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/executions", tags=["Executions"])


class StartExecutionRequest(BaseModel):
    workflow: WorkflowDefinition
    initial_inputs: Optional[Dict[str, Any]] = None
    actor_id: str = "system"


class ResumeExecutionRequest(BaseModel):
    reviewer_id: str = Field(..., description="ID or email of approving user")
    decision: ApprovalStatus = Field(..., description="approved or rejected")
    comments: Optional[str] = None


class ExecutionResponse(BaseModel):
    status: str = "success"
    execution: WorkflowExecutionState


class ExecutionListResponse(BaseModel):
    status: str = "success"
    total: int
    executions: List[WorkflowExecutionState]


@router.get(
    "",
    response_model=ExecutionListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all workflow executions",
)
async def list_executions_endpoint():
    executor = get_executor()
    items = executor.list_executions()
    return ExecutionListResponse(status="success", total=len(items), executions=items)


@router.post(
    "/start",
    response_model=ExecutionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start production workflow execution",
)
async def start_execution_endpoint(payload: StartExecutionRequest):
    executor = get_executor()
    state = executor.start_execution(
        workflow=payload.workflow,
        initial_inputs=payload.initial_inputs,
        actor_id=payload.actor_id,
    )
    return ExecutionResponse(status="success", execution=state)



@router.get(
    "/{execution_id}",
    response_model=ExecutionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get execution status and step traces",
)
async def get_execution_endpoint(execution_id: str):
    executor = get_executor()
    state = executor.get_execution(execution_id)
    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution '{execution_id}' not found",
        )
    return ExecutionResponse(status="success", execution=state)


@router.post(
    "/{execution_id}/resume",
    response_model=ExecutionResponse,
    status_code=status.HTTP_200_OK,
    summary="Resume execution after human approval",
)
async def resume_execution_endpoint(execution_id: str, payload: ResumeExecutionRequest):
    executor = get_executor()
    state = executor.resume_execution(
        execution_id=execution_id,
        reviewer_id=payload.reviewer_id,
        decision=payload.decision,
        comments=payload.comments,
    )
    if not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Execution '{execution_id}' cannot be resumed (not found or not in PAUSED state)",
        )
    return ExecutionResponse(status="success", execution=state)


@router.post(
    "/{execution_id}/cancel",
    response_model=ExecutionResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel active execution",
)
async def cancel_execution_endpoint(execution_id: str):
    executor = get_executor()
    state = executor.cancel_execution(execution_id)
    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution '{execution_id}' not found",
        )
    return ExecutionResponse(status="success", execution=state)
