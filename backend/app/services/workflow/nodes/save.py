"""Save node processor - persist processed content to database.

Node types:
- save: Save processed text back to the document
"""

import logging
from app.services.workflow.node_registry import NodeProcessorRegistry, NodeProcessor, NodeContext, NodeResult
from app.models.document import Document

logger = logging.getLogger(__name__)


@NodeProcessorRegistry.register("save")
class SaveProcessor(NodeProcessor):
    """Save processed content back to the document."""

    async def execute(self, context: NodeContext) -> NodeResult:
        save_mode = context.node.get("config", {}).get("mode", "overwrite")
        suffix = context.node.get("config", {}).get("suffix", "")

        target_doc = await context.db.get(Document, context.document["id"])
        if not target_doc:
            return NodeResult(error=f"文档 {context.document['id']} 不存在")

        # Prepare content
        current_text = context.current_text

        if save_mode == "new" and suffix:
            # Create new document with suffix
            from app.models.document import Document as DocModel
            new_doc = DocModel(
                title=f"{target_doc.title} {suffix}",
                content_json=target_doc.content_json,
                plain_text=current_text,
                user_id=context.user_id,
                folder_id=target_doc.folder_id,
            )
            context.db.add(new_doc)
            await context.db.flush()
            logger.info("Created new document '%s' (mode=new)", new_doc.title)
            return NodeResult(
                actions=[f"保存为新文档: {new_doc.title}"],
                metadata={"new_doc_id": new_doc.id},
            )
        else:
            # Overwrite existing document
            target_doc.plain_text = current_text

            # Wrap as TipTap paragraphs
            paragraphs = current_text.split("\n\n")
            content_nodes = []
            for p in paragraphs:
                p = p.strip()
                if p:
                    content_nodes.append({
                        "type": "paragraph",
                        "content": [{"type": "text", "text": p}],
                    })
            target_doc.content_json = {
                "type": "doc",
                "content": content_nodes,
            }

            logger.info("Saved document %d (mode=overwrite)", target_doc.id)
            return NodeResult(
                actions=["保存"],
                metadata={"doc_id": target_doc.id},
            )
