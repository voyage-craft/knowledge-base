"""Plugin entry for kb.builtin.fix — re-exports FixProcessor from core nodes."""

from app.services.workflow.nodes.edit import FixProcessor

# Re-export for plugin loader discovery
__all__ = ["FixProcessor"]
