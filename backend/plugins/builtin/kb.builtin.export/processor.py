"""Plugin entry for kb.builtin.export — re-exports ExportProcessor from core nodes."""

from app.services.workflow.nodes.export import ExportProcessor

# Re-export for plugin loader discovery
__all__ = ["ExportProcessor"]
