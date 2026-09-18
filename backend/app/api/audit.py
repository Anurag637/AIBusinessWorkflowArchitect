"""
Audit Log API endpoints.
- GET /api/v1/audit/logs: Retrieve chronological immutable audit trail
- POST /api/v1/audit/logs: Append audit log entry
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import uuid
from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from app.models.entities import ActorType

router = APIRouter(prefix="/api/v1/audit", tags=["Audit"])


class AuditLogRecord(BaseModel):
    id: str
    actor_type: str
    actor_id: str
    action: str
    resource_type: str
    resource_id: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str


# In-memory audit log store
AUDIT_ENTRIES: List[AuditLogRecord] = [
    AuditLogRecord(
        id="audit_init_1",
        actor_type=ActorType.SYSTEM.value,
        actor_id="system",
        action="SYSTEM_INITIALIZED",
        resource_type="system",
        resource_id="sys_1",
        metadata={"version": "1.0.0"},
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
]


class CreateAuditLogRequest(BaseModel):
    actor_type: str = "agent"
    actor_id: str
    action: str
    resource_type: str
    resource_id: str
    metadata: Optional[Dict[str, Any]] = None


class AuditLogListResponse(BaseModel):
    status: str = "success"
    total: int
    logs: List[AuditLogRecord]


def add_audit_log(
    action: str,
    resource_type: str,
    resource_id: str,
    actor_type: str = "system",
    actor_id: str = "system",
    metadata: Optional[Dict[str, Any]] = None,
) -> AuditLogRecord:
    entry = AuditLogRecord(
        id=f"audit_{uuid.uuid4().hex[:8]}",
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        metadata=metadata or {},
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    AUDIT_ENTRIES.append(entry)
    return entry


@router.get(
    "/logs",
    response_model=AuditLogListResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve audit trail",
)
async def list_audit_logs(
    resource_type: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = 100,
):
    logs = list(AUDIT_ENTRIES)
    if resource_type:
        logs = [l for l in logs if l.resource_type == resource_type]
    if action:
        logs = [l for l in logs if action.lower() in l.action.lower()]
    logs.reverse()
    return AuditLogListResponse(
        status="success",
        total=len(logs[:limit]),
        logs=logs[:limit],
    )


@router.post(
    "/logs",
    response_model=AuditLogRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Append audit log entry",
)
async def record_audit_log(payload: CreateAuditLogRequest):
    return add_audit_log(
        action=payload.action,
        resource_type=payload.resource_type,
        resource_id=payload.resource_id,
        actor_type=payload.actor_type,
        actor_id=payload.actor_id,
        metadata=payload.metadata,
    )

