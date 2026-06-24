"""Plugin entry for kb.builtin.auto_tag — re-exports AutoTagProcessor from core nodes."""

from app.services.workflow.nodes.tagging import AutoTagProcessor

# Re-export for plugin loader discovery
__all__ = ["AutoTagProcessor"]
