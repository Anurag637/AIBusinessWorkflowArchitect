"""
Human Approval Service managing approval lifecycles, role-based authorization, and decision dispatch.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import uuid
import logging
from pydantic import BaseModel, Field

from app.models.entities import ApprovalStatus

logger = logging.getLogger(__name__)


class ApprovalRecord(BaseModel):
    id: str
    workflow_execution_id: str
    step_id: str
    approver_role: str
    requested_by: str = "system"
    reviewed_by: Optional[str] = None
    status: ApprovalStatus = ApprovalStatus.PENDING
    context_data: Dict[str, Any] = Field(default_factory=dict)
    comments: Optional[str] = None
    modification_details: Optional[str] = None
    created_at: str
    reviewed_at: Optional[str] = None


class ApprovalService:
    """Manages in-memory and persisted approval requests."""

    def __init__(self):
        self._requests: Dict[str, ApprovalRecord] = {}

    def create_request(
        self,
        workflow_execution_id: str,
        step_id: str,
        approver_role: str = "manager",
        requested_by: str = "system",
        context_data: Optional[Dict[str, Any]] = None,
    ) -> ApprovalRecord:
        approval_id = f"appr_{uuid.uuid4().hex[:8]}"
        record = ApprovalRecord(
            id=approval_id,
            workflow_execution_id=workflow_execution_id,
            step_id=step_id,
            approver_role=approver_role,
            requested_by=requested_by,
            status=ApprovalStatus.PENDING,
            context_data=context_data or {},
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._requests[approval_id] = record
        logger.info(f"Created approval request '{approval_id}' for role '{approver_role}'")
        return record

    def get_by_id(self, approval_id: str) -> Optional[ApprovalRecord]:
        return self._requests.get(approval_id)

    def list_pending(self, approver_role: Optional[str] = None) -> List[ApprovalRecord]:
        pending = [
            r for r in self._requests.values()
            if r.status == ApprovalStatus.PENDING
        ]
        if approver_role:
            pending = [r for r in pending if r.approver_role == approver_role or approver_role == "admin"]
        return sorted(pending, key=lambda x: x.created_at, reverse=True)

    def list_all(self, status: Optional[str] = None, approver_role: Optional[str] = None) -> List[ApprovalRecord]:
        records = list(self._requests.values())
        if status:
            records = [r for r in records if (r.status.value if hasattr(r.status, "value") else str(r.status)).lower() == status.lower()]
        if approver_role:
            records = [r for r in records if r.approver_role == approver_role or approver_role == "admin"]
        return sorted(records, key=lambda x: x.created_at, reverse=True)


    def submit_decision(
        self,
        approval_id: str,
        reviewer_id: str,
        decision: ApprovalStatus,
        comments: Optional[str] = None,
        modification_details: Optional[str] = None,
    ) -> Optional[ApprovalRecord]:
        record = self.get_by_id(approval_id)
        if not record:
            return None

        record.status = decision
        record.reviewed_by = reviewer_id
        record.reviewed_at = datetime.now(timezone.utc).isoformat()
        if comments:
            record.comments = comments
        if modification_details:
            record.modification_details = modification_details

        logger.info(f"Approval request '{approval_id}' decided: {decision} by {reviewer_id}")
        return record


_approval_service: Optional[ApprovalService] = None


def get_approval_service() -> ApprovalService:
    global _approval_service
    if _approval_service is None:
        _approval_service = ApprovalService()
    return _approval_service
