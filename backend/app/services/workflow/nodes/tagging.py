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
        keywords = context.accumulated_data.get("keywords", [])

        if not keywords:
            return NodeResult(actions=["自动打标签(无关键词)"])

        assigned_count = 0
        for kw in set(keywords):
            if not kw or not isinstance(kw, str):
                continue

            # Find or create tag
            tag_result = await context.db.execute(
                select(Tag).where(
                    Tag.user_id == context.user_id,
                    Tag.name == kw
                )
            )
            tag = tag_result.scalar_one_or_none()

            if not tag:
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
            metadata={"tags_assigned": assigned_count},
        )
