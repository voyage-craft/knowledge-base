"""Approval node processor - pause workflow for human review.

Node types:
- approval: Pause execution and wait for human approval

Config:
- timeout_hours: Hours to wait before auto-approve/reject (default: 72)
- auto_approve: Whether to auto-approve after timeout (default: false)
- notify: Whether to send notification (default: true)
- message: Message to display to reviewer

Example:
{
  "id": "approve-1",
  "type": "approval",
  "label": "Manual Review",
  "config": {
    "timeout_hours": 72,
    "auto_approve": false,
    "notify": true,
    "message": "Please review the processed document"
  }
}
"""

import logging
from datetime import datetime, timezone, timedelta
from app.services.workflow.node_registry import NodeProcessorRegistry, NodeProcessor, NodeContext, NodeResult
from app.models.workflow import WorkflowRun

logger = logging.getLogger(__name__)


@NodeProcessorRegistry.register("approval")
class ApprovalProcessor(NodeProcessor):
    """Pause workflow execution for human approval."""

    async def execute(self, context: NodeContext) -> NodeResult:
        config = context.node.get("config", {})

        timeout_hours = config.get("timeout_hours", 72)
        auto_approve = config.get("auto_approve", False)
        notify = config.get("notify", True)
        message = config.get("message", "请审核处理后的文档")

        # Store approval request in accumulated data
        approval_data = {
            "node_id": context.node["id"],
            "message": message,
            "requested_at": datetime.now(timezone.utc).isoformat(),
            "timeout_at": (datetime.now(timezone.utc) + timedelta(hours=timeout_hours)).isoformat(),
            "status": "pending",
            "document_id": context.document.get("id"),
            "document_title": context.document.get("title", ""),
        }

        context.accumulated_data["approval_request"] = approval_data

        # Update workflow run status to waiting_approval
        if context.db and context.run_id:
            try:
                run = await context.db.get(WorkflowRun, context.run_id)
                if run:
                    run.status = "waiting_approval"
                    await context.db.commit()
                    logger.info("Workflow run %d set to waiting_approval", context.run_id)
            except Exception as e:
                logger.error("Failed to update workflow run status: %s", e)

        # If auto_approve is True, continue immediately
        if auto_approve:
            logger.info("Approval node: auto-approved")
            return NodeResult(
                actions=["自动批准"],
                metadata={"approval_status": "auto_approved"},
            )

        # Return result indicating workflow is paused
        # The actual approval will be handled by the approval API endpoint
        logger.info("Approval node: workflow paused, waiting for human approval")

        return NodeResult(
            should_continue=False,  # Stop execution
            actions=["等待人工审批"],
            metadata={
                "approval_status": "pending",
                "approval_node_id": context.node["id"],
                "timeout_hours": timeout_hours,
            },
        )


async def handle_approval(
    db,
    run_id: int,
    approval_node_id: str,
    approved: bool,
    comment: str | None = None,
) -> bool:
    """Handle approval response and resume workflow execution.

    Args:
        db: Database session
        run_id: WorkflowRun ID
        approval_node_id: ID of the approval node
        approved: Whether the approval was granted
        comment: Optional comment from reviewer

    Returns:
        True if workflow was resumed successfully
    """
    # Get workflow run
    run = await db.get(WorkflowRun, run_id)
    if not run:
        logger.error("Workflow run %d not found", run_id)
        return False

    if run.status != "waiting_approval":
        logger.warning("Workflow run %d is not in waiting_approval status: %s", run_id, run.status)
        return False

    # Update run status
    if approved:
        run.status = "running"
        logger.info("Workflow run %d approved, resuming", run_id)
    else:
        run.status = "failed"
        run.error_message = f"审批被拒绝: {comment or '无评论'}"
        run.completed_at = datetime.now(timezone.utc)
        logger.info("Workflow run %d rejected", run_id)

    await db.commit()

    # If approved, we need to resume execution
    # This would typically be done by re-invoking the workflow engine
    # For now, we'll just update the status
    # The actual resumption logic depends on how the workflow engine is structured

    return approved
