"""
SQLAlchemy models for all database entities.

Entities:
1. User
2. Workflow
3. WorkflowVersion
4. WorkflowExecution
5. ExecutionStep
6. ApprovalRequest
7. KnowledgeDocument
8. AuditLog
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    String,
    Text,
    Integer,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    JSON,
    Enum as SAEnum,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.models.database import Base


# ─── Enums ────────────────────────────────────────────────────────────────────

import enum


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    ANALYST = "analyst"
    IT_STAFF = "it_staff"
    EMPLOYEE = "employee"


class WorkflowStatus(str, enum.Enum):
    DRAFT = "draft"
    VALIDATED = "validated"
    SIMULATED = "simulated"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ValidationStatus(str, enum.Enum):
    PENDING = "pending"
    VALID = "valid"
    INVALID = "invalid"


class ExecutionMode(str, enum.Enum):
    SIMULATION = "simulation"
    EXECUTION = "execution"


class ExecutionStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class StepStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    SKIPPED = "skipped"


class ApprovalStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFICATION_REQUESTED = "modification_requested"


class ActorType(str, enum.Enum):
    USER = "user"
    SYSTEM = "system"
    AGENT = "agent"


# ─── Helper ───────────────────────────────────────────────────────────────────

def generate_uuid() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ─── Models ───────────────────────────────────────────────────────────────────


class User(Base):
    """User entity - represents system users."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(
        SAEnum(UserRole, name="user_role", create_constraint=True),
        nullable=False,
        default=UserRole.EMPLOYEE,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Relationships
    workflows: Mapped[list["Workflow"]] = relationship(
        "Workflow", back_populates="creator", foreign_keys="Workflow.created_by"
    )

    __table_args__ = (
        Index("ix_users_email", "email"),
        Index("ix_users_role", "role"),
    )


class Workflow(Base):
    """Workflow entity - represents a business workflow."""

    __tablename__ = "workflows"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    requirement_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    current_version_id: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True
    )
    status: Mapped[str] = mapped_column(
        SAEnum(WorkflowStatus, name="workflow_status", create_constraint=True),
        nullable=False,
        default=WorkflowStatus.DRAFT,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    creator: Mapped[Optional["User"]] = relationship(
        "User", back_populates="workflows", foreign_keys=[created_by]
    )
    versions: Mapped[list["WorkflowVersion"]] = relationship(
        "WorkflowVersion", back_populates="workflow", cascade="all, delete-orphan"
    )
    executions: Mapped[list["WorkflowExecution"]] = relationship(
        "WorkflowExecution", back_populates="workflow", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_workflows_status", "status"),
        Index("ix_workflows_created_by", "created_by"),
        Index("ix_workflows_created_at", "created_at"),
    )


class WorkflowVersion(Base):
    """WorkflowVersion entity - versioned workflow definitions."""

    __tablename__ = "workflow_versions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    workflow_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    workflow_definition: Mapped[dict] = mapped_column(JSON, nullable=False)
    requirement_analysis: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    process_plan: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    validation_status: Mapped[str] = mapped_column(
        SAEnum(ValidationStatus, name="validation_status", create_constraint=True),
        nullable=False,
        default=ValidationStatus.PENDING,
    )
    validation_result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Relationships
    workflow: Mapped["Workflow"] = relationship(
        "Workflow", back_populates="versions"
    )
    executions: Mapped[list["WorkflowExecution"]] = relationship(
        "WorkflowExecution", back_populates="workflow_version"
    )

    __table_args__ = (
        UniqueConstraint("workflow_id", "version_number", name="uq_workflow_version"),
        Index("ix_workflow_versions_workflow_id", "workflow_id"),
        Index("ix_workflow_versions_validation_status", "validation_status"),
    )


class WorkflowExecution(Base):
    """WorkflowExecution entity - tracks workflow runs."""

    __tablename__ = "workflow_executions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    workflow_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False
    )
    workflow_version_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workflow_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    execution_mode: Mapped[str] = mapped_column(
        SAEnum(ExecutionMode, name="execution_mode", create_constraint=True),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        SAEnum(ExecutionStatus, name="execution_status", create_constraint=True),
        nullable=False,
        default=ExecutionStatus.PENDING,
    )
    execution_inputs: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    execution_result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    workflow: Mapped["Workflow"] = relationship(
        "Workflow", back_populates="executions"
    )
    workflow_version: Mapped["WorkflowVersion"] = relationship(
        "WorkflowVersion", back_populates="executions"
    )
    steps: Mapped[list["ExecutionStep"]] = relationship(
        "ExecutionStep", back_populates="execution", cascade="all, delete-orphan"
    )
    approval_requests: Mapped[list["ApprovalRequest"]] = relationship(
        "ApprovalRequest", back_populates="execution", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_workflow_executions_workflow_id", "workflow_id"),
        Index("ix_workflow_executions_status", "status"),
        Index("ix_workflow_executions_mode", "execution_mode"),
        Index("ix_workflow_executions_started_at", "started_at"),
    )


class ExecutionStep(Base):
    """ExecutionStep entity - individual step within an execution."""

    __tablename__ = "execution_steps"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    execution_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workflow_executions.id", ondelete="CASCADE"),
        nullable=False,
    )
    step_id: Mapped[str] = mapped_column(String(100), nullable=False)
    step_name: Mapped[str] = mapped_column(String(255), nullable=False)
    step_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(
        SAEnum(StepStatus, name="step_status", create_constraint=True),
        nullable=False,
        default=StepStatus.PENDING,
    )
    input_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    output_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    execution: Mapped["WorkflowExecution"] = relationship(
        "WorkflowExecution", back_populates="steps"
    )

    __table_args__ = (
        Index("ix_execution_steps_execution_id", "execution_id"),
        Index("ix_execution_steps_step_id", "step_id"),
        Index("ix_execution_steps_status", "status"),
    )


class ApprovalRequest(Base):
    """ApprovalRequest entity - human approval requests."""

    __tablename__ = "approval_requests"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    workflow_execution_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workflow_executions.id", ondelete="CASCADE"),
        nullable=False,
    )
    step_id: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(
        SAEnum(ApprovalStatus, name="approval_status", create_constraint=True),
        nullable=False,
        default=ApprovalStatus.PENDING,
    )
    requested_by: Mapped[str] = mapped_column(
        String(100), nullable=False, default="system"
    )
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    modification_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    execution: Mapped["WorkflowExecution"] = relationship(
        "WorkflowExecution", back_populates="approval_requests"
    )

    __table_args__ = (
        Index("ix_approval_requests_execution_id", "workflow_execution_id"),
        Index("ix_approval_requests_status", "status"),
    )


class KnowledgeDocument(Base):
    """KnowledgeDocument entity - indexed company documents."""

    __tablename__ = "knowledge_documents"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    metadata_: Mapped[Optional[dict]] = mapped_column(
        "metadata", JSON, nullable=True
    )
    indexed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    __table_args__ = (
        Index("ix_knowledge_documents_filename", "filename"),
    )


class AuditLog(Base):
    """AuditLog entity - immutable audit trail."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    actor_type: Mapped[str] = mapped_column(
        SAEnum(ActorType, name="actor_type", create_constraint=True),
        nullable=False,
    )
    actor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(100), nullable=False)
    metadata_: Mapped[Optional[dict]] = mapped_column(
        "metadata", JSON, nullable=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    __table_args__ = (
        Index("ix_audit_logs_action", "action"),
        Index("ix_audit_logs_resource_type", "resource_type"),
        Index("ix_audit_logs_resource_id", "resource_id"),
        Index("ix_audit_logs_timestamp", "timestamp"),
        Index("ix_audit_logs_actor", "actor_type", "actor_id"),
    )
