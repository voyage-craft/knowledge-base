"""Plugin entry for kb.builtin.custom_prompt — re-exports CustomPromptProcessor from core nodes."""

from app.services.workflow.nodes.prompt import CustomPromptProcessor

# Re-export for plugin loader discovery
__all__ = ["CustomPromptProcessor"]
