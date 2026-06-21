"""Analysis node processors - document analysis operations.

Node types:
- summarize: Generate a concise summary
- keywords: Extract core keywords
- standardize: Analyze document structure and suggest improvements
"""

import json
import re
import logging
from app.services.workflow.node_registry import NodeProcessorRegistry, NodeProcessor, NodeContext, NodeResult
from app.services.prompt_registry import get_prompt
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


@NodeProcessorRegistry.register("summarize")
class SummarizeProcessor(NodeProcessor):
    """Generate a concise summary of the document."""

    async def execute(self, context: NodeContext) -> NodeResult:
        # Get max input length from config or use default
        max_length = context.node.get("config", {}).get("max_input_length", DEFAULT_MAX_INPUT_LENGTH)

        # Truncate text with warning
        input_text, was_truncated = _truncate_with_warning(
            context.current_text, max_length, "summarize"
        )

        system = await get_prompt("prompt_workflow_summarize")
        prompt = f"文档标题: {context.document.get('title', '')}\n\n文档内容:\n{input_text}"

        result = await llm_service.generate(
            messages=[{"role": "user", "content": prompt}],
            system=system,
            max_tokens=1024,
        )

        # Check for LLM errors
        if _is_llm_error(result):
            logger.warning("LLM returned error for summarize: %s", result[:100])
            return NodeResult(error=result)

        # Store summary in accumulated data
        context.accumulated_data.setdefault("summaries", []).append(result)

        return NodeResult(
            output_data={"summary": result},
            actions=["生成摘要"],
            metadata={
                "summary": result,
                "input_truncated": was_truncated,
                "input_length": len(context.current_text),
            },
        )


@NodeProcessorRegistry.register("keywords")
class KeywordsProcessor(NodeProcessor):
    """Extract core keywords from the document."""

    async def execute(self, context: NodeContext) -> NodeResult:
        # Get max input length from config or use default
        max_length = context.node.get("config", {}).get("max_input_length", DEFAULT_MAX_INPUT_LENGTH)

        # Truncate text with warning
        input_text, was_truncated = _truncate_with_warning(
            context.current_text, max_length, "keywords"
        )

        system = await get_prompt("prompt_workflow_keywords")

        result = await llm_service.generate(
            messages=[{"role": "user", "content": input_text}],
            system=system,
            max_tokens=512,
        )

        # Check for LLM errors
        if _is_llm_error(result):
            logger.warning("LLM returned error for keywords: %s", result[:100])
            return NodeResult(error=result)

        # Extract JSON array from response
        keywords = []
        match = re.search(r"\[.*?\]", result, re.DOTALL)
        if match:
            try:
                keywords = json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        # Store keywords in accumulated data
        context.accumulated_data.setdefault("keywords", []).extend(keywords)

        return NodeResult(
            output_data={"keywords": keywords},
            actions=["提取关键词"],
            metadata={
                "keywords": keywords,
                "input_truncated": was_truncated,
                "input_length": len(context.current_text),
            },
        )


@NodeProcessorRegistry.register("standardize")
class StandardizeProcessor(NodeProcessor):
    """Analyze document structure and suggest improvements."""

    async def execute(self, context: NodeContext) -> NodeResult:
        from app.services.ai_pipeline import ai_pipeline

        result = await ai_pipeline.standardize_document(
            context.current_text,
            context.document.get("title", ""),
            [],  # tags
        )

        # Store standardize result in accumulated data
        context.accumulated_data["standardize_result"] = result

        # Extract quality score if available
        quality_score = result.get("quality_score", 0)
        context.accumulated_data["quality_score"] = quality_score

        return NodeResult(
            output_data=result,
            actions=["标准化分析"],
            metadata={"quality_score": quality_score},
        )
