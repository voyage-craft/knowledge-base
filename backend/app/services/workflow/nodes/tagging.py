"""Tagging node processor - automatic tag assignment.

Node types:
- auto_tag: Assign tags based on extracted keywords
"""

import logging
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from app.models.document import Tag, document_tags
from app.services.workflow.node_registry import NodeProcessorRegistry, NodeProcessor, NodeContext, NodeResult

logger = logging.getLogger(__name__)


@NodeProcessorRegistry.register("auto_tag")
class AutoTagProcessor(NodeProcessor):
    """Assign tags to documents based on extracted keywords."""

    async def execute(self, context: NodeContext) -> NodeResult:
        config = context.node.get("config", {})
        max_tags = int(config.get("max_tags", 5))
        create_new_tags = bool(config.get("create_new_tags", True))
        tag_source = config.get("tag_source", "keywords")

        keywords = context.accumulated_data.get("keywords", [])

        # If tag_source is "ai_generated" and no keywords available, generate tags via LLM
        if tag_source == "ai_generated" and not keywords:
            try:
                import re as _re
                import json as _json
                from app.services.llm_service import llm_service

                title = context.document.get("title", "")
                text_preview = context.current_text[:2000] if context.current_text else ""
                llm_prompt = (
                    f"Based on the following document, suggest up to {max_tags} relevant tags "
                    f"as a JSON array of strings.\n\n"
                    f"Title: {title}\n\nContent:\n{text_preview}"
                )
                llm_result = await llm_service.generate(
                    messages=[{"role": "user", "content": llm_prompt}],
                    system="You are a tagging assistant. Return only a JSON array of tag strings.",
                    max_tokens=256,
                )
                match = _re.search(r"\[.*?\]", llm_result, _re.DOTALL)
                if match:
                    try:
                        keywords = _json.loads(match.group(0))
                    except _json.JSONDecodeError:
                        pass
            except Exception as e:
                logger.warning("AI tag generation failed: %s", e)

        if not keywords:
            return NodeResult(actions=["自动打标签(无关键词)"])

        # Deduplicate while preserving order, then limit to max_tags
        keywords = list(dict.fromkeys(keywords))[:max_tags]

        assigned_count = 0
        for kw in keywords:
            if not kw or not isinstance(kw, str):
                continue

            # Find existing tag
            tag_result = await context.db.execute(
                select(Tag).where(
                    Tag.user_id == context.user_id,
                    Tag.name == kw
                )
            )
            tag = tag_result.scalar_one_or_none()

            if not tag:
                if not create_new_tags:
                    continue  # Skip if we are not allowed to create new tags
                tag = Tag(name=kw, user_id=context.user_id)
                context.db.add(tag)
                await context.db.flush()

            # Assign tag to document
            stmt = sqlite_insert(document_tags).values(
                document_id=context.document["id"],
                tag_id=tag.id
            ).on_conflict_do_nothing()
            await context.db.execute(stmt)
            assigned_count += 1

        return NodeResult(
            actions=[f"自动打标签({assigned_count}个)"],
            metadata={
                "tags_assigned": assigned_count,
                "max_tags": max_tags,
                "create_new_tags": create_new_tags,
                "tag_source": tag_source,
            },
        )
