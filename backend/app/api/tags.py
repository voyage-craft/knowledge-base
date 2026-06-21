from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete as sql_delete
from pydantic import BaseModel, constr, field_validator
import re
from typing import Optional
from app.core.database import get_db
from app.models.document import Tag, Document, document_tags
from app.api.auth import get_current_user_dep
from app.models.user import User

router = APIRouter(prefix="/api/tags", tags=["tags"])


class TagCreate(BaseModel):
    name: constr(min_length=1, max_length=100)
    color: str = "#3B82F6"

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: str) -> str:
        if not re.match(r"^#[0-9A-Fa-f]{6}$", v):
            raise ValueError("颜色必须是有效的十六进制格式，如 #3B82F6")
        return v


class TagResponse(BaseModel):
    id: int
    name: str
    color: str

    class Config:
        from_attributes = True


class AssignTagsRequest(BaseModel):
    tag_ids: list[int]


@router.get("", response_model=list[TagResponse])
async def list_tags(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    result = await db.execute(
        select(Tag)
        .where(Tag.user_id == current_user.id)
        .order_by(Tag.name.asc())
    )
    tags = result.scalars().all()
    return [TagResponse.model_validate(t) for t in tags]


@router.post("", response_model=TagResponse, status_code=status.HTTP_201_CREATED)
async def create_tag(
    data: TagCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    # Check for duplicate name (per-user uniqueness)
    existing = await db.execute(
        select(Tag).where(Tag.name == data.name, Tag.user_id == current_user.id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="标签名已存在")

    tag = Tag(
        name=data.name,
        color=data.color,
        user_id=current_user.id,
    )
    db.add(tag)
    await db.commit()
    await db.refresh(tag)
    return TagResponse.model_validate(tag)


@router.delete("/{tag_id}")
async def delete_tag(
    tag_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    result = await db.execute(
        select(Tag).where(
            Tag.id == tag_id,
            Tag.user_id == current_user.id,
        )
    )
    tag = result.scalar_one_or_none()
    if not tag:
        raise HTTPException(status_code=404, detail="标签不存在")

    # Remove all document-tag associations first
    await db.execute(
        sql_delete(document_tags).where(document_tags.c.tag_id == tag_id)
    )
    await db.delete(tag)
    await db.commit()
    return {"message": "标签已删除"}


@router.put("/assign/{doc_id}")
async def assign_tags(
    doc_id: int,
    data: AssignTagsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """Replace all tags on a document with the given tag IDs."""
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

    # Fetch requested tags (must belong to user)
    if data.tag_ids:
        tags_result = await db.execute(
            select(Tag).where(
                Tag.id.in_(data.tag_ids),
                Tag.user_id == current_user.id,
            )
        )
        tags = list(tags_result.scalars().all())
    else:
        tags = []

    # Replace all tags
    doc.tags = tags
    await db.commit()
    return {"message": "标签已更新"}
