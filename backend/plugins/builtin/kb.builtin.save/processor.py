"""Plugin entry for kb.builtin.save — re-exports SaveProcessor from core nodes."""

from app.services.workflow.nodes.save import SaveProcessor

# Re-export for plugin loader discovery
__all__ = ["SaveProcessor"]
