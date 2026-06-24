"""Set metadata node processor.

Update document metadata (folder, status, tags) without touching content.
Works with condition nodes for quality-based routing workflows.
"""

import logging
from app.services.workflow.node_registry import NodeProcessorRegistry, NodeProcessor, NodeContext, NodeResult

logger = logging.getLogger(__name__)


@NodeProcessorRegistry.register("set_metadata")
class SetMetadataProcessor(NodeProcessor):
    """Update document metadata fields."""

    async def execute(self, context: NodeContext) -> NodeResult:
        config = context.node.get("config", {})
        actions_taken = []

        try:
            from app.models.document import Document, Tag, document_tags
            from sqlalchemy import select

            result = await context.db.execute(
                select(Document).where(Document.id == context.document["id"])
            )
            doc = result.scalar_one_or_none()
            if not doc:
                return NodeResult(error=f"文档 {context.document['id']} 不存在")

            # Update status
            new_status = config.get("status")
            if new_status:
                if new_status not in ("draft", "published", "archived"):
                    return NodeResult(error=f"无效状态: {new_status}")
                old_status = doc.status
                doc.status = new_status
                actions_taken.append(f"状态: {old_status} → {new_status}")

            # Update folder
            folder_id = config.get("folder_id")
            if folder_id is not None:
                doc.folder_id = int(folder_id) if folder_id else None
                actions_taken.append(f"文件夹: {folder_id}")

            # Add tags
            add_tags = config.get("add_tags", [])
            if add_tags:
                user_id = doc.user_id or 1
                for tag_name in add_tags:
                    if not tag_name.strip():
                        continue
                    tag_result = await context.db.execute(
                        select(Tag).where(Tag.name == tag_name.strip())
                    )
                    tag = tag_result.scalar_one_or_none()
                    if not tag:
                        tag = Tag(name=tag_name.strip(), user_id=user_id)
                        context.db.add(tag)
                        await context.db.flush()
                    # Check if already tagged
                    existing = await context.db.execute(
                        select(document_tags).where(
                            document_tags.c.document_id == doc.id,
                            document_tags.c.tag_id == tag.id,
                        )
                    )
                    if not existing.first():
                        await context.db.execute(
                            document_tags.insert().values(document_id=doc.id, tag_id=tag.id)
                        )
                actions_taken.append(f"添加标签: {', '.join(add_tags)}")

            # Remove tags
            remove_tags = config.get("remove_tags", [])
            if remove_tags:
                for tag_name in remove_tags:
                    tag_result = await context.db.execute(
                        select(Tag).where(Tag.name == tag_name.strip())
                    )
                    tag = tag_result.scalar_one_or_none()
                    if tag:
                        await context.db.execute(
                            document_tags.delete().where(
                                document_tags.c.document_id == doc.id,
                                document_tags.c.tag_id == tag.id,
                            )
                        )
                actions_taken.append(f"移除标签: {', '.join(remove_tags)}")

            # Use accumulated data for dynamic values
            # e.g., condition node sets accumulated_data["target_folder"]
            acc_folder = context.accumulated_data.get("target_folder")
            if acc_folder and not folder_id:
                doc.folder_id = int(acc_folder)
                actions_taken.append(f"文件夹(动态): {acc_folder}")

            await context.db.commit()

            return NodeResult(
                actions=actions_taken,
                metadata={"document_id": doc.id, "changes": actions_taken},
            )

        except Exception as e:
            logger.error("Set metadata failed for doc %s: %s", context.document.get("id"), e)
            return NodeResult(error=f"元数据更新失败: {str(e)}")
