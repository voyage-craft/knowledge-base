"""Plugin entry for kb.builtin.polish — re-exports PolishProcessor from core nodes."""

from app.services.workflow.nodes.edit import PolishProcessor

# Re-export for plugin loader discovery
__all__ = ["PolishProcessor"]
