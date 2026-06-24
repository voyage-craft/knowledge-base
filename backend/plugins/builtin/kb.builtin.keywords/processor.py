"""Plugin entry for kb.builtin.keywords — re-exports KeywordsProcessor from core nodes."""

from app.services.workflow.nodes.analysis import KeywordsProcessor

# Re-export for plugin loader discovery
__all__ = ["KeywordsProcessor"]
