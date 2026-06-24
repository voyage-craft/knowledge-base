"""Condition node processor - conditional branching.

Node types:
- condition: Evaluate a condition and branch accordingly

Config:
- field: Field name to evaluate (from accumulated_data)
- operator: Comparison operator (eq, neq, gte, lte, gt, lt, contains)
- value: Value to compare against
- true_branch: Node ID to go to if condition is true
- false_branch: Node ID to go to if condition is false
"""

import logging
from typing import Any
from app.services.workflow.node_registry import NodeProcessorRegistry, NodeProcessor, NodeContext, NodeResult

logger = logging.getLogger(__name__)


def _resolve_field(data: dict, field_path: str):
    """Resolve dot-separated field paths like 'quality.score'."""
    current = data
    for key in field_path.split("."):
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return None
    return current


@NodeProcessorRegistry.register("condition")
class ConditionProcessor(NodeProcessor):
    """Evaluate a condition and return branch target."""

    async def execute(self, context: NodeContext) -> NodeResult:
        config = context.node.get("config", {})

        field = config.get("field", "")
        operator = config.get("operator", "eq")
        expected_value = config.get("value")
        true_branch = config.get("true_branch")
        false_branch = config.get("false_branch")

        if not field:
            return NodeResult(error="条件节点缺少field配置")

        # Get field value from accumulated data (supports dot-path like 'quality.score')
        actual_value = _resolve_field(context.accumulated_data, field)

        # Evaluate condition
        result = self._evaluate(actual_value, operator, expected_value)

        logger.info(
            "Condition: %s %s %s -> %s (actual=%s)",
            field, operator, expected_value, result, actual_value
        )

        # Return branch target
        if result:
            return NodeResult(
                branch_target=true_branch,
                actions=[f"条件成立，转向{true_branch}"],
                metadata={"condition_result": True, "field": field, "actual_value": actual_value},
            )
        else:
            return NodeResult(
                branch_target=false_branch,
                actions=[f"条件不成立，转向{false_branch}"],
                metadata={"condition_result": False, "field": field, "actual_value": actual_value},
            )

    def _evaluate(self, actual: Any, operator: str, expected: Any) -> bool:
        """Evaluate the condition."""
        try:
            if operator == "eq":
                return actual == expected
            elif operator == "neq":
                return actual != expected
            elif operator == "gte":
                return float(actual or 0) >= float(expected or 0)
            elif operator == "lte":
                return float(actual or 0) <= float(expected or 0)
            elif operator == "gt":
                return float(actual or 0) > float(expected or 0)
            elif operator == "lt":
                return float(actual or 0) < float(expected or 0)
            elif operator == "contains":
                return str(expected) in str(actual or "")
            elif operator == "not_contains":
                return str(expected) not in str(actual or "")
            elif operator == "is_empty":
                return not actual
            elif operator == "is_not_empty":
                return bool(actual)
            else:
                logger.warning("Unknown operator: %s", operator)
                return False
        except (ValueError, TypeError) as e:
            logger.error("Condition evaluation error: %s", e)
            return False
