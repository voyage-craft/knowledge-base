"""Plugin entry for kb.builtin.translate_zh — re-exports TranslateZhProcessor from core nodes."""

from app.services.workflow.nodes.edit import TranslateZhProcessor

# Re-export for plugin loader discovery
__all__ = ["TranslateZhProcessor"]
