"""Source node processor - fetches documents matching filter criteria.

Supports filters:
- all: All user documents
- folder: Documents in a specific folder
- tag: Documents with a specific tag
- status: Documents with a specific status
- ids: Specific document IDs (new in v2)
"""

import logging
from sqlalchemy import select
from app.models.document import Document, Tag, document_tags
from app.services.workflow.node_registry import NodeProcessorRegistry, NodeProcessor, NodeContext, NodeResult

logger = logging.getLogger(__name__)


@NodeProcessorRegistry.register("source")
class SourceProcessor(NodeProcessor):
    """Fetch documents matching the source filter criteria."""

    async def execute(self, context: NodeContext) -> NodeResult:
        cfg = context.node.get("config", {})
        filt = cfg.get("filter", "all")

        query = select(Document).where(
            Document.user_id == context.user_id,
            Document.status != "deleted",
        )

        # Filter by specific document IDs (new in v2)
        if filt == "ids" and cfg.get("document_ids"):
            doc_ids = cfg["document_ids"]
            query = query.where(Document.id.in_(doc_ids))

        # Filter by folder
        elif filt == "folder" and cfg.get("folder_id"):
            query = query.where(Document.folder_id == cfg["folder_id"])

        # Filter by tag
        elif filt == "tag" and cfg.get("tag_name"):
            tag_result = await context.db.execute(
                select(Tag.id).where(
                    Tag.user_id == context.user_id,
                    Tag.name == cfg["tag_name"]
                )
            )
            tag_ids = [r[0] for r in tag_result.all()]
            if tag_ids:
                doc_tag_q = select(document_tags.c.document_id).where(
                    document_tags.c.tag_id.in_(tag_ids)
                )
                query = query.where(Document.id.in_(doc_tag_q))

        # Filter by status
        elif filt == "status" and cfg.get("status"):
            query = query.where(Document.status == cfg["status"])

        result = await context.db.execute(query)
        docs = result.scalars().all()

        # Build document list
        from app.services.content_converter import extract_plain_text
        documents = []
        for doc in docs:
            text = doc.plain_text or extract_plain_text(doc.content_json) or doc.title
            documents.append({
                "id": doc.id,
                "title": doc.title,
                "text": text,
                "content_json": doc.content_json,
            })

        logger.info("Source node fetched %d documents", len(documents))

        return NodeResult(
            output_data={"documents": documents},
            actions=[f"获取{len(documents)}个文档"],
            metadata={"document_count": len(documents)},
        )
