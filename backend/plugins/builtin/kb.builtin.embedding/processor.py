"""Plugin entry for kb.builtin.embedding — re-exports EmbeddingProcessor from core nodes."""

from app.services.workflow.nodes.embedding import EmbeddingProcessor

# Re-export for plugin loader discovery
__all__ = ["EmbeddingProcessor"]
