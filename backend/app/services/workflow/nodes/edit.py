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

        system = await self._build_prompt(context)
        extra_kwargs = self._get_extra_kwargs(context)
        result = await llm_service.generate(
            messages=[{"role": "user", "content": input_text}],
            system=system,
            max_tokens=4096,
            **extra_kwargs,
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

    async def _build_prompt(self, context: NodeContext) -> str:
        """Build system prompt. Override in subclasses for custom prompts."""
        return await get_prompt(self.prompt_key)

    def _get_extra_kwargs(self, context: NodeContext) -> dict:
        """Return extra kwargs for the LLM generate call. Override in subclasses."""
        return {}

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

    async def _build_prompt(self, context: NodeContext) -> str:
        config = context.node.get("config", {})
        custom_prompt = config.get("custom_prompt", "")
        if custom_prompt and custom_prompt.strip():
            return custom_prompt.strip()

        style = config.get("style", "academic")
        default_prompt = await get_prompt(self.prompt_key)
        return f"{default_prompt}\n\nStyle: {style}. Apply {style} writing style conventions."

    def _get_extra_kwargs(self, context: NodeContext) -> dict:
        config = context.node.get("config", {})
        temperature = config.get("temperature", 0.3)
        return {"temperature": temperature}


@NodeProcessorRegistry.register("expand")
class ExpandProcessor(EditProcessorBase):
    """Add more details, examples, and context to text."""
    prompt_key = "prompt_edit_expand"
    action_name = "扩展"

    async def _build_prompt(self, context: NodeContext) -> str:
        config = context.node.get("config", {})
        custom_prompt = config.get("custom_prompt", "")
        if custom_prompt and custom_prompt.strip():
            return custom_prompt.strip()

        expansion_ratio = config.get("expansion_ratio", "2x")
        focus_area = config.get("focus_area", "")
        default_prompt = await get_prompt(self.prompt_key)
        parts = [default_prompt, f"\n\nExpansion target: approximately {expansion_ratio} the original length."]
        if focus_area and focus_area.strip():
            parts.append(f" Focus especially on: {focus_area.strip()}.")
        return "".join(parts)


@NodeProcessorRegistry.register("compress")
class CompressProcessor(EditProcessorBase):
    """Compress text to ~50% while keeping key information."""
    prompt_key = "prompt_edit_compress"
    action_name = "压缩"

    async def _build_prompt(self, context: NodeContext) -> str:
        config = context.node.get("config", {})
        custom_prompt = config.get("custom_prompt", "")
        if custom_prompt and custom_prompt.strip():
            return custom_prompt.strip()

        target_ratio = config.get("target_ratio", "50%")
        preserve_key_points = config.get("preserve_key_points", True)
        default_prompt = await get_prompt(self.prompt_key)
        parts = [default_prompt, f"\n\nTarget compression ratio: {target_ratio} of the original length."]
        if preserve_key_points:
            parts.append(" Ensure all key points and main arguments are preserved.")
        return "".join(parts)


@NodeProcessorRegistry.register("translate_zh")
class TranslateZhProcessor(EditProcessorBase):
    """Translate text to Chinese."""
    prompt_key = "prompt_edit_translate_zh"
    action_name = "翻译为中文"

    async def _build_prompt(self, context: NodeContext) -> str:
        config = context.node.get("config", {})
        custom_prompt = config.get("custom_prompt", "")
        if custom_prompt and custom_prompt.strip():
            return custom_prompt.strip()

        formality = config.get("formality", "neutral")
        domain = config.get("domain", "general")
        glossary = config.get("glossary", "")
        default_prompt = await get_prompt(self.prompt_key)
        parts = [default_prompt, f"\n\nFormality level: {formality}. Domain: {domain}."]
        if glossary and glossary.strip():
            parts.append(f" Use the following glossary for consistent terminology: {glossary.strip()}")
        return "".join(parts)


@NodeProcessorRegistry.register("translate_en")
class TranslateEnProcessor(EditProcessorBase):
    """Translate text to English."""
    prompt_key = "prompt_edit_translate_en"
    action_name = "翻译为英文"

    async def _build_prompt(self, context: NodeContext) -> str:
        config = context.node.get("config", {})
        custom_prompt = config.get("custom_prompt", "")
        if custom_prompt and custom_prompt.strip():
            return custom_prompt.strip()

        formality = config.get("formality", "neutral")
        domain = config.get("domain", "general")
        glossary = config.get("glossary", "")
        default_prompt = await get_prompt(self.prompt_key)
        parts = [default_prompt, f"\n\nFormality level: {formality}. Domain: {domain}."]
        if glossary and glossary.strip():
            parts.append(f" Use the following glossary for consistent terminology: {glossary.strip()}")
        return "".join(parts)


@NodeProcessorRegistry.register("fix")
class FixProcessor(EditProcessorBase):
    """Fix grammar, spelling, and punctuation errors."""
    prompt_key = "prompt_edit_fix"
    action_name = "修正语法"

    async def _build_prompt(self, context: NodeContext) -> str:
        config = context.node.get("config", {})
        custom_prompt = config.get("custom_prompt", "")
        if custom_prompt and custom_prompt.strip():
            return custom_prompt.strip()

        fix_scope = config.get("fix_scope", "all")
        strictness = config.get("strictness", "medium")
        default_prompt = await get_prompt(self.prompt_key)
        parts = [default_prompt, f"\n\nFix scope: {fix_scope}. Strictness level: {strictness}."]
        if fix_scope != "all":
            parts.append(f" Only fix issues related to: {fix_scope}.")
        return "".join(parts)
