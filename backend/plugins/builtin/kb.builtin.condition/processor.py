"""Plugin entry for kb.builtin.condition — re-exports ConditionProcessor from core nodes."""

from app.services.workflow.nodes.condition import ConditionProcessor

# Re-export for plugin loader discovery
__all__ = ["ConditionProcessor"]
