"""Comments and annotations API endpoints.

Provides functionality for:
- Document comments with threading support
- Inline annotations anchored to document positions
- Comment resolution tracking
- Emoji reactions

Endpoints:
    POST /api/documents/{doc_id}/comments - Create comment
    GET /api/documents/{doc_id}/comments - List comments
    PUT /api/comments/{comment_id} - Edit comment
    DELETE /api/comments/{comment_id} - Delete comment
    POST /api/comments/{comment_id}/resolve - Mark as resolved
    POST /api/comments/{comment_id}/reactions - Add reaction
    DELETE /api/comments/{comment_id}/reactions/{emoji} - Remove reaction
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone

from app.core.database import get_db
from app.api.auth import get_current_user_dep
from app.models.user import User
from app.models.document import Document
from app.models.collaboration import Comment, CommentReaction
from app.core.events import publish_comment_added

router = APIRouter(tags=["comments"])


class CommentCreate(BaseModel):
    """Request model for creating a comment."""
    content: str = Field(..., min_length=1, max_length=5000)
    parent_id: Optional[int] = None
    anchor_start: Optional[int] = None
    anchor_end: Optional[int] = None
    annotation_text: Optional[str] = Field(None, max_length=500)


class CommentUpdate(BaseModel):
    """Request model for updating a comment."""
    content: str = Field(..., min_length=1, max_length=5000)


class ReactionCreate(BaseModel):
    """Request model for adding a reaction."""
    emoji: str = Field(..., pattern="^(thumbs_up|heart|check|question)$")


class CommentResponse(BaseModel):
    """Response model for a comment."""
    id: int
    document_id: int
    user_id: int
    parent_id: Optional[int]
    content: str
    anchor_start: Optional[int]
    anchor_end: Optional[int]
    annotation_text: Optional[str]
    is_resolved: bool
    resolved_by_id: Optional[int]
    resolved_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    reactions: dict[str, int] = {}  # emoji -> count
    replies: list["CommentResponse"] = []


@router.post("/api/documents/{doc_id}/comments", response_model=CommentResponse, status_code=201)
async def create_comment(
    doc_id: int,
    data: CommentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """Create a new comment on a document.

    Args:
        doc_id: Document ID to comment on
        data: Comment content and optional anchor positions

    Returns:
        Created comment with metadata
    """
    # Verify document exists and user has access
    doc = await db.get(Document, doc_id)
    if not doc or doc.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="文档不存在")

    # Verify parent comment exists if specified
    if data.parent_id:
        parent = await db.get(Comment, data.parent_id)
        if not parent or parent.document_id != doc_id:
            raise HTTPException(status_code=400, detail="父评论不存在")

    # Create comment
    comment = Comment(
        document_id=doc_id,
        user_id=current_user.id,
        parent_id=data.parent_id,
        content=data.content,
        anchor_start=data.anchor_start,
        anchor_end=data.anchor_end,
        annotation_text=data.annotation_text,
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)

    # Publish event
    await publish_comment_added(doc_id, comment.id, current_user.id)

    return CommentResponse(
        id=comment.id,
        document_id=comment.document_id,
        user_id=comment.user_id,
        parent_id=comment.parent_id,
        content=comment.content,
        anchor_start=comment.anchor_start,
        anchor_end=comment.anchor_end,
        annotation_text=comment.annotation_text,
        is_resolved=comment.is_resolved,
        resolved_by_id=comment.resolved_by_id,
        resolved_at=comment.resolved_at,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
    )


@router.get("/api/documents/{doc_id}/comments", response_model=list[CommentResponse])
async def list_comments(
    doc_id: int,
    include_resolved: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """List all comments on a document.

    Args:
        doc_id: Document ID
        include_resolved: Whether to include resolved comments

    Returns:
        List of comments with nested replies
    """
    # Verify document exists and user has access
    doc = await db.get(Document, doc_id)
    if not doc or doc.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="文档不存在")

    # Get top-level comments
    query = select(Comment).where(Comment.document_id == doc_id)
    if not include_resolved:
        query = query.where(Comment.is_resolved == False)
    query = query.where(Comment.parent_id.is_(None)).order_by(desc(Comment.created_at))

    result = await db.execute(query)
    top_comments = result.scalars().all()

    # Build response with replies and reactions
    comments_response = []
    for comment in top_comments:
        comment_data = await _build_comment_response(db, comment)
        comments_response.append(comment_data)

    return comments_response


@router.put("/api/comments/{comment_id}", response_model=CommentResponse)
async def update_comment(
    comment_id: int,
    data: CommentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """Update a comment's content.

    Args:
        comment_id: Comment ID to update
        data: New content

    Returns:
        Updated comment
    """
    result = await db.execute(
        select(Comment).where(
            Comment.id == comment_id,
            Comment.user_id == current_user.id,
        )
    )
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail="评论不存在")

    comment.content = data.content
    comment.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(comment)

    return await _build_comment_response(db, comment)


@router.delete("/api/comments/{comment_id}")
async def delete_comment(
    comment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """Delete a comment.

    Args:
        comment_id: Comment ID to delete

    Returns:
        Success message
    """
    result = await db.execute(
        select(Comment).where(
            Comment.id == comment_id,
            Comment.user_id == current_user.id,
        )
    )
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail="评论不存在")

    await db.delete(comment)
    await db.commit()

    return {"message": "评论已删除"}


@router.post("/api/comments/{comment_id}/resolve", response_model=CommentResponse)
async def resolve_comment(
    comment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """Mark a comment as resolved.

    Args:
        comment_id: Comment ID to resolve

    Returns:
        Updated comment

    Authorization:
        - User must be the comment author OR document owner OR have write access
    """
    result = await db.execute(
        select(Comment).where(Comment.id == comment_id)
    )
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail="评论不存在")

    # Verify authorization: user must be comment author OR document owner
    doc = await db.get(Document, comment.document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    is_comment_author = comment.user_id == current_user.id
    is_document_owner = doc.user_id == current_user.id

    # Check for write access via DocumentShare (if implemented)
    has_write_access = False
    if not is_comment_author and not is_document_owner:
        # Check DocumentShare for write permission
        from app.models.collaboration import DocumentShare
        share_result = await db.execute(
            select(DocumentShare).where(
                DocumentShare.document_id == comment.document_id,
                DocumentShare.shared_with_id == current_user.id,
                DocumentShare.permission.in_(["write", "admin"]),
            )
        )
        has_write_access = share_result.scalar_one_or_none() is not None

    if not is_comment_author and not is_document_owner and not has_write_access:
        raise HTTPException(status_code=403, detail="无权解析此评论")

    comment.is_resolved = True
    comment.resolved_by_id = current_user.id
    comment.resolved_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(comment)

    return await _build_comment_response(db, comment)


@router.post("/api/comments/{comment_id}/reactions")
async def add_reaction(
    comment_id: int,
    data: ReactionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """Add an emoji reaction to a comment.

    Args:
        comment_id: Comment ID
        data: Reaction emoji

    Returns:
        Success message
    """
    result = await db.execute(
        select(Comment).where(Comment.id == comment_id)
    )
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail="评论不存在")

    # Check if reaction already exists
    existing = await db.execute(
        select(CommentReaction).where(
            CommentReaction.comment_id == comment_id,
            CommentReaction.user_id == current_user.id,
            CommentReaction.emoji == data.emoji,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="已存在相同反应")

    reaction = CommentReaction(
        comment_id=comment_id,
        user_id=current_user.id,
        emoji=data.emoji,
    )
    db.add(reaction)
    await db.commit()

    return {"message": "反应已添加"}


@router.delete("/api/comments/{comment_id}/reactions/{emoji}")
async def remove_reaction(
    comment_id: int,
    emoji: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    """Remove an emoji reaction from a comment.

    Args:
        comment_id: Comment ID
        emoji: Emoji to remove

    Returns:
        Success message
    """
    if emoji not in ("thumbs_up", "heart", "check", "question"):
        raise HTTPException(status_code=400, detail="无效的表情")

    result = await db.execute(
        select(CommentReaction).where(
            CommentReaction.comment_id == comment_id,
            CommentReaction.user_id == current_user.id,
            CommentReaction.emoji == emoji,
        )
    )
    reaction = result.scalar_one_or_none()
    if not reaction:
        raise HTTPException(status_code=404, detail="反应不存在")

    await db.delete(reaction)
    await db.commit()

    return {"message": "反应已删除"}


async def _build_comment_response(db: AsyncSession, comment: Comment) -> CommentResponse:
    """Build a complete comment response with reactions and replies."""
    # Get reactions
    reactions_result = await db.execute(
        select(CommentReaction.emoji, func.count(CommentReaction.id))
        .where(CommentReaction.comment_id == comment.id)
        .group_by(CommentReaction.emoji)
    )
    reactions = {row[0]: row[1] for row in reactions_result.all()}

    # Get replies
    replies_result = await db.execute(
        select(Comment)
        .where(Comment.parent_id == comment.id)
        .order_by(Comment.created_at)
    )
    replies = replies_result.scalars().all()

    replies_response = []
    for reply in replies:
        reply_data = await _build_comment_response(db, reply)
        replies_response.append(reply_data)

    return CommentResponse(
        id=comment.id,
        document_id=comment.document_id,
        user_id=comment.user_id,
        parent_id=comment.parent_id,
        content=comment.content,
        anchor_start=comment.anchor_start,
        anchor_end=comment.anchor_end,
        annotation_text=comment.annotation_text,
        is_resolved=comment.is_resolved,
        resolved_by_id=comment.resolved_by_id,
        resolved_at=comment.resolved_at,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        reactions=reactions,
        replies=replies_response,
    )
