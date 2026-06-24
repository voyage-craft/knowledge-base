"""Document rename node processor.

Analyzes document content and suggests a better title using AI.
Supports multiple naming styles and optional auto-apply.
"""

import logging
from app.services.workflow.node_registry import NodeProcessorRegistry, NodeProcessor, NodeContext, NodeResult
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)

# Reuse the error detection from prompt node
def _is_llm_error(result: str) -> bool:
    if not result or not result.strip():
        return True
    error_markers = ["[LLM error:", "[LLM 未配置:", "[LLM 提供商未配置]", "[Stream error:", "[流式传输错误:"]
    for marker in error_markers:
        if result.startswith(marker):
            return True
    return False


STYLE_PROMPTS = {
    "descriptive": "生成一个描述性的标题，准确概括文档核心内容",
    "concise": "生成一个简洁的标题，尽可能简短但信息丰富",
    "academic": "生成一个学术风格的标题，使用专业术语",
    "keyword_prefix": "生成一个以关键词开头的标题，便于搜索和分类",
    "question": "生成一个以问题形式呈现的标题",
}


@NodeProcessorRegistry.register("rename")
class RenameProcessor(NodeProcessor):
    """Analyze document content and suggest a better title."""

    async def execute(self, context: NodeContext) -> NodeResult:
        config = context.node.get("config", {})
        style = config.get("style", "descriptive")
        max_length = config.get("max_length", 80)
        auto_apply = config.get("auto_apply", False)

        current_title = context.document.get("title", "")
        content = context.current_text[:4000] if context.current_text else ""

        if not content:
            return NodeResult(error="文档内容为空，无法生成标题")

        style_instruction = STYLE_PROMPTS.get(style, STYLE_PROMPTS["descriptive"])

        system = "你是一个文档标题优化助手。根据文档内容生成更好的标题。只输出标题文本，不要包含任何解释或引号。"
        prompt = f"""当前标题: {current_title}

文档内容:
{content}

要求: {style_instruction}
最长 {max_length} 字符。
只返回建议的标题，不要包含任何其他内容。"""

        try:
            new_title = (await llm_service.generate(
                messages=[{"role": "user", "content": prompt}],
                system=system,
                max_tokens=256,
            )).strip().strip('"').strip("'").strip()
        except Exception as e:
            logger.error("Rename LLM call failed: %s", e)
            return NodeResult(error=f"标题生成失败: {str(e)}")

        if not new_title or _is_llm_error(new_title):
            return NodeResult(error="标题生成失败，AI 返回了无效结果")

        # Truncate to max_length
        if len(new_title) > max_length:
            new_title = new_title[:max_length].rsplit(" ", 1)[0]

        # Store in accumulated_data for downstream nodes
        context.accumulated_data["suggested_title"] = new_title
        context.accumulated_data["old_title"] = current_title

        # Auto-apply if configured
        if auto_apply:
            try:
                from app.models.document import Document
                from sqlalchemy import select
                result = await context.db.execute(
                    select(Document).where(Document.id == context.document["id"])
                )
                doc = result.scalar_one_or_none()
                if doc:
                    # Create version snapshot before rename
                    from app.models.document import DocumentVersion
                    version = DocumentVersion(
                        document_id=doc.id,
                        version_number=doc.version,
                        title=doc.title,
                        content_json=doc.content_json,
                    )
                    context.db.add(version)
                    doc.title = new_title
                    doc.version += 1
                    context.document["title"] = new_title
                    await context.db.commit()
            except Exception as e:
                logger.error("Auto-rename failed for doc %s: %s", context.document.get("id"), e)
                return NodeResult(error=f"自动重命名失败: {str(e)}")

        return NodeResult(
            actions=[f"重命名: '{current_title}' → '{new_title}'"],
            metadata={
                "new_title": new_title,
                "old_title": current_title,
                "style": style,
                "auto_applied": auto_apply,
            },
        )
