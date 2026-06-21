from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, constr
from typing import Optional
from app.core.database import get_db
from app.models.document import Folder, Document
from app.api.auth import get_current_user_dep
from app.models.user import User

router = APIRouter(prefix="/api/folders", tags=["folders"])


class FolderCreate(BaseModel):
    name: constr(min_length=1, max_length=200)
    parent_id: Optional[int] = None


class FolderUpdate(BaseModel):
    name: constr(min_length=1, max_length=200)


class FolderResponse(BaseModel):
    id: int
    name: str
    parent_id: Optional[int]
    position: int

    class Config:
        from_attributes = True


class MoveDocumentRequest(BaseModel):
    folder_id: Optional[int] = None


@router.get("", response_model=list[FolderResponse])
async def list_folders(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """Get all folders for the current user as a flat list."""
    result = await db.execute(
        select(Folder)
        .where(Folder.user_id == current_user.id)
        .order_by(Folder.position.asc(), Folder.id.asc())
    )
    folders = result.scalars().all()
    return [FolderResponse.model_validate(f) for f in folders]


@router.post("", response_model=FolderResponse, status_code=status.HTTP_201_CREATED)
async def create_folder(
    data: FolderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    # Validate parent folder belongs to user
    if data.parent_id is not None:
        parent_result = await db.execute(
            select(Folder).where(
                Folder.id == data.parent_id,
                Folder.user_id == current_user.id,
            )
        )
        if not parent_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="父文件夹不存在")

    folder = Folder(
        name=data.name,
        parent_id=data.parent_id,
        user_id=current_user.id,
    )
    db.add(folder)
    await db.commit()
    await db.refresh(folder)
    return FolderResponse.model_validate(folder)


@router.put("/{folder_id}", response_model=FolderResponse)
async def rename_folder(
    folder_id: int,
    data: FolderUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    result = await db.execute(
        select(Folder).where(
            Folder.id == folder_id,
            Folder.user_id == current_user.id,
        )
    )
    folder = result.scalar_one_or_none()
    if not folder:
        raise HTTPException(status_code=404, detail="文件夹不存在")

    folder.name = data.name
    await db.commit()
    await db.refresh(folder)
    return FolderResponse.model_validate(folder)


@router.delete("/{folder_id}")
async def delete_folder(
    folder_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    result = await db.execute(
        select(Folder).where(
            Folder.id == folder_id,
            Folder.user_id == current_user.id,
        )
    )
    folder = result.scalar_one_or_none()
    if not folder:
        raise HTTPException(status_code=404, detail="文件夹不存在")

    # Move documents in this folder to root (folder_id = None)
    docs_result = await db.execute(
        select(Document).where(
            Document.folder_id == folder_id,
            Document.user_id == current_user.id,
        )
    )
    for doc in docs_result.scalars().all():
        doc.folder_id = None

    # Reparent child folders to root
    children_result = await db.execute(
        select(Folder).where(
            Folder.parent_id == folder_id,
            Folder.user_id == current_user.id,
        )
    )
    for child in children_result.scalars().all():
        child.parent_id = None

    await db.delete(folder)
    await db.commit()
    return {"message": "文件夹已删除"}


@router.post("/move-document/{doc_id}")
async def move_document(
    doc_id: int,
    data: MoveDocumentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """Move a document to a different folder."""
    # Validate document
    doc_result = await db.execute(
        select(Document).where(
            Document.id == doc_id,
            Document.user_id == current_user.id,
        )
    )
    doc = doc_result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    # Validate target folder (None = root)
    if data.folder_id is not None:
        folder_result = await db.execute(
            select(Folder).where(
                Folder.id == data.folder_id,
                Folder.user_id == current_user.id,
            )
        )
        if not folder_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="目标文件夹不存在")

    doc.folder_id = data.folder_id
    await db.commit()
    return {"message": "文档已移动"}
