from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from fastapi.responses import Response
from app.core.database import get_db
from app.models.document import Document, DocumentVersion, Folder, Tag, document_tags
from app.schemas.document import (
    DocumentCreate, DocumentUpdate, DocumentResponse, DocumentListResponse,
    BatchDeleteRequest, BatchMoveRequest, StatusUpdateRequest,
    VersionResponse, VersionDetailResponse,
)
from app.api.auth import get_current_user_dep
from app.models.user import User
from app.services.content_converter import (
    sanitize_filename, normalize_content_json, tiptap_to_html, html_to_markdown,
    tiptap_to_latex, tiptap_to_docx, extract_plain_text, markdown_to_tiptap,
)
from datetime import datetime, timezone
import json

router = APIRouter(prefix="/api/documents", tags=["documents"])

@router.get("", response_model=DocumentListResponse)
async def list_documents(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: str = Query("", max_length=200),
    folder_id: int | None = None,
    status_filter: str = Query("", alias="status"),
    tag_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    # Use optimized query with eager loading for tags
    from sqlalchemy.orm import selectinload

    query = (
        select(Document)
        .options(selectinload(Document.tags))
        .where(
            Document.user_id == current_user.id,
            Document.status != "deleted",
        )
    )

    if search:
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(
            or_(
                Document.title.ilike(f"%{escaped}%", escape="\\"),
                Document.plain_text.ilike(f"%{escaped}%", escape="\\"),
            )
        )

    if folder_id is not None:
        query = query.where(Document.folder_id == folder_id)

    if status_filter:
        query = query.where(Document.status == status_filter)

    if tag_id is not None:
        query = query.where(
            Document.id.in_(
                select(document_tags.c.document_id).where(
                    document_tags.c.tag_id == tag_id
                )
            )
        )

    # Count total - use simpler query without subquery for better performance
    count_query = select(func.count(Document.id)).where(
        Document.user_id == current_user.id,
        Document.status != "deleted",
    )
    if folder_id is not None:
        count_query = count_query.where(Document.folder_id == folder_id)
    if status_filter:
        count_query = count_query.where(Document.status == status_filter)
    if tag_id is not None:
        count_query = count_query.where(
            Document.id.in_(
                select(document_tags.c.document_id).where(document_tags.c.tag_id == tag_id)
            )
        )

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Get page with optimized ordering
    query = query.order_by(Document.updated_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    documents = result.scalars().unique().all()

    return DocumentListResponse(
        documents=[DocumentResponse.model_validate(d) for d in documents],
        total=total,
        offset=offset,
        limit=limit,
    )

@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_document(
    data: DocumentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    doc = Document(
        title=data.title,
        content_json=data.content_json,
        folder_id=data.folder_id,
        user_id=current_user.id,
        plain_text=extract_plain_text(data.content_json),
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return DocumentResponse.model_validate(doc)

@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    result = await db.execute(
        select(Document).where(
            Document.id == doc_id,
            Document.user_id == current_user.id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    return DocumentResponse.model_validate(doc)

@router.put("/{doc_id}", response_model=DocumentResponse)
async def update_document(
    doc_id: int,
    data: DocumentUpdate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    result = await db.execute(
        select(Document).where(
            Document.id == doc_id,
            Document.user_id == current_user.id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    update_data = data.model_dump(exclude_unset=True)

    # Whitelist allowed fields to prevent unsafe setattr on sensitive columns
    ALLOWED_UPDATE_FIELDS = {"title", "content_json", "latex_source", "folder_id", "status"}
    update_data = {k: v for k, v in update_data.items() if k in ALLOWED_UPDATE_FIELDS}

    # Save version snapshot before applying updates (only when content actually changed)
    if "content_json" in update_data and doc.content_json is not None:
        if update_data["content_json"] != doc.content_json:
            snapshot = DocumentVersion(
                document_id=doc.id,
                title=doc.title,
                content_json=doc.content_json,
                latex_source=doc.latex_source,
                version_number=doc.version,
            )
            db.add(snapshot)

    for key, value in update_data.items():
        setattr(doc, key, value)

    # Re-extract plain text if content changed
    if "content_json" in update_data:
        doc.plain_text = extract_plain_text(doc.content_json)

    doc.version += 1
    doc.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(doc)

    # Fire on_save triggers only when content actually changed (not title-only edits)
    if "content_json" in update_data:
        from app.services.workflow_trigger import fire_triggers
        await fire_triggers("on_save", current_user.id, background_tasks)

    return DocumentResponse.model_validate(doc)

@router.delete("/{doc_id}")
async def delete_document(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    result = await db.execute(
        select(Document).where(
            Document.id == doc_id,
            Document.user_id == current_user.id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    doc.status = "deleted"
    await db.commit()
    return {"message": "Document deleted"}


@router.post("/batch-delete")
async def batch_delete(
    data: BatchDeleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    if not data.ids:
        return {"message": "没有选择文档", "deleted": 0}

    result = await db.execute(
        select(Document).where(
            Document.id.in_(data.ids),
            Document.user_id == current_user.id,
        )
    )
    docs = result.scalars().all()
    count = 0
    for doc in docs:
        doc.status = "deleted"
        count += 1

    await db.commit()
    return {"message": f"已删除 {count} 个文档", "deleted": count}


@router.post("/batch-move")
async def batch_move(
    data: BatchMoveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    if not data.ids:
        return {"message": "没有选择文档", "moved": 0}

    # Validate target folder
    if data.folder_id is not None:
        folder_result = await db.execute(
            select(Folder).where(
                Folder.id == data.folder_id,
                Folder.user_id == current_user.id,
            )
        )
        if not folder_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="目标文件夹不存在")

    result = await db.execute(
        select(Document).where(
            Document.id.in_(data.ids),
            Document.user_id == current_user.id,
        )
    )
    docs = result.scalars().all()
    count = 0
    for doc in docs:
        doc.folder_id = data.folder_id
        count += 1

    await db.commit()
    return {"message": f"已移动 {count} 个文档", "moved": count}


@router.put("/{doc_id}/status")
async def update_status(
    doc_id: int,
    data: StatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    if data.status not in ("draft", "published", "archived"):
        raise HTTPException(status_code=400, detail="无效的状态值")

    result = await db.execute(
        select(Document).where(
            Document.id == doc_id,
            Document.user_id == current_user.id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    doc.status = data.status
    await db.commit()
    return {"message": "状态已更新"}


# ── Version History ─────────────────────────────────────────────

@router.get("/{doc_id}/versions")
async def list_versions(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """List all saved versions for a document."""
    doc = (await db.execute(
        select(Document).where(Document.id == doc_id, Document.user_id == current_user.id)
    )).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    result = await db.execute(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == doc_id)
        .order_by(DocumentVersion.version_number.desc())
    )
    versions = result.scalars().all()
    return [
        VersionResponse(
            id=v.id,
            document_id=v.document_id,
            version_number=v.version_number,
            title=v.title or doc.title,
            created_at=v.created_at,
        )
        for v in versions
    ]


@router.get("/{doc_id}/versions/{version_id}")
async def get_version(
    doc_id: int,
    version_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """Get the full content of a specific version."""
    doc = (await db.execute(
        select(Document).where(Document.id == doc_id, Document.user_id == current_user.id)
    )).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    version = (await db.execute(
        select(DocumentVersion).where(
            DocumentVersion.id == version_id,
            DocumentVersion.document_id == doc_id,
        )
    )).scalar_one_or_none()
    if not version:
        raise HTTPException(status_code=404, detail="版本不存在")

    return VersionDetailResponse(
        id=version.id,
        document_id=version.document_id,
        version_number=version.version_number,
        title=version.title or doc.title,
        content_json=version.content_json,
        created_at=version.created_at,
    )


@router.post("/{doc_id}/versions/{version_id}/restore", response_model=DocumentResponse)
async def restore_version(
    doc_id: int,
    version_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """Restore a document to a previous version."""
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.user_id == current_user.id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    version = (await db.execute(
        select(DocumentVersion).where(
            DocumentVersion.id == version_id,
            DocumentVersion.document_id == doc_id,
        )
    )).scalar_one_or_none()
    if not version:
        raise HTTPException(status_code=404, detail="版本不存在")

    # Save current state as a new version before restoring
    if doc.content_json is not None:
        snapshot = DocumentVersion(
            document_id=doc.id,
            title=doc.title,
            content_json=doc.content_json,
            latex_source=doc.latex_source,
            version_number=doc.version,
        )
        db.add(snapshot)

    # Restore from the selected version
    doc.content_json = version.content_json
    doc.latex_source = version.latex_source
    doc.plain_text = extract_plain_text(version.content_json)
    doc.version += 1
    doc.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(doc)
    return DocumentResponse.model_validate(doc)

@router.get("/{doc_id}/export")
async def export_document(
    doc_id: int,
    format: str = Query("markdown", pattern="^(markdown|html|latex|docx)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    result = await db.execute(
        select(Document).where(
            Document.id == doc_id,
            Document.user_id == current_user.id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    safe_name = sanitize_filename(doc.title)
    normalized_json = normalize_content_json(doc.content_json)

    if format == "docx":
        import io
        docx_doc = tiptap_to_docx(normalized_json, doc.title)
        buffer = io.BytesIO()
        docx_doc.save(buffer)
        buffer.seek(0)
        return Response(
            content=buffer.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{safe_name}.docx"'},
        )

    if format == "latex":
        latex_content = tiptap_to_latex(normalized_json, doc.title)
        return Response(
            content=latex_content,
            media_type="application/x-tex; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{safe_name}.tex"'},
        )

    html_content = tiptap_to_html(normalized_json)

    if format == "html":
        from app.services.content_converter import _html_escape
        safe_title = _html_escape(doc.title)
        full_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{safe_title}</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; max-width: 800px; margin: 2rem auto; padding: 0 1rem; line-height: 1.7; color: #1a1a1a; }}
h1, h2, h3, h4, h5, h6 {{ margin-top: 1.5em; margin-bottom: 0.5em; }}
pre {{ background: #f5f5f5; padding: 1rem; border-radius: 6px; overflow-x: auto; }}
code {{ background: #f0f0f0; padding: 0.1em 0.3em; border-radius: 3px; font-size: 0.9em; }}
blockquote {{ border-left: 3px solid #ddd; margin-left: 0; padding-left: 1rem; color: #666; }}
img {{ max-width: 100%; }}
</style>
</head>
<body>
<h1>{safe_title}</h1>
{html_content}
</body>
</html>"""
        return Response(
            content=full_html,
            media_type="text/html; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{safe_name}.html"'},
        )
    else:
        md_content = f"# {doc.title}\n\n" + html_to_markdown(html_content)
        return Response(
            content=md_content,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{safe_name}.md"'},
        )


@router.post("/import", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def import_markdown(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """Import a Markdown file as a new document."""
    if not file.filename or not file.filename.lower().endswith(".md"):
        raise HTTPException(status_code=400, detail="只支持 .md 文件")

    # Check file size before reading to prevent memory exhaustion
    if file.size and file.size > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件大小不能超过 5MB")

    # Read file content (max 5MB)
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件大小不能超过 5MB")

    try:
        md_text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="文件编码必须是 UTF-8")

    # Extract title from first heading or filename
    import re
    title_match = re.match(r"^#\s+(.+)$", md_text.strip(), re.MULTILINE)
    title = title_match.group(1).strip() if title_match else file.filename.rsplit(".", 1)[0]

    # Convert to TipTap JSON
    content_json = markdown_to_tiptap(md_text)
    plain_text = extract_plain_text(content_json)

    doc = Document(
        title=title,
        content_json=content_json,
        plain_text=plain_text,
        user_id=current_user.id,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return DocumentResponse.model_validate(doc)
