"""Node processor registry for workflow engine v2.

This module provides a registry pattern for workflow node types,
making the engine extensible without modifying core code.

Usage:
    from app.services.workflow.node_registry import NodeProcessorRegistry, NodeProcessor, NodeContext, NodeResult

    @NodeProcessorRegistry.register("my_custom_type")
    class MyCustomProcessor(NodeProcessor):
        async def execute(self, context: NodeContext) -> NodeResult:
            # Process logic here
            return NodeResult(output_text="processed text")
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass
class NodeContext:
    """Context passed to node processors during execution."""
    node: dict                                    # Current node configuration
    document: dict                                # {id, title, text, content_json}
    current_text: str                             # Current text being processed
    accumulated_data: dict = field(default_factory=dict)  # Shared state across nodes
    db: Optional[AsyncSession] = None             # Database session
    user_id: int = 0                              # Current user ID
    run_id: int = 0                               # Workflow run ID
    extra: dict = field(default_factory=dict)     # Additional context data


@dataclass
class NodeResult:
    """Result returned by node processors."""
    output_text: Optional[str] = None             # Modified text (for edit nodes)
    output_data: Optional[dict] = None            # Structured data (for analysis nodes)
    should_continue: bool = True                  # For conditional nodes
    branch_target: Optional[str] = None           # For branching nodes
    error: Optional[str] = None                   # Error message if failed
    actions: list[str] = field(default_factory=list)  # Actions performed
    metadata: dict = field(default_factory=dict)  # Additional metadata


class NodeProcessor:
    """Base class for node processors.

    Subclass this and implement the execute method to create a new node type.
    """

    async def execute(self, context: NodeContext) -> NodeResult:
        """Execute the node's logic.

        Args:
            context: Execution context with node config, document data, etc.

        Returns:
            NodeResult with output text, data, or control flow decisions.
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement execute()")

    def get_prompt_key(self) -> Optional[str]:
        """Return the prompt key for this node type (for LLM-based nodes)."""
        return None


class NodeProcessorRegistry:
    """Registry of node type processors.

    Register new node types using the @register decorator or direct call:
        @NodeProcessorRegistry.register("my_type")
        class MyProcessor(NodeProcessor):
            ...

        # Or from plugin loader:
        NodeProcessorRegistry.register("my_type")(MyProcessor)
    """

    _processors: dict[str, type[NodeProcessor]] = {}
    _metadata: dict[str, dict] = {}  # node_type -> {plugin_id, version, ...}

    @classmethod
    def register(cls, node_type: str):
        """Decorator to register a node processor.

        Args:
            node_type: The node type string (e.g., "polish", "condition", "loop")

        Returns:
            Decorator function
        """
        def decorator(processor_cls: type[NodeProcessor]):
            if node_type in cls._processors:
                logger.warning("Overwriting existing processor for type '%s'", node_type)
            cls._processors[node_type] = processor_cls
            logger.debug("Registered processor '%s' for type '%s'", processor_cls.__name__, node_type)
            return processor_cls
        return decorator

    @classmethod
    def register_with_metadata(
        cls,
        node_type: str,
        processor_cls: type[NodeProcessor],
        plugin_id: str = "",
        version: str = "",
        is_builtin: bool = False,
    ) -> None:
        """Register a processor with plugin metadata (used by plugin_loader)."""
        cls._processors[node_type] = processor_cls
        cls._metadata[node_type] = {
            "plugin_id": plugin_id,
            "version": version,
            "is_builtin": is_builtin,
        }
        logger.debug(
            "Registered processor '%s' for type '%s' (plugin: %s v%s)",
            processor_cls.__name__, node_type, plugin_id, version,
        )

    @classmethod
    def unregister(cls, node_type: str) -> bool:
        """Remove a processor registration. Returns True if it existed."""
        removed = cls._processors.pop(node_type, None) is not None
        cls._metadata.pop(node_type, None)
        return removed

    @classmethod
    def get_metadata(cls, node_type: str) -> dict:
        """Get plugin metadata for a registered node type."""
        return cls._metadata.get(node_type, {})

    @classmethod
    def get(cls, node_type: str) -> type[NodeProcessor]:
        """Get a processor class by node type.

        Raises:
            ValueError: If node type is not registered
        """
        if node_type not in cls._processors:
            raise ValueError(f"Unknown node type: {node_type}. Registered types: {list(cls._processors.keys())}")
        return cls._processors[node_type]

    @classmethod
    def has(cls, node_type: str) -> bool:
        """Check if a node type is registered."""
        return node_type in cls._processors

    @classmethod
    def list_types(cls) -> list[str]:
        """List all registered node types."""
        return list(cls._processors.keys())

    @classmethod
    def clear(cls):
        """Clear all registered processors (for testing)."""
        cls._processors.clear()
        cls._metadata.clear()
