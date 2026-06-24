"""Plugin entry for kb.builtin.source — re-exports SourceProcessor from core nodes."""

from app.services.workflow.nodes.source import SourceProcessor

# Re-export for plugin loader discovery
__all__ = ["SourceProcessor"]
