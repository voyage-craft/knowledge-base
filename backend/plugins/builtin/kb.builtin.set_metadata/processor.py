"""Plugin entry for kb.builtin.set_metadata — re-exports SetMetadataProcessor from core nodes."""

from app.services.workflow.nodes.set_metadata import SetMetadataProcessor

# Re-export for plugin loader discovery
__all__ = ["SetMetadataProcessor"]
