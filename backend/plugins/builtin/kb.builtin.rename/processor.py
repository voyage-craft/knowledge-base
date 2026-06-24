"""Plugin entry for kb.builtin.rename — re-exports RenameProcessor from core nodes."""

from app.services.workflow.nodes.rename import RenameProcessor

# Re-export for plugin loader discovery
__all__ = ["RenameProcessor"]
