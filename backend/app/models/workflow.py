"""Workflow and WorkflowRun models for AI workflow system."""

from sqlalchemy import Column, Integer, String, Text, ForeignKey, JSON, DateTime, func, Index
from app.core.database import Base


class Workflow(Base):
    __tablename__ = "workflows"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    template_type = Column(String(20), default="custom")  # preset / custom
    config_json = Column(JSON, nullable=False)
    schedule_json = Column(JSON, nullable=True)       # {"cron": "0 9 * * *", "enabled": true}
    trigger_type = Column(String(20), default="none")  # none / on_import / on_save / cron
    trigger_config_json = Column(JSON, nullable=True)  # {"folder_id": 1, "tag": "draft"}
    is_active = Column(Integer, default=1)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(String(20), default="pending")  # pending/running/completed/failed/waiting_approval
    total_docs = Column(Integer, default=0)
    processed_docs = Column(Integer, default=0)
    results_json = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)


class WorkflowNodeExecution(Base):
    """Tracks individual node executions within a workflow run.

    Provides per-node execution state for debugging, retry, and resume.
    """
    __tablename__ = "workflow_node_executions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    node_id = Column(String(100), nullable=False)
    node_type = Column(String(50), nullable=False)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    status = Column(String(20), default="pending")  # pending/running/completed/failed/skipped
    input_data = Column(JSON, nullable=True)
    output_data = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_workflow_node_exec_run_node", "run_id", "node_id"),
        Index("ix_workflow_node_exec_doc", "document_id"),
    )
