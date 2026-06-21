"""Preset workflow templates for common document processing tasks.

Each template defines a node graph that the workflow engine can execute.

Basic Node types:
  - source: document input filter (by folder, tag, status, or all)
  - polish / expand / compress / translate_zh / translate_en / fix: edit operations
  - summarize / keywords / auto_tag: metadata extraction
  - standardize: document standardization analysis
  - custom_prompt: user-defined prompt
  - save: save changes back to document
  - export: export processed documents

Advanced Node types (v2):
  - condition: conditional branching based on data
  - ai_analyze: AI-powered document analysis (TOC, structure, quality)
  - format_convert: convert between formats (LaTeX, HTML, DOCX, Markdown)
  - loop: iterate over items (coming soon)
  - approval: human review pause point (coming soon)
"""

from typing import Any


def _node(node_id: str, node_type: str, label: str, config: dict | None = None) -> dict:
    return {
        "id": node_id,
        "type": node_type,
        "label": label,
        "config": config or {},
    }


def _edge(source: str, target: str) -> dict:
    return {"source": source, "target": target}


# ═══════════════════════════════════════════════════════════════════════
# Basic Templates
# ═══════════════════════════════════════════════════════════════════════

# ── Template: Batch Polish ──────────────────────────────────────────────
BATCH_POLISH: dict[str, Any] = {
    "name": "批量润色",
    "description": "自动润色选中的文档，改善语法和流畅性",
    "category": "basic",
    "nodes": [
        _node("source", "source", "文档来源", {"filter": "all"}),
        _node("polish", "polish", "AI 润色"),
        _node("save", "save", "保存文档"),
    ],
    "edges": [
        _edge("source", "polish"),
        _edge("polish", "save"),
    ],
}

# ── Template: Summarize + Tag ───────────────────────────────────────────
SUMMARIZE_TAG: dict[str, Any] = {
    "name": "智能摘要 + 打标签",
    "description": "为文档生成摘要并自动提取关键词作为标签",
    "category": "basic",
    "nodes": [
        _node("source", "source", "文档来源", {"filter": "all"}),
        _node("summarize", "summarize", "生成摘要"),
        _node("keywords", "keywords", "提取关键词"),
        _node("auto_tag", "auto_tag", "自动打标签"),
        _node("save", "save", "保存文档"),
    ],
    "edges": [
        _edge("source", "summarize"),
        _edge("source", "keywords"),
        _edge("summarize", "auto_tag"),
        _edge("keywords", "auto_tag"),
        _edge("auto_tag", "save"),
    ],
}

# ── Template: Batch Translate ───────────────────────────────────────────
BATCH_TRANSLATE: dict[str, Any] = {
    "name": "批量翻译",
    "description": "将文档批量翻译为目标语言（默认翻译为英文）",
    "category": "basic",
    "nodes": [
        _node("source", "source", "文档来源", {"filter": "all"}),
        _node("translate", "translate_en", "翻译为英文"),
        _node("save", "save", "保存为新文档", {"mode": "new"}),
    ],
    "edges": [
        _edge("source", "translate"),
        _edge("translate", "save"),
    ],
}

# ── Template: Document Standardize ──────────────────────────────────────
STANDARDIZE: dict[str, Any] = {
    "name": "文档标准化",
    "description": "分析文档结构，生成标准化摘要和改进建议",
    "category": "basic",
    "nodes": [
        _node("source", "source", "文档来源", {"filter": "all"}),
        _node("standardize", "standardize", "标准化分析"),
        _node("summarize", "summarize", "生成摘要"),
        _node("save", "save", "保存文档"),
    ],
    "edges": [
        _edge("source", "standardize"),
        _edge("source", "summarize"),
        _edge("standardize", "save"),
        _edge("summarize", "save"),
    ],
}

# ── Template: Content Expand ────────────────────────────────────────────
CONTENT_EXPAND: dict[str, Any] = {
    "name": "内容扩展",
    "description": "为内容较短的文档自动扩展补充细节和示例",
    "category": "basic",
    "nodes": [
        _node("source", "source", "文档来源", {"filter": "all"}),
        _node("expand", "expand", "AI 内容扩展"),
        _node("polish", "polish", "润色优化"),
        _node("save", "save", "保存文档"),
    ],
    "edges": [
        _edge("source", "expand"),
        _edge("expand", "polish"),
        _edge("polish", "save"),
    ],
}


# ═══════════════════════════════════════════════════════════════════════
# Advanced Templates (v2 - with condition, ai_analyze, format_convert)
# ═══════════════════════════════════════════════════════════════════════

# ── Template: Document Publishing Pipeline ──────────────────────────────
DOCUMENT_PUBLISHING: dict[str, Any] = {
    "name": "文档出版流水线",
    "description": "完整的文档处理到出版流程：AI分析、质量检查、智能润色、排版、导出",
    "category": "advanced",
    "nodes": [
        _node("source", "source", "文档来源", {"filter": "all"}),
        _node("analyze", "ai_analyze", "结构分析", {
            "analysis_type": "toc_extraction",
            "output_field": "toc_data",
        }),
        _node("quality_check", "condition", "质量检查", {
            "field": "quality_score",
            "operator": "gte",
            "value": 60,
            "true_branch": "polish",
            "false_branch": "fix_structure",
        }),
        _node("fix_structure", "custom_prompt", "修复结构", {
            "prompt": "请为以下文档补充缺失的章节结构，添加概述和总结部分。保持原有内容不变，只补充结构。"
        }),
        _node("polish", "polish", "AI润色"),
        _node("summarize", "summarize", "生成摘要"),
        _node("keywords", "keywords", "提取关键词"),
        _node("auto_tag", "auto_tag", "自动标签"),
        _node("format", "format_convert", "LaTeX转换", {
            "output_format": "latex",
        }),
        _node("save", "save", "保存文档"),
    ],
    "edges": [
        _edge("source", "analyze"),
        _edge("analyze", "quality_check"),
        _edge("fix_structure", "polish"),
        _edge("polish", "summarize"),
        _edge("polish", "keywords"),
        _edge("summarize", "auto_tag"),
        _edge("keywords", "auto_tag"),
        _edge("auto_tag", "format"),
        _edge("format", "save"),
    ],
}

# ── Template: Academic Paper Processing ─────────────────────────────────
ACADEMIC_PAPER: dict[str, Any] = {
    "name": "学术论文处理流程",
    "description": "学术论文标准化处理：结构检查、章节补充、参考文献格式化、LaTeX转换",
    "category": "advanced",
    "nodes": [
        _node("source", "source", "论文来源", {"filter": "tag", "tag_name": "论文"}),
        _node("analyze", "ai_analyze", "论文结构分析", {
            "analysis_type": "academic_structure",
            "output_field": "academic_analysis",
        }),
        _node("structure_check", "condition", "结构完整性", {
            "field": "academic_analysis.completeness_score",
            "operator": "gte",
            "value": 70,
            "true_branch": "format_refs",
            "false_branch": "add_sections",
        }),
        _node("add_sections", "custom_prompt", "补充章节", {
            "prompt": "请为以下学术论文补充缺失的标准章节（摘要、引言、方法、结果、讨论、结论）。保持已有内容不变。"
        }),
        _node("format_refs", "custom_prompt", "参考文献格式化", {
            "prompt": "请将以下文档中的参考文献统一格式化为IEEE引用格式。"
        }),
        _node("latex_convert", "format_convert", "LaTeX转换", {
            "output_format": "latex",
        }),
        _node("save", "save", "保存"),
    ],
    "edges": [
        _edge("source", "analyze"),
        _edge("analyze", "structure_check"),
        _edge("add_sections", "format_refs"),
        _edge("structure_check", "format_refs"),
        _edge("format_refs", "latex_convert"),
        _edge("latex_convert", "save"),
    ],
}

# ── Template: Technical Documentation Standardization ───────────────────
TECH_DOC_STANDARDIZE: dict[str, Any] = {
    "name": "技术文档标准化流程",
    "description": "技术文档标准化：术语统一、代码块格式化、质量评估",
    "category": "advanced",
    "nodes": [
        _node("source", "source", "文档来源", {"filter": "status", "status": "draft"}),
        _node("assess", "ai_analyze", "质量评估", {
            "analysis_type": "quality_assessment",
            "output_field": "quality_result",
        }),
        _node("quality_check", "condition", "质量检查", {
            "field": "quality_result.overall_score",
            "operator": "gte",
            "value": 80,
            "true_branch": "polish",
            "false_branch": "standardize",
        }),
        _node("standardize", "standardize", "标准化分析"),
        _node("polish", "polish", "润色"),
        _node("code_format", "custom_prompt", "代码格式化", {
            "prompt": "请规范化以下文档中的代码块，确保代码缩进一致、语言标注正确、添加必要的注释。"
        }),
        _node("keywords", "keywords", "提取关键词"),
        _node("auto_tag", "auto_tag", "自动标签"),
        _node("save", "save", "保存"),
    ],
    "edges": [
        _edge("source", "assess"),
        _edge("assess", "quality_check"),
        _edge("quality_check", "polish"),
        _edge("quality_check", "standardize"),
        _edge("standardize", "polish"),
        _edge("polish", "code_format"),
        _edge("code_format", "keywords"),
        _edge("keywords", "auto_tag"),
        _edge("auto_tag", "save"),
    ],
}

# ── Template: Multi-Language Translation ────────────────────────────────
MULTI_LANGUAGE_TRANSLATE: dict[str, Any] = {
    "name": "多语言翻译流程",
    "description": "文档多语言翻译：先翻译为英文，再从英文翻译为其他语言，保存多语言版本",
    "category": "advanced",
    "nodes": [
        _node("source", "source", "文档来源", {"filter": "all"}),
        _node("translate_en", "translate_en", "翻译为英文"),
        _node("save_en", "save", "保存英文版", {"mode": "new", "suffix": "(EN)"}),
        _node("translate_zh", "translate_zh", "翻译为中文"),
        _node("save_zh", "save", "保存中文版", {"mode": "new", "suffix": "(ZH)"}),
    ],
    "edges": [
        _edge("source", "translate_en"),
        _edge("translate_en", "save_en"),
        _edge("save_en", "translate_zh"),
        _edge("translate_zh", "save_zh"),
    ],
}

# ── Template: Quality Assessment Pipeline ───────────────────────────────
QUALITY_ASSESSMENT: dict[str, Any] = {
    "name": "文档质量评估流程",
    "description": "评估文档质量并根据分数进行不同处理：高分直接保存，低分进行润色改进",
    "category": "advanced",
    "nodes": [
        _node("source", "source", "文档来源", {"filter": "all"}),
        _node("assess", "ai_analyze", "质量评估", {
            "analysis_type": "quality_assessment",
            "output_field": "quality_result",
        }),
        _node("quality_check", "condition", "质量检查", {
            "field": "quality_result.overall_score",
            "operator": "gte",
            "value": 80,
            "true_branch": "save",
            "false_branch": "improve",
        }),
        _node("improve", "polish", "AI润色"),
        _node("save", "save", "保存"),
    ],
    "edges": [
        _edge("source", "assess"),
        _edge("assess", "quality_check"),
        _edge("quality_check", "save"),
        _edge("quality_check", "improve"),
        _edge("improve", "save"),
    ],
}

# ── Template: Batch Export Pipeline ─────────────────────────────────────
BATCH_EXPORT: dict[str, Any] = {
    "name": "批量导出流水线",
    "description": "批量处理并导出文档为多种格式（LaTeX、DOCX）",
    "category": "advanced",
    "nodes": [
        _node("source", "source", "文档来源", {"filter": "all"}),
        _node("polish", "polish", "AI润色"),
        _node("to_latex", "format_convert", "转换为LaTeX", {
            "output_format": "latex",
        }),
        _node("export_docx", "export", "导出DOCX", {
            "format": "docx",
        }),
        _node("save", "save", "保存"),
    ],
    "edges": [
        _edge("source", "polish"),
        _edge("polish", "to_latex"),
        _edge("polish", "export_docx"),
        _edge("polish", "save"),
    ],
}

# ── Template: TOC Analysis + Export ─────────────────────────────────────
TOC_ANALYSIS_EXPORT: dict[str, Any] = {
    "name": "目录分析与导出",
    "description": "分析文档结构生成目录，然后导出为LaTeX格式",
    "category": "advanced",
    "nodes": [
        _node("source", "source", "文档来源", {"filter": "all"}),
        _node("analyze", "ai_analyze", "目录分析", {
            "analysis_type": "toc_extraction",
            "output_field": "toc_data",
        }),
        _node("format", "format_convert", "LaTeX转换", {
            "output_format": "latex",
        }),
        _node("save", "save", "保存"),
    ],
    "edges": [
        _edge("source", "analyze"),
        _edge("analyze", "format"),
        _edge("format", "save"),
    ],
}


# ═══════════════════════════════════════════════════════════════════════
# Registry
# ═══════════════════════════════════════════════════════════════════════

PRESET_TEMPLATES: dict[str, dict[str, Any]] = {
    # Basic templates
    "batch_polish": BATCH_POLISH,
    "summarize_tag": SUMMARIZE_TAG,
    "batch_translate": BATCH_TRANSLATE,
    "standardize": STANDARDIZE,
    "content_expand": CONTENT_EXPAND,
    # Advanced templates (v2)
    "document_publishing": DOCUMENT_PUBLISHING,
    "academic_paper": ACADEMIC_PAPER,
    "tech_doc_standardize": TECH_DOC_STANDARDIZE,
    "multi_language_translate": MULTI_LANGUAGE_TRANSLATE,
    "quality_assessment": QUALITY_ASSESSMENT,
    "batch_export": BATCH_EXPORT,
    "toc_analysis_export": TOC_ANALYSIS_EXPORT,
}


def get_template(template_key: str) -> dict[str, Any] | None:
    """Get a preset template by key."""
    return PRESET_TEMPLATES.get(template_key)


def list_templates() -> list[dict[str, Any]]:
    """List all preset templates with their keys."""
    return [
        {"key": key, **tmpl}
        for key, tmpl in PRESET_TEMPLATES.items()
    ]


def list_templates_by_category(category: str | None = None) -> list[dict[str, Any]]:
    """List templates filtered by category."""
    if category is None:
        return list_templates()
    return [
        {"key": key, **tmpl}
        for key, tmpl in PRESET_TEMPLATES.items()
        if tmpl.get("category") == category
    ]
