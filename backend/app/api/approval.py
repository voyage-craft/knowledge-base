"""Approval API endpoints for workflow approval workflow.

Provides endpoints for:
- Listing pending approvals
- Approving/rejecting workflow runs
- Viewing approval history

Endpoints:
    GET /api/approvals - List pending approvals
    POST /api/approvals/{run_id}/approve - Approve a workflow run
    POST /api/approvals/{run_id}/reject - Reject a workflow run
    GET /api/approvals/{run_id} - Get approval details
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone

from app.core.database import get_db
from app.api.auth import get_current_user_dep
from app.models.user import User
from app.models.workflow import WorkflowRun, Workflow
from app.services.workflow.nodes.approval import handle_approval

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


class ApprovalResponse(BaseModel):
    """Response model for an approval request."""
    run_id: int
    workflow_id: int
    workflow_name: str
    status: str
    approval_node_id: str
    message: str
    document_id: Optional[int] = None
    document_title: Optional[str] = None
    requested_at: Optional[datetime] = None
    timeout_at: Optional[datetime] = None
    results_json: Optional[dict] = None


class ApprovalActionRequest(BaseModel):
    """Request model for approval action."""
    comment: Optional[str] = Field(None, max_length=1000)


class ApprovalActionResponse(BaseModel):
    """Response model for approval action."""
    success: bool
    message: str
    run_status: str


@router.get("", response_model=list[ApprovalResponse])
async def list_pending_approvals(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """List all pending approval requests for the current user.

    Returns:
        List of workflow runs waiting for approval
    """
    # Get workflow runs waiting for approval
    result = await db.execute(
        select(WorkflowRun)
        .where(
            WorkflowRun.user_id == current_user.id,
            WorkflowRun.status == "waiting_approval",
        )
        .order_by(WorkflowRun.started_at.desc())
    )
    runs = result.scalars().all()

    approvals = []
    for run in runs:
        # Get workflow name
        workflow = await db.get(Workflow, run.workflow_id)
        workflow_name = workflow.name if workflow else "Unknown"

        # Extract approval data from results_json
        results = run.results_json or {}
        approval_data = results.get("approval_request", {})

        approvals.append(ApprovalResponse(
            run_id=run.id,
            workflow_id=run.workflow_id,
            workflow_name=workflow_name,
            status=run.status,
            approval_node_id=approval_data.get("node_id", ""),
            message=approval_data.get("message", "请审核"),
            document_id=approval_data.get("document_id"),
            document_title=approval_data.get("document_title"),
            requested_at=datetime.fromisoformat(approval_data["requested_at"]) if approval_data.get("requested_at") else None,
            timeout_at=datetime.fromisoformat(approval_data["timeout_at"]) if approval_data.get("timeout_at") else None,
            results_json=results,
        ))

    return approvals


@router.get("/{run_id}", response_model=ApprovalResponse)
async def get_approval_details(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """Get details of a specific approval request.

    Args:
        run_id: WorkflowRun ID

    Returns:
        Approval details
    """
    result = await db.execute(
        select(WorkflowRun).where(
            WorkflowRun.id == run_id,
            WorkflowRun.user_id == current_user.id,
        )
    )
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(status_code=404, detail="工作流运行不存在")

    # Get workflow name
    workflow = await db.get(Workflow, run.workflow_id)
    workflow_name = workflow.name if workflow else "Unknown"

    # Extract approval data from results_json
    results = run.results_json or {}
    approval_data = results.get("approval_request", {})

    return ApprovalResponse(
        run_id=run.id,
        workflow_id=run.workflow_id,
        workflow_name=workflow_name,
        status=run.status,
        approval_node_id=approval_data.get("node_id", ""),
        message=approval_data.get("message", "请审核"),
        document_id=approval_data.get("document_id"),
        document_title=approval_data.get("document_title"),
        requested_at=datetime.fromisoformat(approval_data["requested_at"]) if approval_data.get("requested_at") else None,
        timeout_at=datetime.fromisoformat(approval_data["timeout_at"]) if approval_data.get("timeout_at") else None,
        results_json=results,
    )


@router.post("/{run_id}/approve", response_model=ApprovalActionResponse)
async def approve_workflow(
    run_id: int,
    data: ApprovalActionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """Approve a workflow run and resume execution.

    Args:
        run_id: WorkflowRun ID
        data: Approval action with optional comment

    Returns:
        Approval action result
    """
    # Get workflow run
    result = await db.execute(
        select(WorkflowRun).where(
            WorkflowRun.id == run_id,
            WorkflowRun.user_id == current_user.id,
        )
    )
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(status_code=404, detail="工作流运行不存在")

    if run.status != "waiting_approval":
        raise HTTPException(status_code=400, detail=f"工作流状态不是等待审批: {run.status}")

    # Extract approval node ID from results
    results = run.results_json or {}
    approval_data = results.get("approval_request", {})
    approval_node_id = approval_data.get("node_id", "")

    # Handle approval
    success = await handle_approval(
        db=db,
        run_id=run_id,
        approval_node_id=approval_node_id,
        approved=True,
        comment=data.comment,
    )

    if success:
        return ApprovalActionResponse(
            success=True,
            message="审批通过，工作流已恢复执行",
            run_status="running",
        )
    else:
        raise HTTPException(status_code=500, detail="审批处理失败")


@router.post("/{run_id}/reject", response_model=ApprovalActionResponse)
async def reject_workflow(
    run_id: int,
    data: ApprovalActionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """Reject a workflow run.

    Args:
        run_id: WorkflowRun ID
        data: Rejection action with comment

    Returns:
        Rejection action result
    """
    # Get workflow run
    result = await db.execute(
        select(WorkflowRun).where(
            WorkflowRun.id == run_id,
            WorkflowRun.user_id == current_user.id,
        )
    )
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(status_code=404, detail="工作流运行不存在")

    if run.status != "waiting_approval":
        raise HTTPException(status_code=400, detail=f"工作流状态不是等待审批: {run.status}")

    # Extract approval node ID from results
    results = run.results_json or {}
    approval_data = results.get("approval_request", {})
    approval_node_id = approval_data.get("node_id", "")

    # Handle rejection
    success = await handle_approval(
        db=db,
        run_id=run_id,
        approval_node_id=approval_node_id,
        approved=False,
        comment=data.comment,
    )

    return ApprovalActionResponse(
        success=True,
        message="审批已拒绝，工作流已终止",
        run_status="failed",
    )
