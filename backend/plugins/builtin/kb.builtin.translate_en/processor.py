"""Plugin entry for kb.builtin.translate_en — re-exports TranslateEnProcessor from core nodes."""

from app.services.workflow.nodes.edit import TranslateEnProcessor

# Re-export for plugin loader discovery
__all__ = ["TranslateEnProcessor"]
