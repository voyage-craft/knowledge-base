import json
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db, AsyncSessionLocal
from app.models.import_batch import ImportBatch, ImportFile
from app.models.document import Document, Folder, Tag, document_tags
from app.models.user import User
from app.schemas.import_batch import (
    ImportBatchResponse, ImportFileResponse,
    ImportFileUpdateRequest, ImportApproveRequest,
)
from app.api.auth import get_current_user_dep
from app.services.ai_pipeline import ai_pipeline
from app.services.file_parser import file_parser
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/import", tags=["import"])

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB per file
MAX_BATCH_FILES = 50


@router.post("/batch", response_model=ImportBatchResponse, status_code=201)
async def create_batch(
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """Upload multiple files and create an import batch."""
    if len(files) > MAX_BATCH_FILES:
        raise HTTPException(status_code=400, detail=f"一次最多上传 {MAX_BATCH_FILES} 个文件")

    allowed_exts = {".md", ".txt", ".tex", ".latex", ".docx", ".pdf"}
    import_files = []

    for upload in files:
        filename = upload.filename or "unknown"
        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in allowed_exts:
            raise HTTPException(status_code=400, detail=f"不支持的文件格式: {ext} ({filename})")

        content = await upload.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"文件过大: {filename} (最大 10MB)")

        try:
            parsed = await file_parser.parse(content, filename)
        except ValueError as e:
            parsed = ""
            logger.warning("Failed to parse %s: %s", filename, e)

        file_type = file_parser.detect_type(filename)

        # Handle both string (plain text) and dict (TipTap JSON) results
        if isinstance(parsed, dict):
            raw_text = json.dumps(parsed, ensure_ascii=False)
        else:
            raw_text = parsed if parsed else ""

        imp_file = ImportFile(
            user_id=current_user.id,
            filename=filename,
            file_type=file_type,
            raw_text=raw_text if raw_text else None,
            status="pending" if raw_text else "error",
            error_message=None if raw_text else f"文件解析失败: {file_type}",
        )
        import_files.append(imp_file)

    # Create batch
    batch = ImportBatch(
        user_id=current_user.id,
        status="pending",
        total_files=len(import_files),
    )
    db.add(batch)
    await db.flush()

    for f in import_files:
        f.batch_id = batch.id
        db.add(f)

    await db.commit()

    # Refresh to get IDs
    await db.refresh(batch)
    result = await db.execute(
        select(ImportFile).where(ImportFile.batch_id == batch.id)
    )
    batch_files = result.scalars().all()

    return ImportBatchResponse(
        id=batch.id,
        status=batch.status,
        total_files=batch.total_files,
        processed_count=batch.processed_count,
        created_at=batch.created_at,
        files=[ImportFileResponse.model_validate(f) for f in batch_files],
    )


@router.get("/batch/{batch_id}", response_model=ImportBatchResponse)
async def get_batch(
    batch_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """Get batch status and file list."""
    result = await db.execute(
        select(ImportBatch).where(
            ImportBatch.id == batch_id,
            ImportBatch.user_id == current_user.id,
        )
    )
    batch = result.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail="批次不存在")

    files_result = await db.execute(
        select(ImportFile).where(ImportFile.batch_id == batch.id)
    )
    files = files_result.scalars().all()

    return ImportBatchResponse(
        id=batch.id,
        status=batch.status,
        total_files=batch.total_files,
        processed_count=batch.processed_count,
        created_at=batch.created_at,
        files=[ImportFileResponse.model_validate(f) for f in files],
    )


@router.post("/batch/{batch_id}/analyze", response_model=ImportBatchResponse)
async def analyze_batch(
    batch_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """Run AI analysis on all pending files in the batch."""
    result = await db.execute(
        select(ImportBatch).where(
            ImportBatch.id == batch_id,
            ImportBatch.user_id == current_user.id,
        )
    )
    batch = result.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail="批次不存在")

    # Get pending files
    files_result = await db.execute(
        select(ImportFile).where(
            ImportFile.batch_id == batch.id,
            ImportFile.status == "pending",
        )
    )
    pending_files = files_result.scalars().all()

    if not pending_files:
        raise HTTPException(status_code=400, detail="没有待分析的文件")

    # Update batch status
    batch.status = "processing"
    await db.commit()

    # Get file IDs (detached from session before concurrent work)
    file_ids = [f.id for f in pending_files]
    raw_texts = {f.id: f.raw_text for f in pending_files}
    filenames = {f.id: f.filename for f in pending_files}

    import asyncio

    async def analyze_one(file_id: int):
        """Analyze a single file using its own DB session."""
        raw_text = raw_texts.get(file_id)
        filename = filenames.get(file_id, "unknown")

        if not raw_text:
            async with AsyncSessionLocal() as sess:
                result = await sess.execute(select(ImportFile).where(ImportFile.id == file_id))
                f = result.scalar_one_or_none()
                if f:
                    f.status = "error"
                    f.error_message = "文件内容为空，无法分析"
                    await sess.commit()
            return

        # Mark as analyzing
        async with AsyncSessionLocal() as sess:
            result = await sess.execute(select(ImportFile).where(ImportFile.id == file_id))
            f = result.scalar_one_or_none()
            if f:
                f.status = "analyzing"
                await sess.commit()

        # Run AI analysis (no DB needed)
        try:
            analysis = await ai_pipeline.analyze_document(raw_text, filename)
        except Exception as e:
            logger.error("AI analysis failed for %s: %s", filename, e)
            analysis = None

        # Save result
        async with AsyncSessionLocal() as sess:
            result = await sess.execute(select(ImportFile).where(ImportFile.id == file_id))
            f = result.scalar_one_or_none()
            if f:
                if analysis:
                    f.ai_analysis = analysis
                    f.status = "ready"
                else:
                    f.status = "error"
                    f.error_message = "AI 分析失败，请稍后重试"
                await sess.commit()

    # Process files concurrently (max 3 parallel LLM calls)
    semaphore = asyncio.Semaphore(3)

    async def limited_analyze(file_id: int):
        async with semaphore:
            return await analyze_one(file_id)

    await asyncio.gather(*[limited_analyze(fid) for fid in file_ids])

    # Update batch status and get final results (all in one session for consistency)
    async with AsyncSessionLocal() as sess:
        result = await sess.execute(select(ImportBatch).where(ImportBatch.id == batch_id))
        batch = result.scalar_one_or_none()
        if batch:
            # Count ready and error files
            files_result = await sess.execute(
                select(ImportFile).where(ImportFile.batch_id == batch.id)
            )
            all_files = files_result.scalars().all()
            ready_count = sum(1 for f in all_files if f.status == "ready")
            batch.processed_count = ready_count
            batch.status = "review"
            await sess.commit()

            return ImportBatchResponse(
                id=batch.id,
                status=batch.status,
                total_files=batch.total_files,
                processed_count=batch.processed_count,
                created_at=batch.created_at,
                files=[ImportFileResponse.model_validate(f) for f in all_files],
            )

    # Fallback (should not reach here)
    raise HTTPException(status_code=500, detail="分析完成后无法获取结果")


@router.put("/file/{file_id}", response_model=ImportFileResponse)
async def update_file_analysis(
    file_id: int,
    data: ImportFileUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """User edits AI suggestions (title, tags, folder, etc)."""
    result = await db.execute(
        select(ImportFile).where(
            ImportFile.id == file_id,
            ImportFile.user_id == current_user.id,
        )
    )
    imp_file = result.scalar_one_or_none()
    if not imp_file:
        raise HTTPException(status_code=404, detail="文件不存在")

    if data.ai_analysis is not None:
        imp_file.ai_analysis = data.ai_analysis

    await db.commit()
    await db.refresh(imp_file)
    return ImportFileResponse.model_validate(imp_file)


@router.post("/batch/{batch_id}/approve", response_model=ImportBatchResponse)
async def approve_files(
    batch_id: int,
    data: ImportApproveRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """Approve selected files for import — creates Document records."""
    result = await db.execute(
        select(ImportBatch).where(
            ImportBatch.id == batch_id,
            ImportBatch.user_id == current_user.id,
        )
    )
    batch = result.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail="批次不存在")

    approved_ids = set(data.file_ids)
    files_result = await db.execute(
        select(ImportFile).where(ImportFile.batch_id == batch.id)
    )
    all_files = files_result.scalars().all()

    from app.services.content_converter import markdown_to_tiptap, extract_plain_text

    for imp_file in all_files:
        if imp_file.id not in approved_ids:
            continue
        if imp_file.status not in ("ready",):
            continue

        # Determine title from AI analysis or filename
        title = imp_file.filename.rsplit(".", 1)[0]
        analysis = imp_file.ai_analysis or {}
        if analysis.get("title"):
            title = analysis["title"]

        # Convert raw text to TipTap JSON
        raw = imp_file.raw_text or ""

        # Check if raw_text is already TipTap JSON (from DOCX/PDF structural parser)
        content_json = None
        if raw.startswith("{"):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict) and parsed.get("type") == "doc":
                    content_json = parsed
            except (json.JSONDecodeError, TypeError):
                pass

        if not content_json:
            if imp_file.file_type == "md":
                content_json = markdown_to_tiptap(raw)
            else:
                # For other formats, wrap plain text as paragraphs
                paragraphs = raw.split("\n\n")
                content_nodes = []
                for p in paragraphs:
                    p = p.strip()
                    if p:
                        content_nodes.append({
                            "type": "paragraph",
                            "content": [{"type": "text", "text": p}],
                        })
                content_json = {"type": "doc", "content": content_nodes} if content_nodes else {"type": "doc", "content": []}

        plain_text = extract_plain_text(content_json)

        # Create the document
        doc = Document(
            title=title,
            content_json=content_json,
            plain_text=plain_text,
            user_id=current_user.id,
        )

        # Apply suggested folder if exists
        suggested_folder = analysis.get("suggested_folder")
        if suggested_folder:
            folder_result = await db.execute(
                select(Folder).where(
                    Folder.user_id == current_user.id,
                    Folder.name == suggested_folder,
                )
            )
            folder = folder_result.scalar_one_or_none()
            if not folder:
                folder = Folder(name=suggested_folder, user_id=current_user.id)
                db.add(folder)
                await db.flush()
            doc.folder_id = folder.id

        db.add(doc)
        await db.flush()

        # Apply suggested tags
        suggested_tags = analysis.get("suggested_tags", [])
        # Batch fetch existing tags to avoid N+1
        if suggested_tags:
            tag_result = await db.execute(
                select(Tag).where(
                    Tag.user_id == current_user.id,
                    Tag.name.in_(suggested_tags),
                )
            )
            existing_tags = {t.name: t for t in tag_result.scalars().all()}
        else:
            existing_tags = {}
        for tag_name in suggested_tags:
            tag = existing_tags.get(tag_name)
            if not tag:
                tag = Tag(name=tag_name, user_id=current_user.id)
                db.add(tag)
                await db.flush()
            # Link tag to document
            from sqlalchemy.dialects.sqlite import insert as sqlite_insert
            stmt = sqlite_insert(document_tags).values(
                document_id=doc.id, tag_id=tag.id
            ).on_conflict_do_nothing()
            await db.execute(stmt)

        imp_file.status = "imported"
        imp_file.imported_document_id = doc.id

    # Check if all files are processed
    imported_count = sum(1 for f in all_files if f.status in ("imported", "rejected"))
    if imported_count >= batch.total_files:
        batch.status = "completed"

    await db.commit()

    # Fire on_import workflow triggers
    from app.services.workflow_trigger import fire_triggers
    await fire_triggers("on_import", current_user.id, background_tasks)

    # Refresh
    await db.refresh(batch)
    files_result = await db.execute(
        select(ImportFile).where(ImportFile.batch_id == batch.id)
    )
    all_files = files_result.scalars().all()

    return ImportBatchResponse(
        id=batch.id,
        status=batch.status,
        total_files=batch.total_files,
        processed_count=batch.processed_count,
        created_at=batch.created_at,
        files=[ImportFileResponse.model_validate(f) for f in all_files],
    )


@router.post("/file/{file_id}/reject", response_model=ImportFileResponse)
async def reject_file(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """Reject a file from import."""
    result = await db.execute(
        select(ImportFile).where(
            ImportFile.id == file_id,
            ImportFile.user_id == current_user.id,
        )
    )
    imp_file = result.scalar_one_or_none()
    if not imp_file:
        raise HTTPException(status_code=404, detail="文件不存在")

    imp_file.status = "rejected"
    await db.commit()
    await db.refresh(imp_file)
    return ImportFileResponse.model_validate(imp_file)
