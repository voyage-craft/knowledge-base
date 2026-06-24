"""Plugin entry for kb.builtin.loop — re-exports LoopProcessor from core nodes."""

from app.services.workflow.nodes.loop import LoopProcessor

# Re-export for plugin loader discovery
__all__ = ["LoopProcessor"]
