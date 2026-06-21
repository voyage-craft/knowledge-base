"""Enhanced workflow templates with advanced node types.

This module provides pre-built workflow templates that leverage
the new node types: condition, format_convert, ai_analyze, etc.
"""


def _node(node_id: str, node_type: str, label: str, config: dict = None) -> dict:
    """Helper to create a node configuration."""
    node = {"id": node_id, "type": node_type, "label": label}
    if config:
        node["config"] = config
    return node


def _edge(source: str, target: str) -> dict:
    """Helper to create an edge configuration."""
    return {"source": source, "target": target}


# ── Document Publishing Pipeline ─────────────────────────────────────────

DOCUMENT_PUBLISHING = {
    "name": "文档出版流水线",
    "description": "完整的文档处理到出版流程：分析、标准化、排版、导出",
    "category": "publishing",
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
        _node("format", "format_convert", "格式转换", {
            "output_format": "latex",
        }),
        _node("export", "export", "导出PDF", {
            "format": "pdf",
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
        _edge("format", "export"),
        _edge("format", "save"),
    ],
}


# ── Academic Paper Processing ────────────────────────────────────────────

ACADEMIC_PAPER = {
    "name": "学术论文处理流程",
    "description": "学术论文标准化处理：结构检查、参考文献格式化、LaTeX编译",
    "category": "academic",
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


# ── Technical Documentation Standardization ──────────────────────────────

TECH_DOC_STANDARDIZE = {
    "name": "技术文档标准化流程",
    "description": "技术文档标准化：术语统一、代码块格式化、API文档生成",
    "category": "technical",
    "nodes": [
        _node("source", "source", "文档来源", {"filter": "status", "status": "draft"}),
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
        _edge("source", "standardize"),
        _edge("source", "code_format"),
        _edge("standardize", "polish"),
        _edge("code_format", "polish"),
        _edge("polish", "keywords"),
        _edge("keywords", "auto_tag"),
        _edge("auto_tag", "save"),
    ],
}


# ── Multi-Language Translation Pipeline ──────────────────────────────────

MULTI_LANGUAGE_TRANSLATE = {
    "name": "多语言翻译流程",
    "description": "文档多语言翻译：先翻译为英文，再从英文翻译为其他语言",
    "category": "translation",
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


# ── Document Quality Assessment ──────────────────────────────────────────

QUALITY_ASSESSMENT = {
    "name": "文档质量评估流程",
    "description": "评估文档质量并根据分数进行不同处理",
    "category": "quality",
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


# ── Batch Export Pipeline ────────────────────────────────────────────────

BATCH_EXPORT = {
    "name": "批量导出流水线",
    "description": "批量处理并导出文档为多种格式",
    "category": "export",
    "nodes": [
        _node("source", "source", "文档来源", {"filter": "all"}),
        _node("polish", "polish", "AI润色"),
        _node("to_latex", "format_convert", "转换为LaTeX", {
            "output_format": "latex",
        }),
        _node("export_pdf", "export", "导出PDF", {
            "format": "pdf",
        }),
        _node("export_docx", "export", "导出DOCX", {
            "format": "docx",
        }),
        _node("save", "save", "保存"),
    ],
    "edges": [
        _edge("source", "polish"),
        _edge("polish", "to_latex"),
        _edge("to_latex", "export_pdf"),
        _edge("to_latex", "export_docx"),
        _edge("polish", "save"),
    ],
}


# ── All templates registry ───────────────────────────────────────────────

ENHANCED_TEMPLATES = {
    "document_publishing": DOCUMENT_PUBLISHING,
    "academic_paper": ACADEMIC_PAPER,
    "tech_doc_standardize": TECH_DOC_STANDARDIZE,
    "multi_language_translate": MULTI_LANGUAGE_TRANSLATE,
    "quality_assessment": QUALITY_ASSESSMENT,
    "batch_export": BATCH_EXPORT,
}
