"""MCP tool: Create, update, delete, and manage documents."""

import json
from app.mcp.server import mcp
from app.core.database import AsyncSessionLocal
from app.models.document import Document, Tag, document_tags
from sqlalchemy import select


async def _get_or_create_user_id(session) -> int:
    """Get the first admin user ID as default for MCP-created documents."""
    from app.models.user import User
    result = await session.execute(select(User.id).where(User.is_admin == True).limit(1))
    row = result.first()
    return row[0] if row else 1


@mcp.tool()
async def create_document(
    title: str,
    content_markdown: str,
    folder_id: int | None = None,
    tags: list[str] | None = None,
    status: str = "draft",
) -> dict:
    """Create a new document in the knowledge base.

    Content should be in Markdown format. Documents are created as drafts by default
    for human review before publishing.
    """
    if not title or not content_markdown:
        return {"error": {"code": "INVALID_INPUT", "message": "title and content_markdown are required"}}
    if len(content_markdown) > 100_000:
        return {"error": {"code": "INVALID_INPUT", "message": "Content too large (max 100KB)"}}

    async with AsyncSessionLocal() as session:
        try:
            from app.services.content_converter import markdown_to_tiptap, extract_plain_text
            content_json = markdown_to_tiptap(content_markdown)
            plain_text = extract_plain_text(content_json)
        except Exception:
            content_json = {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": content_markdown}]}]}
            plain_text = content_markdown

        user_id = await _get_or_create_user_id(session)

        doc = Document(
            title=title,
            content_json=content_json,
            plain_text=plain_text,
            status=status,
            folder_id=folder_id,
            user_id=user_id,
            version=1,
        )
        session.add(doc)
        await session.flush()

        if tags:
            for tag_name in tags:
                tag_result = await session.execute(select(Tag).where(Tag.name == tag_name))
                tag = tag_result.scalar_one_or_none()
                if not tag:
                    tag = Tag(name=tag_name, user_id=user_id)
                    session.add(tag)
                    await session.flush()
                await session.execute(document_tags.insert().values(document_id=doc.id, tag_id=tag.id))

        await session.commit()
        await session.refresh(doc)

        return {
            "id": doc.id,
            "title": doc.title,
            "status": doc.status,
            "message": f"Document created (status: {status})",
        }


@mcp.tool()
async def update_document(
    document_id: int,
    title: str | None = None,
    content_markdown: str | None = None,
) -> dict:
    """Update an existing document's title or content. Creates a version snapshot before updating."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Document).where(Document.id == document_id))
        doc = result.scalar_one_or_none()
        if not doc:
            return {"error": {"code": "NOT_FOUND", "message": f"Document {document_id} not found"}}

        from app.models.document import DocumentVersion
        version = DocumentVersion(
            document_id=doc.id,
            version_number=doc.version,
            title=doc.title,
            content_json=doc.content_json,
        )
        session.add(version)

        if title is not None:
            doc.title = title

        if content_markdown is not None:
            if len(content_markdown) > 100_000:
                return {"error": {"code": "INVALID_INPUT", "message": "Content too large (max 100KB)"}}
            try:
                from app.services.content_converter import markdown_to_tiptap, extract_plain_text
                doc.content_json = markdown_to_tiptap(content_markdown)
                doc.plain_text = extract_plain_text(doc.content_json)
            except Exception:
                doc.content_json = {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": content_markdown}]}]}
                doc.plain_text = content_markdown

        doc.version += 1
        await session.commit()

        return {"id": doc.id, "title": doc.title, "version": doc.version, "message": "Document updated"}


@mcp.tool()
async def delete_document(document_id: int, permanent: bool = False) -> dict:
    """Delete or archive a document. By default archives (status='archived'). Set permanent=True to fully delete."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Document).where(Document.id == document_id))
        doc = result.scalar_one_or_none()
        if not doc:
            return {"error": {"code": "NOT_FOUND", "message": f"Document {document_id} not found"}}

        if permanent:
            await session.delete(doc)
            await session.commit()
            return {"id": document_id, "message": "Document permanently deleted"}
        else:
            doc.status = "archived"
            await session.commit()
            return {"id": document_id, "status": "archived", "message": "Document archived"}


@mcp.tool()
async def move_document(document_id: int, folder_id: int | None = None, status: str | None = None) -> dict:
    """Move a document to a different folder or change its status."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Document).where(Document.id == document_id))
        doc = result.scalar_one_or_none()
        if not doc:
            return {"error": {"code": "NOT_FOUND", "message": f"Document {document_id} not found"}}

        if folder_id is not None:
            doc.folder_id = folder_id
        if status is not None:
            if status not in ("draft", "published", "archived"):
                return {"error": {"code": "INVALID_INPUT", "message": f"Invalid status: {status}"}}
            doc.status = status

        await session.commit()
        return {"id": doc.id, "folder_id": doc.folder_id, "status": doc.status, "message": "Document moved"}


@mcp.tool()
async def manage_tags(document_id: int, add_tags: list[str] | None = None, remove_tags: list[str] | None = None) -> dict:
    """Add or remove tags from a document."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Document).where(Document.id == document_id))
        doc = result.scalar_one_or_none()
        if not doc:
            return {"error": {"code": "NOT_FOUND", "message": f"Document {document_id} not found"}}

        user_id = doc.user_id or await _get_or_create_user_id(session)

        if add_tags:
            for tag_name in add_tags:
                tag_result = await session.execute(select(Tag).where(Tag.name == tag_name))
                tag = tag_result.scalar_one_or_none()
                if not tag:
                    tag = Tag(name=tag_name, user_id=user_id)
                    session.add(tag)
                    await session.flush()
                # Check if already tagged
                existing = await session.execute(
                    select(document_tags).where(
                        document_tags.c.document_id == document_id,
                        document_tags.c.tag_id == tag.id,
                    )
                )
                if not existing.first():
                    await session.execute(document_tags.insert().values(document_id=document_id, tag_id=tag.id))

        if remove_tags:
            for tag_name in remove_tags:
                tag_result = await session.execute(select(Tag).where(Tag.name == tag_name))
                tag = tag_result.scalar_one_or_none()
                if tag:
                    await session.execute(
                        document_tags.delete().where(
                            document_tags.c.document_id == document_id,
                            document_tags.c.tag_id == tag.id,
                        )
                    )

        await session.commit()

        # Return current tags
        tag_result = await session.execute(
            select(Tag.name).join(document_tags, Tag.id == document_tags.c.tag_id)
            .where(document_tags.c.document_id == document_id)
        )
        current_tags = [row[0] for row in tag_result.fetchall()]

        return {"id": document_id, "tags": current_tags, "message": "Tags updated"}
