"""AI Pipeline service for document analysis, graph extraction, and standardization."""

import json
import logging
import re

from app.services.llm_service import llm_service
from app.services.prompt_registry import get_prompt

logger = logging.getLogger(__name__)


def _extract_json(text: str) -> dict | None:
    """Extract JSON from LLM response, handling markdown code fences."""
    # Try direct parse first
    text = text.strip()
    if text.startswith("{"):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

    # Try extracting from ```json ... ``` fences
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Last resort: find first { ... } block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return None


class AIPipeline:
    """Core AI analysis pipeline for document processing."""

    async def analyze_document(self, text: str, filename: str) -> dict:
        """Analyze a document for batch import review."""
        system = await get_prompt("prompt_pipeline_analyze")
        prompt = f"""请分析以下文档，并以JSON格式返回分析结果。

文件名: {filename}

文档内容:
{text[:8000]}

请返回以下JSON结构:
{{
  "title": "建议的文档标题",
  "summary": "100字以内的摘要",
  "keywords": ["关键词1", "关键词2", "关键词3"],
  "suggested_tags": ["建议标签1", "建议标签2"],
  "suggested_folder": "建议的文件夹名称",
  "issues": [
    {{"type": "格式/内容/结构", "description": "问题描述", "severity": "low/medium/high"}}
  ],
  "fixes": [
    {{"description": "修复建议", "priority": 1}}
  ],
  "quality_score": 85
}}

quality_score 范围 0-100，评估文档的完整性、结构性和可读性。"""

        result = await llm_service.generate(
            messages=[{"role": "user", "content": prompt}],
            system=system,
            max_tokens=2048,
        )

        data = _extract_json(result)
        if data is None:
            logger.warning("Failed to parse AI analysis response for %s", filename)
            return {
                "title": filename.rsplit(".", 1)[0],
                "summary": "AI分析失败，请手动审核",
                "keywords": [],
                "suggested_tags": [],
                "suggested_folder": "",
                "issues": [{"type": "系统", "description": "AI分析结果解析失败", "severity": "medium"}],
                "fixes": [],
                "quality_score": 50,
            }

        return data

    async def extract_graph_entities(self, text: str, title: str) -> dict:
        """Extract entities and concepts from a document for knowledge graph building."""
        system = await get_prompt("prompt_pipeline_graph_extract")
        prompt = f"""请从以下文档中提取实体、概念和关系，用于构建知识图谱。

文档标题: {title}

文档内容:
{text[:8000]}

请返回以下JSON结构:
{{
  "entities": [
    {{"label": "实体名称", "type": "person/location/organization/term/technology", "description": "简短描述"}}
  ],
  "concepts": [
    {{"label": "概念名称", "description": "简短描述"}}
  ],
  "relationships": [
    {{"source": "实体/概念名称", "target": "实体/概念名称", "type": "references/related_to/contains_entity/depends_on", "description": "关系描述"}}
  ]
}}

要求:
- 提取5-20个最重要的实体
- 提取3-10个核心概念
- 关系只记录明确存在的，不要臆造
- entity type 必须是: person, location, organization, term, technology 之一
- relationship type 必须是: references, related_to, contains_entity, depends_on 之一"""

        result = await llm_service.generate(
            messages=[{"role": "user", "content": prompt}],
            system=system,
            max_tokens=4096,
        )

        data = _extract_json(result)
        if data is None:
            logger.warning("Failed to parse graph extraction response for %s", title)
            return {"entities": [], "concepts": [], "relationships": []}

        data.setdefault("entities", [])
        data.setdefault("concepts", [])
        data.setdefault("relationships", [])
        return data

    async def standardize_document(self, text: str, title: str, current_tags: list[str]) -> dict:
        """Analyze a document and suggest standardization improvements."""
        system = await get_prompt("prompt_pipeline_standardize")
        tags_str = ", ".join(current_tags) if current_tags else "无"
        prompt = f"""请分析以下文档并按标准模板提出整理建议。

文档标题: {title}
当前标签: {tags_str}

文档内容:
{text[:8000]}

请返回以下JSON结构:
{{
  "structured_summary": "结构化摘要（包含目的、方法、结论等关键信息）",
  "keywords": ["关键词1", "关键词2", "关键词3", "关键词4", "关键词5"],
  "categories": ["建议分类1", "建议分类2"],
  "content_suggestions": {{
    "missing_sections": ["缺少的章节，如概述、总结等"],
    "improvements": ["内容改进建议1", "内容改进建议2"],
    "structure_score": 75
  }},
  "metadata": {{
    "difficulty": "beginner/intermediate/advanced",
    "audience": "目标受众描述",
    "document_type": "教程/笔记/报告/参考/方案"
  }}
}}

要求:
- keywords 提取5-8个最核心的关键词
- structure_score 范围 0-100
- difficulty 必须是 beginner, intermediate, advanced 之一
- document_type 必须是 教程, 笔记, 报告, 参考, 方案 之一"""

        result = await llm_service.generate(
            messages=[{"role": "user", "content": prompt}],
            system=system,
            max_tokens=2048,
        )

        data = _extract_json(result)
        if data is None:
            logger.warning("Failed to parse standardization response for %s", title)
            return {
                "structured_summary": "AI分析失败",
                "keywords": [],
                "categories": [],
                "content_suggestions": {"missing_sections": [], "improvements": [], "structure_score": 0},
                "metadata": {"difficulty": "intermediate", "audience": "", "document_type": "笔记"},
            }

        return data

    async def generate_document(
        self,
        requirements: str,
        title: str = "",
        document_type: str = "",
        language: str = "zh",
        max_sections: int = 10,
        target_length: str = "medium",
    ) -> dict:
        """Generate a full document from requirements using two-phase AI generation."""
        lang = "中文" if language == "zh" else "English"
        length_guide = {"short": "每章节200-400字", "medium": "每章节400-800字", "long": "每章节800-1500字"}.get(target_length, "每章节400-800字")

        # Phase 1: Generate outline
        outline_system = "你是一个专业的文档大纲规划师。根据用户需求生成结构化的文档大纲。只返回JSON格式，不要包含其他内容。"
        outline_prompt = f"""需求: {requirements}
文档类型: {document_type or '通用'}
语言: {lang}
最大章节数: {max_sections}

请返回JSON格式的大纲:
{{
  "title": "生成的文档标题",
  "sections": [
    {{"heading": "章节标题", "level": 1, "key_points": ["要点1", "要点2"]}}
  ]
}}"""

        outline_raw = await llm_service.generate(
            messages=[{"role": "user", "content": outline_prompt}],
            system=outline_system,
            max_tokens=2048,
        )
        outline = _extract_json(outline_raw)
        if not outline:
            raise ValueError("AI大纲生成失败，请重试")

        doc_title = title or outline.get("title", "新文档")
        sections = outline.get("sections", [])[:max_sections]

        # Phase 2: Expand each section
        content_nodes = []
        for section in sections:
            section_system = "你是一个专业的技术写作助手。根据给定的章节标题和关键要点，生成详实的章节内容。只输出正文内容，不要重复标题。"
            section_prompt = f"""章节标题: {section['heading']}
关键要点: {', '.join(section.get('key_points', []))}
文档需求: {requirements}
目标长度: {length_guide}

请生成该章节的完整内容。"""

            section_text = await llm_service.generate(
                messages=[{"role": "user", "content": section_prompt}],
                system=section_system,
                max_tokens=2048,
            )

            level = section.get("level", 1)
            level = max(1, min(level, 6))
            content_nodes.append({
                "type": "heading",
                "attrs": {"level": level},
                "content": [{"type": "text", "text": section["heading"]}],
            })
            # Convert generated text to paragraphs
            for para_text in section_text.strip().split("\n\n"):
                if para_text.strip():
                    content_nodes.append({
                        "type": "paragraph",
                        "content": [{"type": "text", "text": para_text.strip()}],
                    })

        return {
            "title": doc_title,
            "content_json": {"type": "doc", "content": content_nodes},
            "sections_generated": len(sections),
        }


ai_pipeline = AIPipeline()
