"""Loop node processor - iterate over items and execute body nodes.

Node types:
- loop: Iterate over a list of items and execute body nodes for each

Config:
- source_field: Field name in accumulated_data containing the list to iterate
- item_variable: Variable name to store current item in accumulated_data
- max_iterations: Maximum number of iterations (safety limit)
- body_nodes: List of node IDs to execute for each item

Example:
{
  "id": "loop-1",
  "type": "loop",
  "label": "Iterate Chapters",
  "config": {
    "source_field": "chapters",
    "item_variable": "current_chapter",
    "max_iterations": 50,
    "body_nodes": ["process-chapter", "save-chapter"]
  }
}
"""

import logging
from typing import Any
from app.services.workflow.node_registry import NodeProcessorRegistry, NodeProcessor, NodeContext, NodeResult

logger = logging.getLogger(__name__)


@NodeProcessorRegistry.register("loop")
class LoopProcessor(NodeProcessor):
    """Iterate over items and execute body nodes for each item."""

    async def execute(self, context: NodeContext) -> NodeResult:
        config = context.node.get("config", {})

        source_field = config.get("source_field", "")
        item_variable = config.get("item_variable", "current_item")
        max_iterations = config.get("max_iterations", 50)
        body_node_ids = config.get("body_nodes", [])

        if not source_field:
            return NodeResult(error="循环节点缺少source_field配置")

        if not body_node_ids:
            return NodeResult(error="循环节点缺少body_nodes配置")

        # Get items from accumulated data
        items = context.accumulated_data.get(source_field, [])

        if not items:
            logger.info("Loop: no items in '%s', skipping", source_field)
            return NodeResult(
                actions=[f"循环跳过(无{source_field})"],
                metadata={"iterations": 0},
            )

        # Limit iterations
        items = items[:max_iterations]
        total_iterations = len(items)

        logger.info("Loop: iterating %d items from '%s'", total_iterations, source_field)

        # Get node map from extra context
        node_map = context.extra.get("node_map", {})
        if not node_map:
            return NodeResult(error="循环节点无法获取节点映射")

        # Execute body nodes for each item
        all_results = []
        for i, item in enumerate(items):
            logger.debug("Loop iteration %d/%d: %s", i + 1, total_iterations, item_variable)

            # Store current item in accumulated data
            context.accumulated_data[item_variable] = item
            context.accumulated_data[f"{item_variable}_index"] = i

            # Execute body nodes
            for body_node_id in body_node_ids:
                body_node = node_map.get(body_node_id)
                if not body_node:
                    logger.warning("Loop: body node '%s' not found", body_node_id)
                    continue

                # Get processor for body node
                body_type = body_node.get("type", "")
                if not NodeProcessorRegistry.has(body_type):
                    logger.warning("Loop: unknown body node type '%s'", body_type)
                    continue

                processor = NodeProcessorRegistry.get(body_type)

                # Create context for body node
                body_context = NodeContext(
                    node=body_node,
                    document=context.document,
                    current_text=context.current_text,
                    accumulated_data=context.accumulated_data,
                    db=context.db,
                    user_id=context.user_id,
                    run_id=context.run_id,
                    extra=context.extra,
                )

                # Execute body node
                try:
                    result = await processor().execute(body_context)
                    all_results.append(result)

                    # Update text if modified
                    if result.output_text is not None:
                        context.current_text = result.output_text

                    # Store metadata
                    if result.metadata:
                        context.accumulated_data.update(result.metadata)

                    # Check if we should continue
                    if not result.should_continue:
                        logger.info("Loop: body node '%s' requested stop at iteration %d", body_node_id, i)
                        break

                    # Handle branch target
                    if result.branch_target:
                        logger.info("Loop: body node '%s' branched to '%s'", body_node_id, result.branch_target)
                        # For now, we don't support branching out of loops
                        # This could be extended in the future

                except Exception as e:
                    logger.error("Loop: body node '%s' failed at iteration %d: %s", body_node_id, i, e)
                    all_results.append(NodeResult(error=str(e)))

        # Clean up loop variables
        context.accumulated_data.pop(item_variable, None)
        context.accumulated_data.pop(f"{item_variable}_index", None)

        # Aggregate results
        successful = sum(1 for r in all_results if not r.error)
        failed = sum(1 for r in all_results if r.error)

        return NodeResult(
            actions=[f"循环完成({total_iterations}次迭代)"],
            metadata={
                "iterations": total_iterations,
                "successful": successful,
                "failed": failed,
            },
        )
