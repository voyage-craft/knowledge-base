"""Embedding generation node processor.

Triggers embedding generation for a document after content changes.
Keeps the vector index in sync for RAG search.
"""

import logging
from app.services.workflow.node_registry import NodeProcessorRegistry, NodeProcessor, NodeContext, NodeResult

logger = logging.getLogger(__name__)


@NodeProcessorRegistry.register("embedding")
class EmbeddingProcessor(NodeProcessor):
    """Generate or refresh embeddings for a document."""

    async def execute(self, context: NodeContext) -> NodeResult:
        config = context.node.get("config", {})
        force_rebuild = config.get("force_rebuild", False)

        doc_id = context.document.get("id")
        if not doc_id:
            return NodeResult(error="文档 ID 不存在")

        try:
            from app.services.embedding_service import embedding_service
            from app.models.document import Document, DocumentChunk
            from app.services.content_converter import extract_plain_text
            from sqlalchemy import select, delete

            # Get the document
            result = await context.db.execute(
                select(Document).where(Document.id == doc_id)
            )
            doc = result.scalar_one_or_none()
            if not doc:
                return NodeResult(error=f"文档 {doc_id} 不存在")

            content = doc.content_json
            if not content:
                return NodeResult(error="文档内容为空")

            # Extract plain text and chunk it
            plain_text = extract_plain_text(content)
            if not plain_text or len(plain_text) < 50:
                return NodeResult(error="文档内容太短，无需生成嵌入")

            # Delete existing embeddings if force rebuild
            if force_rebuild:
                await context.db.execute(
                    delete(DocumentChunk).where(DocumentChunk.document_id == doc_id)
                )

            # Check if embeddings already exist
            existing = await context.db.execute(
                select(DocumentChunk).where(DocumentChunk.document_id == doc_id)
            )
            if existing.scalars().first() and not force_rebuild:
                return NodeResult(
                    actions=["嵌入已存在，跳过"],
                    metadata={"document_id": doc_id, "skipped": True},
                )

            # Chunk the text (simple paragraph-based chunking)
            paragraphs = [p.strip() for p in plain_text.split("\n\n") if p.strip()]
            chunks = []
            current_chunk = ""
            for para in paragraphs:
                if len(current_chunk) + len(para) > 1000:
                    if current_chunk:
                        chunks.append(current_chunk)
                    current_chunk = para
                else:
                    current_chunk = f"{current_chunk}\n\n{para}" if current_chunk else para
            if current_chunk:
                chunks.append(current_chunk)

            if not chunks:
                return NodeResult(error="无法分块文档内容")

            # Generate embeddings
            embeddings = await embedding_service.embed(chunks)

            # Store chunks with embeddings
            import json
            for i, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
                doc_chunk = DocumentChunk(
                    document_id=doc_id,
                    user_id=getattr(doc, "user_id", None) or context.user_id or 1,
                    chunk_index=i,
                    chunk_text=chunk_text,
                    embedding=json.dumps(embedding),
                )
                context.db.add(doc_chunk)

            await context.db.commit()

            return NodeResult(
                actions=[f"生成 {len(chunks)} 个文本块的嵌入向量"],
                metadata={
                    "document_id": doc_id,
                    "chunks_created": len(chunks),
                    "total_tokens": sum(len(c) for c in chunks),
                },
            )

        except ImportError:
            return NodeResult(error="嵌入模型未安装，请运行: pip install sentence-transformers")
        except Exception as e:
            logger.error("Embedding generation failed for doc %s: %s", doc_id, e)
            return NodeResult(error=f"嵌入生成失败: {str(e)}")
