"""Edit node processors - text transformation operations.

Node types:
- polish: Improve clarity, grammar, and fluency
- expand: Add more details, examples, and context
- compress: Reduce to ~50% length while keeping key info
- translate_zh: Translate to Chinese
- translate_en: Translate to English
- fix: Fix grammar, spelling, and punctuation errors
"""

import logging
from app.services.workflow.node_registry import NodeProcessorRegistry, NodeProcessor, NodeContext, NodeResult
from app.services.prompt_registry import get_prompt
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)

# Default max input length for LLM calls
DEFAULT_MAX_INPUT_LENGTH = 8000


class EditProcessorBase(NodeProcessor):
    """Base class for edit operations that transform text via LLM."""

    prompt_key: str = ""
    action_name: str = ""
    max_input_length: int = DEFAULT_MAX_INPUT_LENGTH

    async def execute(self, context: NodeContext) -> NodeResult:
        # Get max input length from config or use default
        max_length = context.node.get("config", {}).get("max_input_length", self.max_input_length)

        # Truncate text with warning
        input_text = context.current_text
        if len(input_text) > max_length:
            logger.warning(
                "Text truncated from %d to %d chars for %s node",
                len(input_text), max_length, context.node.get("type", "unknown")
            )
            input_text = input_text[:max_length]

        system = await get_prompt(self.prompt_key)
        result = await llm_service.generate(
            messages=[{"role": "user", "content": input_text}],
            system=system,
            max_tokens=4096,
        )

        # Check for LLM errors
        if self._is_llm_error(result):
            logger.warning("LLM returned error for %s: %s", self.action_name, result[:100])
            return NodeResult(error=result)

        return NodeResult(
            output_text=result,
            actions=[self.action_name],
            metadata={
                "input_truncated": len(context.current_text) > max_length,
                "input_length": len(context.current_text),
                "output_length": len(result),
            },
        )

    def _is_llm_error(self, result: str) -> bool:
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


@NodeProcessorRegistry.register("polish")
class PolishProcessor(EditProcessorBase):
    """Improve text clarity, grammar, and fluency."""
    prompt_key = "prompt_edit_polish"
    action_name = "润色"


@NodeProcessorRegistry.register("expand")
class ExpandProcessor(EditProcessorBase):
    """Add more details, examples, and context to text."""
    prompt_key = "prompt_edit_expand"
    action_name = "扩展"


@NodeProcessorRegistry.register("compress")
class CompressProcessor(EditProcessorBase):
    """Compress text to ~50% while keeping key information."""
    prompt_key = "prompt_edit_compress"
    action_name = "压缩"


@NodeProcessorRegistry.register("translate_zh")
class TranslateZhProcessor(EditProcessorBase):
    """Translate text to Chinese."""
    prompt_key = "prompt_edit_translate_zh"
    action_name = "翻译为中文"


@NodeProcessorRegistry.register("translate_en")
class TranslateEnProcessor(EditProcessorBase):
    """Translate text to English."""
    prompt_key = "prompt_edit_translate_en"
    action_name = "翻译为英文"


@NodeProcessorRegistry.register("fix")
class FixProcessor(EditProcessorBase):
    """Fix grammar, spelling, and punctuation errors."""
    prompt_key = "prompt_edit_fix"
    action_name = "修正语法"
