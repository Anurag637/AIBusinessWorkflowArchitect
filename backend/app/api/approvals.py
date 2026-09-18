"""
Human Approval API endpoints.
- GET /api/v1/approvals/pending: Fetch pending approvals for current role
- GET /api/v1/approvals/{approval_id}: Fetch specific approval details
- POST /api/v1/approvals/{approval_id}/decide: Submit approval/rejection decision
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.models.entities import ApprovalStatus
from app.services.approval import get_approval_service, ApprovalRecord
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/approvals", tags=["Approvals"])


class CreateApprovalRequest(BaseModel):
    workflow_execution_id: str
    step_id: str
    approver_role: str = "manager"
    requested_by: str = "system"
    context_data: Optional[Dict[str, Any]] = None


class DecisionRequest(BaseModel):
    reviewer_id: str = Field(..., description="ID or email of the reviewer")
    decision: ApprovalStatus = Field(..., description="approved, rejected, or modification_requested")
    comments: Optional[str] = None
    modification_details: Optional[str] = None


class ApprovalResponse(BaseModel):
    status: str = "success"
    approval: ApprovalRecord


class ApprovalListResponse(BaseModel):
    status: str = "success"
    total: int
    approvals: List[ApprovalRecord]


from app.api.audit import add_audit_log
from app.services.executor import get_executor


@router.get(
    "",
    response_model=ApprovalListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all approval requests with optional status filter",
)
async def list_approvals(status: Optional[str] = None, role: Optional[str] = None):
    service = get_approval_service()
    if status and status.lower() == "pending":
        records = service.list_pending(approver_role=role)
    else:
        records = service.list_all(status=status, approver_role=role)
    return ApprovalListResponse(
        status="success",
        total=len(records),
        approvals=records,
    )


@router.get(
    "/pending",
    response_model=ApprovalListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all pending approval requests",
)
async def list_pending_approvals(role: Optional[str] = None):
    service = get_approval_service()
    pending = service.list_pending(approver_role=role)
    return ApprovalListResponse(
        status="success",
        total=len(pending),
        approvals=pending,
    )


@router.get(
    "/{approval_id}",
    response_model=ApprovalResponse,
    status_code=status.HTTP_200_OK,
    summary="Get details of a specific approval request",
)
async def get_approval_details(approval_id: str):
    service = get_approval_service()
    record = service.get_by_id(approval_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approval request '{approval_id}' not found",
        )
    return ApprovalResponse(status="success", approval=record)


@router.post(
    "/{approval_id}/decide",
    response_model=ApprovalResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit approval or rejection decision and advance execution",
)
async def decide_approval(approval_id: str, payload: DecisionRequest):
    service = get_approval_service()
    record = service.submit_decision(
        approval_id=approval_id,
        reviewer_id=payload.reviewer_id,
        decision=payload.decision,
        comments=payload.comments,
        modification_details=payload.modification_details,
    )
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approval request '{approval_id}' not found",
        )

    # Automatically advance the paused workflow execution if linked
    if record.workflow_execution_id:
        try:
            executor = get_executor()
            executor.resume_execution(
                execution_id=record.workflow_execution_id,
                reviewer_id=payload.reviewer_id,
                decision=payload.decision,
                comments=payload.comments,
            )
            logger.info(f"Automatically resumed execution '{record.workflow_execution_id}' following {payload.decision} decision.")
        except Exception as e:
            logger.error(f"Error resuming execution '{record.workflow_execution_id}': {e}", exc_info=True)

    # Record immutable audit log
    add_audit_log(
        action=f"APPROVAL_{payload.decision.value.upper()}",
        resource_type="approval",
        resource_id=approval_id,
        actor_type="human",
        actor_id=payload.reviewer_id,
        metadata={
            "execution_id": record.workflow_execution_id,
            "step_id": record.step_id,
            "decision": payload.decision.value,
            "comments": payload.comments,
        },
    )

    return ApprovalResponse(status="success", approval=record)


@router.post(
    "",
    response_model=ApprovalResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new approval request",
)
async def create_approval(payload: CreateApprovalRequest):
    service = get_approval_service()
    record = service.create_request(
        workflow_execution_id=payload.workflow_execution_id,
        step_id=payload.step_id,
        approver_role=payload.approver_role,
        requested_by=payload.requested_by,
        context_data=payload.context_data,
    )

    add_audit_log(
        action="APPROVAL_REQUESTED",
        resource_type="approval",
        resource_id=record.id,
        actor_type="system",
        actor_id=payload.requested_by,
        metadata={
            "execution_id": payload.workflow_execution_id,
            "step_id": payload.step_id,
            "role": payload.approver_role,
        },
    )

    return ApprovalResponse(status="success", approval=record)

