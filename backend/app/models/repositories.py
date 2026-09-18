"""
Repository layer providing clean CRUD and query interfaces for all database entities.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from app.models.entities import (
    User,
    UserRole,
    Workflow,
    WorkflowStatus,
    WorkflowVersion,
    WorkflowExecution,
    ExecutionStep,
    ExecutionMode,
    ExecutionStatus,
    StepStatus,
    ApprovalRequest,
    ApprovalStatus,
    KnowledgeDocument,
    AuditLog,
    ActorType,
)


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, name: str, email: str, role: UserRole = UserRole.EMPLOYEE) -> User:
        user = User(name=name, email=email, role=role)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_by_id(self, user_id: str) -> Optional[User]:
        stmt = select(User).where(User.id == user_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_email(self, email: str) -> Optional[User]:
        stmt = select(User).where(User.email == email)
        return self.db.execute(stmt).scalar_one_or_none()

    def list_all(self, limit: int = 100, offset: int = 0) -> List[User]:
        stmt = select(User).order_by(desc(User.created_at)).limit(limit).offset(offset)
        return list(self.db.execute(stmt).scalars().all())


class WorkflowRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        name: str,
        description: Optional[str] = None,
        requirement_text: Optional[str] = None,
        created_by: Optional[str] = None,
        status: WorkflowStatus = WorkflowStatus.DRAFT,
    ) -> Workflow:
        workflow = Workflow(
            name=name,
            description=description,
            requirement_text=requirement_text,
            created_by=created_by,
            status=status,
        )
        self.db.add(workflow)
        self.db.commit()
        self.db.refresh(workflow)
        return workflow

    def get_by_id(self, workflow_id: str) -> Optional[Workflow]:
        stmt = select(Workflow).where(Workflow.id == workflow_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def list_all(
        self,
        status: Optional[WorkflowStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Workflow]:
        stmt = select(Workflow)
        if status:
            stmt = stmt.where(Workflow.status == status)
        stmt = stmt.order_by(desc(Workflow.updated_at)).limit(limit).offset(offset)
        return list(self.db.execute(stmt).scalars().all())

    def update_status(self, workflow_id: str, status: WorkflowStatus) -> Optional[Workflow]:
        workflow = self.get_by_id(workflow_id)
        if workflow:
            workflow.status = status
            workflow.updated_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(workflow)
        return workflow

    def set_current_version(self, workflow_id: str, version_id: str) -> Optional[Workflow]:
        workflow = self.get_by_id(workflow_id)
        if workflow:
            workflow.current_version_id = version_id
            workflow.updated_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(workflow)
        return workflow

    def delete(self, workflow_id: str) -> bool:
        workflow = self.get_by_id(workflow_id)
        if workflow:
            self.db.delete(workflow)
            self.db.commit()
            return True
        return False


class WorkflowVersionRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        workflow_id: str,
        version_number: int,
        workflow_definition: Dict[str, Any],
        requirement_analysis: Optional[Dict[str, Any]] = None,
        process_plan: Optional[Dict[str, Any]] = None,
        created_by: Optional[str] = None,
    ) -> WorkflowVersion:
        wv = WorkflowVersion(
            workflow_id=workflow_id,
            version_number=version_number,
            workflow_definition=workflow_definition,
            requirement_analysis=requirement_analysis,
            process_plan=process_plan,
            created_by=created_by,
        )
        self.db.add(wv)
        self.db.commit()
        self.db.refresh(wv)
        return wv

    def get_by_id(self, version_id: str) -> Optional[WorkflowVersion]:
        stmt = select(WorkflowVersion).where(WorkflowVersion.id == version_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_version(self, workflow_id: str, version_number: int) -> Optional[WorkflowVersion]:
        stmt = select(WorkflowVersion).where(
            WorkflowVersion.workflow_id == workflow_id,
            WorkflowVersion.version_number == version_number,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_latest(self, workflow_id: str) -> Optional[WorkflowVersion]:
        stmt = (
            select(WorkflowVersion)
            .where(WorkflowVersion.workflow_id == workflow_id)
            .order_by(desc(WorkflowVersion.version_number))
            .limit(1)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_by_workflow(self, workflow_id: str) -> List[WorkflowVersion]:
        stmt = (
            select(WorkflowVersion)
            .where(WorkflowVersion.workflow_id == workflow_id)
            .order_by(desc(WorkflowVersion.version_number))
        )
        return list(self.db.execute(stmt).scalars().all())


class ExecutionRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_execution(
        self,
        workflow_id: str,
        workflow_version_id: str,
        execution_mode: ExecutionMode,
        execution_inputs: Optional[Dict[str, Any]] = None,
    ) -> WorkflowExecution:
        execution = WorkflowExecution(
            workflow_id=workflow_id,
            workflow_version_id=workflow_version_id,
            execution_mode=execution_mode,
            status=ExecutionStatus.PENDING,
            execution_inputs=execution_inputs or {},
        )
        self.db.add(execution)
        self.db.commit()
        self.db.refresh(execution)
        return execution

    def get_execution(self, execution_id: str) -> Optional[WorkflowExecution]:
        stmt = select(WorkflowExecution).where(WorkflowExecution.id == execution_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def list_by_workflow(
        self, workflow_id: str, limit: int = 50, offset: int = 0
    ) -> List[WorkflowExecution]:
        stmt = (
            select(WorkflowExecution)
            .where(WorkflowExecution.workflow_id == workflow_id)
            .order_by(desc(WorkflowExecution.started_at))
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.execute(stmt).scalars().all())

    def update_execution_status(
        self,
        execution_id: str,
        status: ExecutionStatus,
        execution_result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> Optional[WorkflowExecution]:
        execution = self.get_execution(execution_id)
        if not execution:
            return None
        execution.status = status
        now = datetime.now(timezone.utc)
        if status == ExecutionStatus.RUNNING and not execution.started_at:
            execution.started_at = now
        elif status in (ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED):
            execution.completed_at = now
        if execution_result is not None:
            execution.execution_result = execution_result
        if error_message is not None:
            execution.error_message = error_message
        self.db.commit()
        self.db.refresh(execution)
        return execution

    def add_step(
        self,
        execution_id: str,
        step_id: str,
        step_name: str,
        step_type: str,
        input_data: Optional[Dict[str, Any]] = None,
    ) -> ExecutionStep:
        step = ExecutionStep(
            execution_id=execution_id,
            step_id=step_id,
            step_name=step_name,
            step_type=step_type,
            status=StepStatus.PENDING,
            input_data=input_data or {},
        )
        self.db.add(step)
        self.db.commit()
        self.db.refresh(step)
        return step

    def update_step(
        self,
        step_pk: str,
        status: StepStatus,
        output_data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> Optional[ExecutionStep]:
        stmt = select(ExecutionStep).where(ExecutionStep.id == step_pk)
        step = self.db.execute(stmt).scalar_one_or_none()
        if not step:
            return None
        step.status = status
        now = datetime.now(timezone.utc)
        if status == StepStatus.RUNNING and not step.started_at:
            step.started_at = now
        elif status in (StepStatus.COMPLETED, StepStatus.FAILED, StepStatus.SKIPPED):
            step.completed_at = now
        if output_data is not None:
            step.output_data = output_data
        if error is not None:
            step.error = error
        self.db.commit()
        self.db.refresh(step)
        return step

    def list_steps(self, execution_id: str) -> List[ExecutionStep]:
        stmt = (
            select(ExecutionStep)
            .where(ExecutionStep.execution_id == execution_id)
            .order_by(ExecutionStep.started_at)
        )
        return list(self.db.execute(stmt).scalars().all())


class ApprovalRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_request(
        self,
        workflow_execution_id: str,
        step_id: str,
        requested_by: str = "system",
        comments: Optional[str] = None,
    ) -> ApprovalRequest:
        req = ApprovalRequest(
            workflow_execution_id=workflow_execution_id,
            step_id=step_id,
            requested_by=requested_by,
            comments=comments,
            status=ApprovalStatus.PENDING,
        )
        self.db.add(req)
        self.db.commit()
        self.db.refresh(req)
        return req

    def get_by_id(self, approval_id: str) -> Optional[ApprovalRequest]:
        stmt = select(ApprovalRequest).where(ApprovalRequest.id == approval_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def list_pending(self) -> List[ApprovalRequest]:
        stmt = (
            select(ApprovalRequest)
            .where(ApprovalRequest.status == ApprovalStatus.PENDING)
            .order_by(desc(ApprovalRequest.created_at))
        )
        return list(self.db.execute(stmt).scalars().all())

    def respond(
        self,
        approval_id: str,
        reviewed_by: str,
        decision: ApprovalStatus,
        comments: Optional[str] = None,
        modification_details: Optional[str] = None,
    ) -> Optional[ApprovalRequest]:
        req = self.get_by_id(approval_id)
        if not req:
            return None
        req.status = decision
        req.reviewed_by = reviewed_by
        req.reviewed_at = datetime.now(timezone.utc)
        if comments:
            req.comments = comments
        if modification_details:
            req.modification_details = modification_details
        self.db.commit()
        self.db.refresh(req)
        return req


class KnowledgeDocumentRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        filename: str,
        title: str,
        source: Optional[str] = None,
        content_hash: Optional[str] = None,
        chunk_count: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> KnowledgeDocument:
        doc = KnowledgeDocument(
            filename=filename,
            title=title,
            source=source,
            content_hash=content_hash,
            chunk_count=chunk_count,
            metadata_=metadata or {},
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def get_by_id(self, doc_id: str) -> Optional[KnowledgeDocument]:
        stmt = select(KnowledgeDocument).where(KnowledgeDocument.id == doc_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def list_all(self, limit: int = 100) -> List[KnowledgeDocument]:
        stmt = select(KnowledgeDocument).order_by(desc(KnowledgeDocument.indexed_at)).limit(limit)
        return list(self.db.execute(stmt).scalars().all())


class AuditLogRepository:
    """Immutable audit log repository."""

    def __init__(self, db: Session):
        self.db = db

    def log(
        self,
        actor_type: ActorType,
        actor_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        entry = AuditLog(
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata_=metadata or {},
        )
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def list_by_resource(
        self, resource_type: str, resource_id: str, limit: int = 100
    ) -> List[AuditLog]:
        stmt = (
            select(AuditLog)
            .where(
                AuditLog.resource_type == resource_type,
                AuditLog.resource_id == resource_id,
            )
            .order_by(desc(AuditLog.timestamp))
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_recent(self, limit: int = 100) -> List[AuditLog]:
        stmt = select(AuditLog).order_by(desc(AuditLog.timestamp)).limit(limit)
        return list(self.db.execute(stmt).scalars().all())
