"""Retry mechanism for node processors.

This module provides a retry wrapper that can be applied to any node processor
to automatically retry failed executions with exponential backoff.

Usage:
    from app.services.workflow.nodes.retry import with_retry

    @NodeProcessorRegistry.register("my_node")
    @with_retry(max_retries=3, backoff_base=2.0)
    class MyNodeProcessor(NodeProcessor):
        async def execute(self, context: NodeContext) -> NodeResult:
            # Your node logic here
            pass
"""

import asyncio
import logging
from functools import wraps
from typing import TypeVar, Callable
from app.services.workflow.node_registry import NodeProcessor, NodeContext, NodeResult

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=NodeProcessor)


def with_retry(
    max_retries: int = 3,
    backoff_base: float = 2.0,
    max_backoff: float = 60.0,
    retryable_errors: tuple[type[Exception], ...] | None = None,
):
    """Decorator to add retry logic to a node processor.

    Args:
        max_retries: Maximum number of retry attempts
        backoff_base: Base for exponential backoff (seconds)
        max_backoff: Maximum backoff time (seconds)
        retryable_errors: Tuple of exception types to retry (None = retry all)

    Returns:
        Decorated processor class with retry logic
    """

    def decorator(processor_cls: type[T]) -> type[T]:
        original_execute = processor_cls.execute

        @wraps(original_execute)
        async def execute_with_retry(self, context: NodeContext) -> NodeResult:
            last_error = None
            retry_count = 0

            for attempt in range(max_retries + 1):
                try:
                    result = await original_execute(self, context)

                    # If successful or non-retryable error, return immediately
                    if not result.error:
                        if attempt > 0:
                            logger.info(
                                "Node %s succeeded after %d retries",
                                context.node.get("type", "unknown"),
                                attempt,
                            )
                        return result

                    # Check if error is retryable
                    last_error = result.error
                    if retryable_errors and not any(
                        isinstance(e, retryable_errors) for e in [Exception(result.error)]
                    ):
                        return result

                    # If this was the last attempt, return the error
                    if attempt >= max_retries:
                        logger.warning(
                            "Node %s failed after %d retries: %s",
                            context.node.get("type", "unknown"),
                            max_retries,
                            result.error,
                        )
                        return result

                    # Calculate backoff
                    backoff = min(backoff_base ** attempt, max_backoff)
                    logger.info(
                        "Node %s failed (attempt %d/%d), retrying in %.1fs: %s",
                        context.node.get("type", "unknown"),
                        attempt + 1,
                        max_retries + 1,
                        backoff,
                        result.error,
                    )

                    # Wait before retry
                    await asyncio.sleep(backoff)
                    retry_count = attempt + 1

                except Exception as e:
                    last_error = str(e)

                    # Check if exception is retryable
                    if retryable_errors and not isinstance(e, retryable_errors):
                        raise

                    # If this was the last attempt, raise
                    if attempt >= max_retries:
                        logger.error(
                            "Node %s failed after %d retries with exception: %s",
                            context.node.get("type", "unknown"),
                            max_retries,
                            e,
                        )
                        raise

                    # Calculate backoff
                    backoff = min(backoff_base ** attempt, max_backoff)
                    logger.info(
                        "Node %s exception (attempt %d/%d), retrying in %.1fs: %s",
                        context.node.get("type", "unknown"),
                        attempt + 1,
                        max_retries + 1,
                        backoff,
                        e,
                    )

                    # Wait before retry
                    await asyncio.sleep(backoff)
                    retry_count = attempt + 1

            # Should not reach here, but just in case
            return NodeResult(
                error=f"重试{retry_count}次后失败: {last_error}",
                metadata={"retry_count": retry_count},
            )

        processor_cls.execute = execute_with_retry
        return processor_cls

    return decorator


class RetryableNodeProcessor(NodeProcessor):
    """Base class for node processors with built-in retry support.

    Subclass this instead of NodeProcessor to automatically get retry logic.
    """

    max_retries: int = 3
    backoff_base: float = 2.0
    max_backoff: float = 60.0
    retryable_errors: tuple[type[Exception], ...] | None = None

    async def execute_with_retry(self, context: NodeContext) -> NodeResult:
        """Execute with retry logic."""
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                result = await self.execute(context)

                if not result.error:
                    if attempt > 0:
                        logger.info(
                            "Node %s succeeded after %d retries",
                            context.node.get("type", "unknown"),
                            attempt,
                        )
                    return result

                last_error = result.error
                if attempt >= self.max_retries:
                    return result

                backoff = min(self.backoff_base ** attempt, self.max_backoff)
                logger.info(
                    "Node %s failed (attempt %d/%d), retrying in %.1fs",
                    context.node.get("type", "unknown"),
                    attempt + 1,
                    self.max_retries + 1,
                    backoff,
                )
                await asyncio.sleep(backoff)

            except Exception as e:
                last_error = str(e)
                if self.retryable_errors and not isinstance(e, self.retryable_errors):
                    raise

                if attempt >= self.max_retries:
                    raise

                backoff = min(self.backoff_base ** attempt, self.max_backoff)
                logger.info(
                    "Node %s exception (attempt %d/%d), retrying in %.1fs",
                    context.node.get("type", "unknown"),
                    attempt + 1,
                    self.max_retries + 1,
                    backoff,
                )
                await asyncio.sleep(backoff)

        return NodeResult(error=f"重试失败: {last_error}")
