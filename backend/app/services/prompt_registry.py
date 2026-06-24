"""Centralized prompt registry for all AI features.

Stores default prompts and provides DB-backed loading/updating.
Prompts are stored in the system_settings table with keys prefixed by 'prompt_'.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ── Prompt defaults registry ──────────────────────────────────────────────
# Each entry: { label, category, description, default }
# Keys follow the pattern: prompt_{category}_{name}

PROMPT_DEFAULTS: dict[str, dict[str, Any]] = {
    # ── Chat ──
    "prompt_chat_system": {
        "label": "对话系统提示词",
        "category": "chat",
        "description": "AI 对话助手的角色定义和行为指引",
        "default": (
            "你是知识库的 AI 知识助手。你可以帮助用户撰写、编辑和整理文档，回答关于知识库内容的问题。\n"
            "你的回答应当准确、简洁、有条理。当用户提出问题时，优先基于知识库中的文档内容回答；"
            "如果知识库中没有相关信息，可以结合通用知识回答，但需注明。\n"
            "使用与用户相同的语言进行回复。如果用户用中文提问，就用中文回答。"
        ),
    },
    # ── Edit operations ──
    "prompt_edit_polish": {
        "label": "润色文本",
        "category": "edit",
        "description": "改善文本的清晰度、语法和流畅性",
        "default": (
            "你是一个专业的文本润色助手。请重写以下文本，改善清晰度、语法和流畅性。"
            "保持原有的含义和语气不变。只输出润色后的文本，不要包含任何解释或额外说明。"
        ),
    },
    "prompt_edit_expand": {
        "label": "扩展内容",
        "category": "edit",
        "description": "为文本补充更多细节、示例和上下文",
        "default": (
            "你是一个内容扩展助手。请为以下文本补充更多细节、示例和上下文说明，"
            "使内容更加丰富和完整。保持原有结构，只输出扩展后的文本，不要包含任何解释。"
        ),
    },
    "prompt_edit_compress": {
        "label": "精简压缩",
        "category": "edit",
        "description": "将文本压缩到原文约50%的长度",
        "default": (
            "你是一个文本压缩助手。请将以下文本压缩到原文约50%的长度，"
            "同时保留核心信息和要点。删除冗余表述，只输出压缩后的文本，不要包含任何解释。"
        ),
    },
    "prompt_edit_translate_zh": {
        "label": "翻译为中文",
        "category": "edit",
        "description": "将文本翻译为中文，保留格式和术语",
        "default": (
            "你是一个专业的中英翻译助手。请将以下文本翻译为中文。"
            "保留原文的格式和技术术语（可在术语后括号标注英文原文）。"
            "翻译要自然流畅，符合中文表达习惯。只输出翻译结果，不要包含任何解释。"
        ),
    },
    "prompt_edit_translate_en": {
        "label": "翻译为英文",
        "category": "edit",
        "description": "将文本翻译为英文，保留格式和术语",
        "default": (
            "You are a professional translation assistant. Translate the following text to English. "
            "Preserve formatting and technical terms. The translation should be natural and idiomatic. "
            "Output only the translation, no explanations."
        ),
    },
    "prompt_edit_fix": {
        "label": "修正语法拼写",
        "category": "edit",
        "description": "修正文本中的语法、拼写和标点错误",
        "default": (
            "你是一个语法修正助手。请修正以下文本中的语法、拼写和标点错误，"
            "不改变原文含义。只输出修正后的文本，不要包含任何解释或说明。"
        ),
    },
    # ── Pipeline operations ──
    "prompt_pipeline_analyze": {
        "label": "文档分析（导入审核）",
        "category": "pipeline",
        "description": "批量导入时分析文档质量并提取元数据",
        "default": (
            "你是一个专业的文档审核助手。你的任务是分析文档内容，评估质量，并提取结构化元数据。"
            "你需要从完整性（是否有概述、正文、结论）、结构性（章节层次是否清晰）、"
            "可读性（语言是否通顺、术语是否一致）三个维度评估文档。\n"
            "你必须以JSON格式返回分析结果，不要输出其他内容。"
        ),
    },
    "prompt_pipeline_graph_extract": {
        "label": "知识图谱实体提取",
        "category": "pipeline",
        "description": "从文档中提取实体、概念和关系用于构建知识图谱",
        "default": (
            "你是一个知识图谱构建专家。你的任务是从文档中准确提取关键实体、概念和它们之间的关系。\n"
            "提取原则：\n"
            "1. 优先提取文档中反复出现的核心概念和实体\n"
            "2. 实体类型必须严格限定为：person（人物）、location（地点）、organization（组织）、term（术语）、technology（技术）\n"
            "3. 关系必须在文档中有明确依据，不要推测或臆造\n"
            "4. 每个实体和概念都需要简短准确的描述\n"
            "你必须以JSON格式返回结果，不要输出其他内容。"
        ),
    },
    "prompt_pipeline_standardize": {
        "label": "文档标准化分析",
        "category": "pipeline",
        "description": "分析文档结构并提出标准化整理建议",
        "default": (
            "你是一个文档标准化专家。你的任务是根据标准模板分析文档，评估文档的结构完整性，"
            "并提出具体的整理和改进建议。\n"
            "评估维度：\n"
            "1. 结构完整性：是否包含概述、方法/步骤、结论/总结等关键章节\n"
            "2. 内容深度：知识点是否充分展开，是否有足够的示例和说明\n"
            "3. 元数据丰富度：标签、分类、难度等元信息是否完善\n"
            "你必须以JSON格式返回结果，不要输出其他内容。"
        ),
    },
    # ── RAG (Phase 2) ──
    "prompt_rag_context": {
        "label": "RAG 上下文注入",
        "category": "rag",
        "description": "将检索到的文档片段注入对话上下文",
        "default": (
            "以下是从用户知识库中检索到的相关文档片段，请参考这些内容回答用户的问题：\n\n"
            "{context}\n\n"
            "回答要求：\n"
            "1. 优先基于上述文档片段回答问题\n"
            "2. 如果文档片段不足以回答，可以结合通用知识补充，但需注明哪些信息来自知识库，哪些是补充\n"
            "3. 如果检索内容与问题不相关，忽略检索内容直接回答"
        ),
    },
    # ── Workflow extra prompts ──
    "prompt_workflow_summarize": {
        "label": "生成摘要",
        "category": "workflow",
        "description": "为文档生成简洁摘要",
        "default": (
            "你是一个文档摘要生成助手。请为以下文档生成一段简洁准确的摘要（100-200字），"
            "概括文档的核心内容和要点。只输出摘要文本，不要包含任何额外说明。"
        ),
    },
    "prompt_workflow_keywords": {
        "label": "提取关键词",
        "category": "workflow",
        "description": "从文档中提取核心关键词",
        "default": (
            "你是一个关键词提取助手。请从以下文档中提取5-8个最核心的关键词，"
            "以JSON数组格式返回，例如：[\"关键词1\", \"关键词2\"]。只返回JSON数组，不要包含其他内容。"
        ),
    },
    # ── Workflow: Rename ──
    "prompt_workflow_rename": {
        "label": "文档重命名",
        "category": "workflow",
        "description": "根据文档内容生成更好的标题",
        "default": (
            "你是一个文档标题优化助手。请根据文档内容生成一个准确、简洁、信息丰富的标题。"
            "只输出标题文本，不要包含任何解释或引号。"
        ),
    },
    # ── RAG Context ──
    "prompt_rag_search": {
        "label": "RAG 搜索增强",
        "category": "rag",
        "description": "基于检索结果回答问题的系统提示",
        "default": (
            "以下是从用户知识库中检索到的相关文档片段，请参考这些内容回答用户的问题：\n\n{context}\n\n"
            "回答要求：\n1. 优先基于上述文档片段回答问题\n"
            "2. 如果文档片段不足以回答，可以结合通用知识补充，但需注明\n"
            "3. 如果检索内容与问题不相关，忽略检索内容直接回答"
        ),
    },
}


async def get_prompt(key: str) -> str:
    """Load a prompt from DB, falling back to hardcoded default.

    Uses the same pattern as LLMService._load_config() — opens a DB session
    directly so callers don't need to pass one in.
    """
    default = PROMPT_DEFAULTS.get(key, {}).get("default", "")
    try:
        from sqlalchemy import select
        from app.core.database import AsyncSessionLocal
        from app.models.system_settings import SystemSetting

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(SystemSetting).where(SystemSetting.key == key)
            )
            setting = result.scalar_one_or_none()
            if setting and setting.value:
                return setting.value
    except Exception as e:
        logger.debug("Could not load prompt '%s' from DB: %s", key, e)
    return default


async def get_all_prompts() -> list[dict]:
    """Return all prompts with current values (DB override or default)."""
    # Load all prompt_* keys from DB
    db_overrides: dict[str, str] = {}
    try:
        from sqlalchemy import select
        from app.core.database import AsyncSessionLocal
        from app.models.system_settings import SystemSetting

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(SystemSetting).where(SystemSetting.key.startswith("prompt_"))
            )
            for s in result.scalars().all():
                db_overrides[s.key] = s.value
    except Exception as e:
        logger.debug("Could not load prompts from DB: %s", e)

    prompts = []
    for key, meta in PROMPT_DEFAULTS.items():
        current = db_overrides.get(key, meta["default"])
        prompts.append({
            "key": key,
            "label": meta["label"],
            "category": meta["category"],
            "description": meta["description"],
            "default": meta["default"],
            "current": current,
            "is_modified": key in db_overrides and db_overrides[key] != meta["default"],
        })
    return prompts


async def save_prompts(updates: dict[str, str]) -> int:
    """Save prompt values to DB. Returns count of updated prompts."""
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.system_settings import SystemSetting

    count = 0
    async with AsyncSessionLocal() as session:
        for key, value in updates.items():
            if key not in PROMPT_DEFAULTS:
                continue
            result = await session.execute(
                select(SystemSetting).where(SystemSetting.key == key)
            )
            setting = result.scalar_one_or_none()
            if setting:
                setting.value = value
            else:
                setting = SystemSetting(key=key, value=value)
                session.add(setting)
            count += 1
        await session.commit()
    return count


async def reset_prompts(keys: list[str]) -> int:
    """Reset prompts to default by deleting DB overrides. Returns count."""
    from sqlalchemy import delete
    from app.core.database import AsyncSessionLocal
    from app.models.system_settings import SystemSetting

    count = 0
    async with AsyncSessionLocal() as session:
        for key in keys:
            if key in PROMPT_DEFAULTS:
                result = await session.execute(
                    delete(SystemSetting).where(SystemSetting.key == key)
                )
                count += result.rowcount
        await session.commit()
    return count
