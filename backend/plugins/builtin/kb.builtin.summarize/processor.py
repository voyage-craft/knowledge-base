"""Plugin entry for kb.builtin.summarize — re-exports SummarizeProcessor from core nodes."""

from app.services.workflow.nodes.analysis import SummarizeProcessor

# Re-export for plugin loader discovery
__all__ = ["SummarizeProcessor"]
