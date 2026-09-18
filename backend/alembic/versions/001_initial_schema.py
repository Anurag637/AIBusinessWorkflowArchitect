"""initial_schema

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-09-18 15:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users
    op.create_table(
        'users',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('role', sa.Enum('admin', 'manager', 'analyst', 'it_staff', 'employee', name='user_role'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )
    op.create_index('ix_users_email', 'users', ['email'])
    op.create_index('ix_users_role', 'users', ['role'])

    # 2. workflows
    op.create_table(
        'workflows',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('requirement_text', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(length=36), nullable=True),
        sa.Column('current_version_id', sa.String(length=36), nullable=True),
        sa.Column('status', sa.Enum('draft', 'validated', 'simulated', 'pending_approval', 'approved', 'rejected', 'running', 'completed', 'failed', name='workflow_status'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_workflows_created_at', 'workflows', ['created_at'])
    op.create_index('ix_workflows_created_by', 'workflows', ['created_by'])
    op.create_index('ix_workflows_status', 'workflows', ['status'])

    # 3. workflow_versions
    op.create_table(
        'workflow_versions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('workflow_id', sa.String(length=36), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('workflow_definition', sa.JSON(), nullable=False),
        sa.Column('requirement_analysis', sa.JSON(), nullable=True),
        sa.Column('process_plan', sa.JSON(), nullable=True),
        sa.Column('created_by', sa.String(length=36), nullable=True),
        sa.Column('validation_status', sa.Enum('pending', 'valid', 'invalid', name='validation_status'), nullable=False),
        sa.Column('validation_result', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflows.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('workflow_id', 'version_number', name='uq_workflow_version')
    )
    op.create_index('ix_workflow_versions_validation_status', 'workflow_versions', ['validation_status'])
    op.create_index('ix_workflow_versions_workflow_id', 'workflow_versions', ['workflow_id'])

    # 4. workflow_executions
    op.create_table(
        'workflow_executions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('workflow_id', sa.String(length=36), nullable=False),
        sa.Column('workflow_version_id', sa.String(length=36), nullable=False),
        sa.Column('execution_mode', sa.Enum('simulation', 'execution', name='execution_mode'), nullable=False),
        sa.Column('status', sa.Enum('pending', 'running', 'completed', 'failed', 'paused', 'cancelled', name='execution_status'), nullable=False),
        sa.Column('execution_inputs', sa.JSON(), nullable=True),
        sa.Column('execution_result', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflows.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workflow_version_id'], ['workflow_versions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_workflow_executions_mode', 'workflow_executions', ['execution_mode'])
    op.create_index('ix_workflow_executions_started_at', 'workflow_executions', ['started_at'])
    op.create_index('ix_workflow_executions_status', 'workflow_executions', ['status'])
    op.create_index('ix_workflow_executions_workflow_id', 'workflow_executions', ['workflow_id'])

    # 5. execution_steps
    op.create_table(
        'execution_steps',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('execution_id', sa.String(length=36), nullable=False),
        sa.Column('step_id', sa.String(length=100), nullable=False),
        sa.Column('step_name', sa.String(length=255), nullable=False),
        sa.Column('step_type', sa.String(length=50), nullable=False),
        sa.Column('status', sa.Enum('pending', 'running', 'completed', 'failed', 'paused', 'skipped', name='step_status'), nullable=False),
        sa.Column('input_data', sa.JSON(), nullable=True),
        sa.Column('output_data', sa.JSON(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['execution_id'], ['workflow_executions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_execution_steps_execution_id', 'execution_steps', ['execution_id'])
    op.create_index('ix_execution_steps_status', 'execution_steps', ['status'])
    op.create_index('ix_execution_steps_step_id', 'execution_steps', ['step_id'])

    # 6. approval_requests
    op.create_table(
        'approval_requests',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('workflow_execution_id', sa.String(length=36), nullable=False),
        sa.Column('step_id', sa.String(length=100), nullable=False),
        sa.Column('status', sa.Enum('pending', 'approved', 'rejected', 'modification_requested', name='approval_status'), nullable=False),
        sa.Column('requested_by', sa.String(length=100), nullable=False),
        sa.Column('reviewed_by', sa.String(length=36), nullable=True),
        sa.Column('comments', sa.Text(), nullable=True),
        sa.Column('modification_details', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['workflow_execution_id'], ['workflow_executions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_approval_requests_execution_id', 'approval_requests', ['workflow_execution_id'])
    op.create_index('ix_approval_requests_status', 'approval_requests', ['status'])

    # 7. knowledge_documents
    op.create_table(
        'knowledge_documents',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('filename', sa.String(length=500), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('source', sa.String(length=500), nullable=True),
        sa.Column('content_hash', sa.String(length=64), nullable=True),
        sa.Column('chunk_count', sa.Integer(), nullable=False),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('indexed_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_knowledge_documents_filename', 'knowledge_documents', ['filename'])

    # 8. audit_logs
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('actor_type', sa.Enum('user', 'system', 'agent', name='actor_type'), nullable=False),
        sa.Column('actor_id', sa.String(length=100), nullable=False),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('resource_type', sa.String(length=100), nullable=False),
        sa.Column('resource_id', sa.String(length=100), nullable=False),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_audit_logs_action', 'audit_logs', ['action'])
    op.create_index('ix_audit_logs_actor_id', 'audit_logs', ['actor_id'])
    op.create_index('ix_audit_logs_resource', 'audit_logs', ['resource_type', 'resource_id'])
    op.create_index('ix_audit_logs_timestamp', 'audit_logs', ['timestamp'])


def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_table('knowledge_documents')
    op.drop_table('approval_requests')
    op.drop_table('execution_steps')
    op.drop_table('workflow_executions')
    op.drop_table('workflow_versions')
    op.drop_table('workflows')
    op.drop_table('users')
