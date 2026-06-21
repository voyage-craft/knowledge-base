"""Custom prompt node processor.

Node types:
- custom_prompt: Process text with a custom system prompt
"""

import logging
from app.services.workflow.node_registry import NodeProcessorRegistry, NodeProcessor, NodeContext, NodeResult
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)

# Default max input length for LLM calls
DEFAULT_MAX_INPUT_LENGTH = 8000


def _is_llm_error(result: str) -> bool:
    """Check if LLM result indicates an error.

    Checks for:
    - Error markers like "[LLM error: ...]"
    - Empty responses
    - Very short responses that might indicate failures
    """
    if not result or not result.strip():
        return True

    # Check for error markers
    error_markers = [
        "[LLM error:",
        "[LLM 未配置:",
        "[LLM 提供商未配置]",
        "[Stream error:",
        "[流式传输错误:",
    ]
    for marker in error_markers:
        if result.startswith(marker):
            return True

    return False


def _truncate_with_warning(text: str, max_length: int, node_type: str) -> tuple[str, bool]:
    """Truncate text with warning if needed.

    Returns:
        Tuple of (truncated_text, was_truncated)
    """
    if len(text) > max_length:
        logger.warning(
            "Text truncated from %d to %d chars for %s node",
            len(text), max_length, node_type
        )
        return text[:max_length], True
    return text, False


@NodeProcessorRegistry.register("custom_prompt")
class CustomPromptProcessor(NodeProcessor):
    """Process text with a custom system prompt from node config."""

    async def execute(self, context: NodeContext) -> NodeResult:
        prompt_text = context.node.get("config", {}).get("prompt", "")

        if not prompt_text:
            return NodeResult(error="自定义提示词为空")

        # Get max input length from config or use default
        max_length = context.node.get("config", {}).get("max_input_length", DEFAULT_MAX_INPUT_LENGTH)

        # Truncate text with warning
        input_text, was_truncated = _truncate_with_warning(
            context.current_text, max_length, "custom_prompt"
        )

        # Validate prompt length
        max_prompt_length = context.node.get("config", {}).get("max_prompt_length", 2000)
        if len(prompt_text) > max_prompt_length:
            logger.warning(
                "Custom prompt truncated from %d to %d chars",
                len(prompt_text), max_prompt_length
            )
            prompt_text = prompt_text[:max_prompt_length]

        result = await llm_service.generate(
            messages=[{"role": "user", "content": input_text}],
            system=prompt_text,
            max_tokens=4096,
        )

        # Check for LLM errors
        if _is_llm_error(result):
            logger.warning("LLM returned error for custom_prompt: %s", result[:100])
            return NodeResult(error=result)

        return NodeResult(
            output_text=result,
            actions=["自定义处理"],
            metadata={
                "input_truncated": was_truncated,
                "input_length": len(context.current_text),
                "output_length": len(result),
            },
        )
