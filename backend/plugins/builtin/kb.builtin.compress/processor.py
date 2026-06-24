"""Plugin entry for kb.builtin.compress — re-exports CompressProcessor from core nodes."""

from app.services.workflow.nodes.edit import CompressProcessor

# Re-export for plugin loader discovery
__all__ = ["CompressProcessor"]
