"""
Unit tests for database models and repositories using in-memory SQLite.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.database import Base
from app.models.entities import (
    User,
    UserRole,
    Workflow,
    WorkflowStatus,
    WorkflowVersion,
    WorkflowExecution,
    ExecutionMode,
    ExecutionStatus,
    StepStatus,
    ApprovalStatus,
    ActorType,
)
from app.models.repositories import (
    UserRepository,
    WorkflowRepository,
    WorkflowVersionRepository,
    ExecutionRepository,
    ApprovalRepository,
    KnowledgeDocumentRepository,
    AuditLogRepository,
)


@pytest.fixture
def db_session():
    """Create a fresh in-memory database session for each test."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def test_user_repository(db_session):
    repo = UserRepository(db_session)
    user = repo.create(name="Alice Smith", email="alice@example.com", role=UserRole.MANAGER)
    assert user.id is not None
    assert user.name == "Alice Smith"
    assert user.role == UserRole.MANAGER

    fetched = repo.get_by_id(user.id)
    assert fetched is not None
    assert fetched.email == "alice@example.com"

    fetched_by_email = repo.get_by_email("alice@example.com")
    assert fetched_by_email is not None
    assert fetched_by_email.id == user.id

    all_users = repo.list_all()
    assert len(all_users) == 1


def test_workflow_and_version_repository(db_session):
    u_repo = UserRepository(db_session)
    user = u_repo.create(name="Bob", email="bob@example.com", role=UserRole.ANALYST)

    wf_repo = WorkflowRepository(db_session)
    wv_repo = WorkflowVersionRepository(db_session)

    wf = wf_repo.create(
        name="Laptop Approval Workflow",
        description="Process laptop requests with budget check",
        requirement_text="When an employee requests a laptop under 25k, IT approves...",
        created_by=user.id,
    )
    assert wf.id is not None
    assert wf.status == WorkflowStatus.DRAFT

    definition = {
        "workflow_id": wf.id,
        "name": wf.name,
        "steps": [
            {"id": "step_1", "name": "Check Budget", "type": "tool", "tool": "database_query"}
        ],
    }
    v1 = wv_repo.create(
        workflow_id=wf.id,
        version_number=1,
        workflow_definition=definition,
        created_by=user.id,
    )
    assert v1.version_number == 1
    assert v1.workflow_definition["name"] == "Laptop Approval Workflow"

    wf_repo.set_current_version(wf.id, v1.id)
    updated_wf = wf_repo.get_by_id(wf.id)
    assert updated_wf.current_version_id == v1.id

    latest = wv_repo.get_latest(wf.id)
    assert latest.id == v1.id


def test_execution_repository(db_session):
    wf_repo = WorkflowRepository(db_session)
    wv_repo = WorkflowVersionRepository(db_session)
    exec_repo = ExecutionRepository(db_session)

    wf = wf_repo.create(name="Test WF")
    v1 = wv_repo.create(workflow_id=wf.id, version_number=1, workflow_definition={"steps": []})

    execution = exec_repo.create_execution(
        workflow_id=wf.id,
        workflow_version_id=v1.id,
        execution_mode=ExecutionMode.SIMULATION,
        execution_inputs={"amount": 20000},
    )
    assert execution.id is not None
    assert execution.status == ExecutionStatus.PENDING
    assert execution.execution_mode == ExecutionMode.SIMULATION

    step = exec_repo.add_step(
        execution_id=execution.id,
        step_id="step_1",
        step_name="Validate input",
        step_type="tool",
        input_data={"param": 1},
    )
    assert step.id is not None
    assert step.status == StepStatus.PENDING

    exec_repo.update_step(step.id, status=StepStatus.COMPLETED, output_data={"valid": True})
    steps = exec_repo.list_steps(execution.id)
    assert len(steps) == 1
    assert steps[0].status == StepStatus.COMPLETED

    exec_repo.update_execution_status(
        execution.id, status=ExecutionStatus.COMPLETED, execution_result={"success": True}
    )
    finished = exec_repo.get_execution(execution.id)
    assert finished.status == ExecutionStatus.COMPLETED
    assert finished.completed_at is not None


def test_approval_repository(db_session):
    wf_repo = WorkflowRepository(db_session)
    wv_repo = WorkflowVersionRepository(db_session)
    exec_repo = ExecutionRepository(db_session)
    app_repo = ApprovalRepository(db_session)

    wf = wf_repo.create(name="Expense Approval")
    v1 = wv_repo.create(workflow_id=wf.id, version_number=1, workflow_definition={})
    execution = exec_repo.create_execution(
        workflow_id=wf.id,
        workflow_version_id=v1.id,
        execution_mode=ExecutionMode.EXECUTION,
    )

    req = app_repo.create_request(
        workflow_execution_id=execution.id,
        step_id="step_approval",
        requested_by="system",
        comments="Please review hardware cost",
    )
    assert req.id is not None
    assert req.status == ApprovalStatus.PENDING

    pending = app_repo.list_pending()
    assert len(pending) == 1

    app_repo.respond(
        approval_id=req.id,
        reviewed_by="Manager Bob",
        decision=ApprovalStatus.APPROVED,
        comments="Approved as per quarterly budget",
    )
    decided = app_repo.get_by_id(req.id)
    assert decided.status == ApprovalStatus.APPROVED
    assert decided.comments == "Approved as per quarterly budget"


def test_knowledge_document_repository(db_session):
    doc_repo = KnowledgeDocumentRepository(db_session)
    doc = doc_repo.create(
        filename="laptop_policy.md",
        title="Laptop Provisioning Policy",
        source="internal_wiki",
        content_hash="abc123hash",
        chunk_count=3,
        metadata={"author": "IT Ops", "dept": "IT"},
    )
    assert doc.id is not None
    assert doc.filename == "laptop_policy.md"

    fetched = doc_repo.get_by_id(doc.id)
    assert fetched is not None
    assert fetched.title == "Laptop Provisioning Policy"


def test_audit_log_repository(db_session):
    audit_repo = AuditLogRepository(db_session)
    entry = audit_repo.log(
        actor_type=ActorType.USER,
        actor_id="user_123",
        action="WORKFLOW_CREATED",
        resource_type="workflow",
        resource_id="wf_456",
        metadata={"name": "Laptop WF"},
    )
    assert entry.id is not None
    assert entry.action == "WORKFLOW_CREATED"

    logs = audit_repo.list_by_resource(resource_type="workflow", resource_id="wf_456")
    assert len(logs) == 1
    assert logs[0].actor_type == ActorType.USER
