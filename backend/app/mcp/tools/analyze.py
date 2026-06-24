"""MCP tool: AI analysis of documents."""

import logging
from app.mcp.server import mcp
from app.mcp.auth_context import require_user_id
from app.core.database import AsyncSessionLocal
from app.models.document import Document
from sqlalchemy import select

logger = logging.getLogger(__name__)


@mcp.tool()
async def summarize_document(document_id: int) -> dict:
    """Generate an AI summary of a document. Returns structured summary, keywords, and metadata."""
    user_id = require_user_id()
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Document).where(Document.id == document_id, Document.user_id == user_id)
        )
        doc = result.scalar_one_or_none()
        if not doc:
            return {"error": {"code": "NOT_FOUND", "message": f"Document {document_id} not found"}}

        text = doc.plain_text or ""
        if not text:
            return {"error": {"code": "INVALID_INPUT", "message": "Document has no text content"}}

        if len(text) < 50:
            return {"error": {"code": "INVALID_INPUT", "message": "Document too short to summarize"}}

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
            logger.error("Summarize failed for doc %d: %s", document_id, e)
            return {"error": {"code": "AI_ERROR", "message": "AI analysis failed, please retry"}}


@mcp.tool()
async def analyze_document(document_id: int) -> dict:
    """Full AI analysis: quality score, issues, suggested tags, and improvement recommendations."""
    user_id = require_user_id()
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Document).where(Document.id == document_id, Document.user_id == user_id)
        )
        doc = result.scalar_one_or_none()
        if not doc:
            return {"error": {"code": "NOT_FOUND", "message": f"Document {document_id} not found"}}

        text = doc.plain_text or ""
        if not text:
            return {"error": {"code": "INVALID_INPUT", "message": "Document has no text content"}}

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
            logger.error("Analyze failed for doc %d: %s", document_id, e)
            return {"error": {"code": "AI_ERROR", "message": "AI analysis failed, please retry"}}
