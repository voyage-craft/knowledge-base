"""AI analysis node processor - AI-powered document analysis.

Node types:
- ai_analyze: Perform AI analysis on document content

Config:
- analysis_type: Type of analysis (toc_extraction, structure_analysis, quality_assessment)
- output_field: Field name to store results in accumulated_data
- max_tokens: Maximum tokens for LLM response
- max_input_length: Maximum input text length (default: 6000)
"""

import json
import logging
from app.services.workflow.node_registry import NodeProcessorRegistry, NodeProcessor, NodeContext, NodeResult
from app.services.llm_service import llm_service
from app.services.prompt_registry import get_prompt

logger = logging.getLogger(__name__)

# Default max input length for AI analysis
DEFAULT_MAX_INPUT_LENGTH = 6000


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


@NodeProcessorRegistry.register("ai_analyze")
class AIAnalyzeProcessor(NodeProcessor):
    """Perform AI-powered document analysis."""

    async def execute(self, context: NodeContext) -> NodeResult:
        config = context.node.get("config", {})
        analysis_type = config.get("analysis_type", "structure_analysis")
        output_field = config.get("output_field", "analysis_result")
        max_tokens = config.get("max_tokens", 4096)

        try:
            if analysis_type == "toc_extraction":
                result = await self._extract_toc(context, max_tokens)
            elif analysis_type == "structure_analysis":
                result = await self._analyze_structure(context, max_tokens)
            elif analysis_type == "quality_assessment":
                result = await self._assess_quality(context, max_tokens)
            elif analysis_type == "academic_structure":
                result = await self._analyze_academic(context, max_tokens)
            else:
                return NodeResult(error=f"未知的分析类型: {analysis_type}")

            # Store result in accumulated data
            context.accumulated_data[output_field] = result

            return NodeResult(
                output_data={output_field: result},
                actions=[f"AI分析({analysis_type})"],
                metadata={"analysis_type": analysis_type},
            )

        except Exception as e:
            logger.error("AI analysis failed for type %s: %s", analysis_type, e)
            return NodeResult(error=f"AI分析失败: {e}")

    async def _extract_toc(self, context: NodeContext, max_tokens: int) -> dict:
        """Extract table of contents structure from document."""
        # Get max input length from config or use default
        max_length = context.node.get("config", {}).get("max_input_length", DEFAULT_MAX_INPUT_LENGTH)

        # Truncate text with warning
        text, was_truncated = _truncate_with_warning(
            context.current_text, max_length, "ai_analyze"
        )

        system = """你是一个文档结构分析专家。请从以下文档中提取目录结构。

请以JSON格式返回目录结构：
{
  "entries": [
    {
      "title": "章节标题",
      "level": 1,
      "children": [
        {"title": "子章节标题", "level": 2, "children": []}
      ]
    }
  ],
  "suggestions": ["建议1", "建议2"]
}

只返回JSON，不要其他内容。"""

        result = await llm_service.generate(
            messages=[{"role": "user", "content": f"文档标题: {context.document.get('title', '')}\n\n文档内容:\n{text}"}],
            system=system,
            max_tokens=max_tokens,
        )

        # Check for LLM errors
        if _is_llm_error(result):
            logger.warning("LLM returned error for toc_extraction: %s", result[:100])
            return {"entries": [], "suggestions": ["LLM返回错误"]}

        try:
            parsed = json.loads(result)
            parsed["input_truncated"] = was_truncated
            return parsed
        except json.JSONDecodeError:
            # Try to extract JSON from response
            import re
            match = re.search(r"\{.*\}", result, re.DOTALL)
            if match:
                parsed = json.loads(match.group(0))
                parsed["input_truncated"] = was_truncated
                return parsed
            return {"entries": [], "suggestions": ["无法解析目录结构"], "input_truncated": was_truncated}

    async def _analyze_structure(self, context: NodeContext, max_tokens: int) -> dict:
        """Analyze document structure and quality."""
        text = context.current_text[:6000]

        system = """你是一个文档质量分析专家。请分析以下文档的结构完整性。

请以JSON格式返回分析结果：
{
  "quality_score": 85,
  "has_introduction": true,
  "has_conclusion": true,
  "heading_count": 5,
  "word_count": 1500,
  "issues": ["缺少结论部分"],
  "suggestions": ["建议添加总结"]
}

只返回JSON，不要其他内容。"""

        result = await llm_service.generate(
            messages=[{"role": "user", "content": f"文档标题: {context.document.get('title', '')}\n\n文档内容:\n{text}"}],
            system=system,
            max_tokens=max_tokens,
        )

        try:
            return json.loads(result)
        except json.JSONDecodeError:
            import re
            match = re.search(r"\{.*\}", result, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            return {"quality_score": 0, "issues": ["无法解析分析结果"]}

    async def _assess_quality(self, context: NodeContext, max_tokens: int) -> dict:
        """Assess document quality with detailed scoring."""
        text = context.current_text[:6000]

        system = """你是一个文档质量评估专家。请从以下维度评估文档质量：

1. 完整性（completeness_score）：是否有引言、正文、结论
2. 可读性（readability_score）：语言是否通顺、术语是否一致
3. 结构性（structure_score）：章节层次是否清晰
4. 新鲜度（freshness_score）：内容是否过时

请以JSON格式返回：
{
  "completeness_score": 80,
  "readability_score": 75,
  "structure_score": 85,
  "freshness_score": 90,
  "overall_score": 82,
  "issues": ["缺少结论"],
  "suggestions": ["建议添加总结章节"]
}

只返回JSON，不要其他内容。"""

        result = await llm_service.generate(
            messages=[{"role": "user", "content": f"文档标题: {context.document.get('title', '')}\n\n文档内容:\n{text}"}],
            system=system,
            max_tokens=max_tokens,
        )

        try:
            return json.loads(result)
        except json.JSONDecodeError:
            import re
            match = re.search(r"\{.*\}", result, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            return {"overall_score": 0, "issues": ["无法解析评估结果"]}

    async def _analyze_academic(self, context: NodeContext, max_tokens: int) -> dict:
        """Analyze academic paper structure."""
        text = context.current_text[:6000]

        system = """你是一个学术论文分析专家。请分析以下文档是否符合学术论文结构。

标准学术论文结构包括：
1. 摘要（Abstract）
2. 引言（Introduction）
3. 方法（Methodology）
4. 结果（Results）
5. 讨论（Discussion）
6. 结论（Conclusion）
7. 参考文献（References）

请以JSON格式返回：
{
  "has_abstract": true,
  "has_introduction": true,
  "has_methodology": false,
  "has_results": true,
  "has_discussion": false,
  "has_conclusion": true,
  "has_references": false,
  "completeness_score": 50,
  "missing_sections": ["方法", "讨论", "参考文献"],
  "suggestions": ["补充方法论章节"]
}

只返回JSON，不要其他内容。"""

        result = await llm_service.generate(
            messages=[{"role": "user", "content": f"文档标题: {context.document.get('title', '')}\n\n文档内容:\n{text}"}],
            system=system,
            max_tokens=max_tokens,
        )

        try:
            return json.loads(result)
        except json.JSONDecodeError:
            import re
            match = re.search(r"\{.*\}", result, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            return {"completeness_score": 0, "issues": ["无法解析分析结果"]}
