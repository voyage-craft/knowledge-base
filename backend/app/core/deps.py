"""
Shared dependencies for API routes.

This module contains common dependencies used across multiple API modules
to avoid code duplication.
"""
import logging
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.models.user import User
from app.api.auth import get_current_user_dep

logger = logging.getLogger(__name__)


async def require_admin(
    current_user: User = Depends(get_current_user_dep),
) -> User:
    """Dependency that requires the current user to be an admin.

    Usage:
        @router.get("/admin/users")
        async def list_users(admin: User = Depends(require_admin)):
            ...
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return current_user


async def get_document_or_404(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
) -> "Document":
    """Dependency that fetches a document by ID and verifies ownership.

    Returns 404 if document not found or doesn't belong to the user.

    Usage:
        @router.get("/documents/{doc_id}")
        async def get_document(doc: Document = Depends(get_document_or_404)):
            return doc
    """
    from app.models.document import Document

    result = await db.execute(
        select(Document).where(
            Document.id == doc_id,
            Document.user_id == current_user.id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    return doc
