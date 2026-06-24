"""
批量操作工具API

提供批量导出、批量标签管理、批量状态更新等功能
"""
import io
import json
import logging
import zipfile
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.api.auth import get_current_user_dep
from app.models.user import User
from app.models.document import Document, Tag, document_tags
from app.services.content_converter import (
    normalize_content_json, tiptap_to_html, html_to_markdown,
    tiptap_to_latex, tiptap_to_docx, sanitize_filename
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/batch", tags=["batch-tools"])


# ── Pydantic schemas ──────────────────────────────────────────

class BatchExportRequest(BaseModel):
    """批量导出请求"""
    document_ids: list[int]
    format: str = "markdown"  # markdown, html, latex, docx
    include_metadata: bool = True


class BatchTagRequest(BaseModel):
    """批量标签操作请求"""
    document_ids: list[int]
    tag_ids: list[int]
    action: str = "add"  # add, remove, replace


class BatchStatusRequest(BaseModel):
    """批量状态更新请求"""
    document_ids: list[int]
    status: str  # draft, published, archived


class BatchFolderRequest(BaseModel):
    """批量移动到文件夹"""
    document_ids: list[int]
    folder_id: Optional[int] = None


# ── 批量导出 ──────────────────────────────────────────────────

@router.post("/export")
async def batch_export(
    request: BatchExportRequest,
    current_user: User = Depends(get_current_user_dep),
    db: AsyncSession = Depends(get_db),
):
    """批量导出文档为ZIP压缩包"""
    if not request.document_ids:
        raise HTTPException(status_code=400, detail="未选择文档")

    if request.format not in ("markdown", "html", "latex", "docx"):
        raise HTTPException(status_code=400, detail="不支持的导出格式")

    # 获取文档
    result = await db.execute(
        select(Document).where(
            Document.id.in_(request.document_ids),
            Document.user_id == current_user.id,
            Document.status != "deleted",
        )
    )
    documents = result.scalars().all()

    if not documents:
        raise HTTPException(status_code=404, detail="未找到文档")

    # 创建ZIP文件
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for doc in documents:
            try:
                safe_name = sanitize_filename(doc.title)
                normalized_json = normalize_content_json(doc.content_json)

                if request.format == "docx":
                    docx_doc = tiptap_to_docx(normalized_json, doc.title)
                    file_buffer = io.BytesIO()
                    docx_doc.save(file_buffer)
                    file_buffer.seek(0)
                    zip_file.writestr(f"{safe_name}.docx", file_buffer.read())

                elif request.format == "latex":
                    latex_content = tiptap_to_latex(normalized_json, doc.title)
                    zip_file.writestr(f"{safe_name}.tex", latex_content)

                elif request.format == "html":
                    html_content = tiptap_to_html(normalized_json)
                    full_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>{doc.title}</title>
</head>
<body>
<h1>{doc.title}</h1>
{html_content}
</body>
</html>"""
                    zip_file.writestr(f"{safe_name}.html", full_html)

                else:  # markdown
                    html_content = tiptap_to_html(normalized_json)
                    md_content = f"# {doc.title}\n\n" + html_to_markdown(html_content)
                    zip_file.writestr(f"{safe_name}.md", md_content)

                # 添加元数据
                if request.include_metadata:
                    metadata = {
                        "id": doc.id,
                        "title": doc.title,
                        "status": doc.status,
                        "version": doc.version,
                        "created_at": doc.created_at.isoformat() if doc.created_at else None,
                        "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
                    }
                    zip_file.writestr(f"{safe_name}_metadata.json", json.dumps(metadata, ensure_ascii=False, indent=2))

            except Exception as e:
                logger.warning("导出文档 %s 失败: %s", doc.id, e)
                continue

    zip_buffer.seek(0)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"knowledge_base_export_{timestamp}.zip"

    logger.info("批量导出完成: %d 个文档, 格式: %s", len(documents), request.format)

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


# ── 批量标签管理 ──────────────────────────────────────────────────

@router.post("/tags")
async def batch_tag_operation(
    request: BatchTagRequest,
    current_user: User = Depends(get_current_user_dep),
    db: AsyncSession = Depends(get_db),
):
    """批量标签操作"""
    if not request.document_ids:
        raise HTTPException(status_code=400, detail="未选择文档")
    if not request.tag_ids:
        raise HTTPException(status_code=400, detail="未选择标签")

    # 验证文档所有权
    docs_result = await db.execute(
        select(Document.id).where(
            Document.id.in_(request.document_ids),
            Document.user_id == current_user.id,
        )
    )
    valid_doc_ids = [row[0] for row in docs_result.fetchall()]

    # 验证标签所有权
    tags_result = await db.execute(
        select(Tag.id).where(
            Tag.id.in_(request.tag_ids),
            Tag.user_id == current_user.id,
        )
    )
    valid_tag_ids = [row[0] for row in tags_result.fetchall()]

    if not valid_doc_ids or not valid_tag_ids:
        raise HTTPException(status_code=400, detail="无效的文档或标签")

    affected_count = 0

    if request.action == "add":
        # 添加标签（忽略已存在的）
        for doc_id in valid_doc_ids:
            for tag_id in valid_tag_ids:
                try:
                    await db.execute(
                        document_tags.insert().values(document_id=doc_id, tag_id=tag_id)
                        .prefix_with("OR IGNORE")
                    )
                    affected_count += 1
                except Exception:
                    pass

    elif request.action == "remove":
        # 移除标签
        for doc_id in valid_doc_ids:
            for tag_id in valid_tag_ids:
                await db.execute(
                    document_tags.delete().where(
                        document_tags.c.document_id == doc_id,
                        document_tags.c.tag_id == tag_id,
                    )
                )
                affected_count += 1

    elif request.action == "replace":
        # 替换标签（先删除所有，再添加新的）
        for doc_id in valid_doc_ids:
            await db.execute(
                document_tags.delete().where(document_tags.c.document_id == doc_id)
            )
            for tag_id in valid_tag_ids:
                try:
                    await db.execute(
                        document_tags.insert().values(document_id=doc_id, tag_id=tag_id)
                        .prefix_with("OR IGNORE")
                    )
                except Exception:
                    pass
            affected_count += len(valid_tag_ids)

    await db.commit()

    logger.info("批量标签操作完成: action=%s, documents=%d, tags=%d",
                request.action, len(valid_doc_ids), len(valid_tag_ids))

    return {
        "message": f"已{request.action}标签",
        "affected_documents": len(valid_doc_ids),
        "affected_tags": len(valid_tag_ids),
    }


# ── 批量状态更新 ──────────────────────────────────────────────────

@router.post("/status")
async def batch_update_status(
    request: BatchStatusRequest,
    current_user: User = Depends(get_current_user_dep),
    db: AsyncSession = Depends(get_db),
):
    """批量更新文档状态"""
    if not request.document_ids:
        raise HTTPException(status_code=400, detail="未选择文档")

    if request.status not in ("draft", "published", "archived"):
        raise HTTPException(status_code=400, detail="无效的状态值")

    result = await db.execute(
        update(Document)
        .where(
            Document.id.in_(request.document_ids),
            Document.user_id == current_user.id,
        )
        .values(status=request.status, updated_at=datetime.now(timezone.utc))
    )
    await db.commit()

    logger.info("批量状态更新: %d 个文档 -> %s", result.rowcount, request.status)

    return {
        "message": f"已更新 {result.rowcount} 个文档状态",
        "updated_count": result.rowcount,
    }


# ── 批量移动文件夹 ──────────────────────────────────────────────────

@router.post("/move")
async def batch_move_to_folder(
    request: BatchFolderRequest,
    current_user: User = Depends(get_current_user_dep),
    db: AsyncSession = Depends(get_db),
):
    """批量移动文档到文件夹"""
    if not request.document_ids:
        raise HTTPException(status_code=400, detail="未选择文档")

    # 验证文件夹所有权（如果不是移动到根目录）
    if request.folder_id is not None:
        from app.models.document import Folder
        folder_result = await db.execute(
            select(Folder).where(
                Folder.id == request.folder_id,
                Folder.user_id == current_user.id,
            )
        )
        if not folder_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="目标文件夹不存在")

    result = await db.execute(
        update(Document)
        .where(
            Document.id.in_(request.document_ids),
            Document.user_id == current_user.id,
        )
        .values(folder_id=request.folder_id, updated_at=datetime.now(timezone.utc))
    )
    await db.commit()

    logger.info("批量移动: %d 个文档 -> 文件夹 %s", result.rowcount, request.folder_id)

    return {
        "message": f"已移动 {result.rowcount} 个文档",
        "moved_count": result.rowcount,
    }


# ── 批量删除 ──────────────────────────────────────────────────

@router.post("/delete")
async def batch_soft_delete(
    document_ids: list[int],
    current_user: User = Depends(get_current_user_dep),
    db: AsyncSession = Depends(get_db),
):
    """批量软删除文档"""
    if not document_ids:
        raise HTTPException(status_code=400, detail="未选择文档")

    result = await db.execute(
        update(Document)
        .where(
            Document.id.in_(document_ids),
            Document.user_id == current_user.id,
        )
        .values(status="deleted", updated_at=datetime.now(timezone.utc))
    )
    await db.commit()

    logger.info("批量删除: %d 个文档", result.rowcount)

    return {
        "message": f"已删除 {result.rowcount} 个文档",
        "deleted_count": result.rowcount,
    }
