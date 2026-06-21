"""MCP tool: AI analysis of documents."""

from app.mcp.server import mcp
from app.core.database import AsyncSessionLocal
from app.models.document import Document
from sqlalchemy import select


@mcp.tool()
async def summarize_document(document_id: int) -> dict:
    """Generate an AI summary of a document. Returns structured summary, keywords, and metadata."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Document).where(Document.id == document_id))
        doc = result.scalar_one_or_none()
        if not doc:
            return {"error": f"Document {document_id} not found"}

        text = doc.plain_text or ""
        if not text:
            return {"error": "Document has no text content"}

        if len(text) < 50:
            return {"error": "Document too short to summarize"}

        try:
            from app.services.ai_pipeline import ai_pipeline
            analysis = await ai_pipeline.standardize_document(text)
            return {
                "document_id": document_id,
                "title": doc.title,
                "summary": analysis.get("structured_summary", ""),
                "keywords": analysis.get("keywords", []),
                "categories": analysis.get("categories", []),
            }
        except Exception as e:
            return {"error": f"AI analysis failed: {str(e)}"}


@mcp.tool()
async def analyze_document(document_id: int) -> dict:
    """Full AI analysis: quality score, issues, suggested tags, and improvement recommendations."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Document).where(Document.id == document_id))
        doc = result.scalar_one_or_none()
        if not doc:
            return {"error": f"Document {document_id} not found"}

        text = doc.plain_text or ""
        if not text:
            return {"error": "Document has no text content"}

        try:
            from app.services.ai_pipeline import ai_pipeline
            analysis = await ai_pipeline.analyze_document(text, doc.title or "")
            return {
                "document_id": document_id,
                "title": doc.title,
                "quality_score": analysis.get("quality_score"),
                "issues": analysis.get("issues", []),
                "suggested_tags": analysis.get("suggested_tags", []),
                "suggestions": analysis.get("suggestions", []),
                "metadata": analysis.get("metadata", {}),
            }
        except Exception as e:
            return {"error": f"AI analysis failed: {str(e)}"}
