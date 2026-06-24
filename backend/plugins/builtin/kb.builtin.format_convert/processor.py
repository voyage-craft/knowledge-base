"""Plugin entry for kb.builtin.format_convert — re-exports FormatConvertProcessor from core nodes."""

from app.services.workflow.nodes.format_convert import FormatConvertProcessor

# Re-export for plugin loader discovery
__all__ = ["FormatConvertProcessor"]
