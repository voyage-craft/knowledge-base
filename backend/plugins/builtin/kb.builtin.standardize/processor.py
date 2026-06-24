"""Plugin entry for kb.builtin.standardize — re-exports StandardizeProcessor from core nodes."""

from app.services.workflow.nodes.analysis import StandardizeProcessor

# Re-export for plugin loader discovery
__all__ = ["StandardizeProcessor"]
