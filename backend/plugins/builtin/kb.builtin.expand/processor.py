"""Plugin entry for kb.builtin.expand — re-exports ExpandProcessor from core nodes."""

from app.services.workflow.nodes.edit import ExpandProcessor

# Re-export for plugin loader discovery
__all__ = ["ExpandProcessor"]
