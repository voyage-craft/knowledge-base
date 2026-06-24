"""Plugin entry for kb.builtin.approval — re-exports ApprovalProcessor from core nodes."""

from app.services.workflow.nodes.approval import ApprovalProcessor

# Re-export for plugin loader discovery
__all__ = ["ApprovalProcessor"]
