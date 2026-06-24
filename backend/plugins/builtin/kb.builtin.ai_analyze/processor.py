"""Plugin entry for kb.builtin.ai_analyze — re-exports AIAnalyzeProcessor from core nodes."""

from app.services.workflow.nodes.ai_analyze import AIAnalyzeProcessor

# Re-export for plugin loader discovery
__all__ = ["AIAnalyzeProcessor"]
