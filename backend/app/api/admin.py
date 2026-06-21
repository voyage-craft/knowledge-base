from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import get_db
from app.core.security import hash_password
from app.models.user import User
from app.api.auth import get_current_user_dep
from app.api.settings import require_admin
from app.schemas.admin import (
    AdminUserResponse,
    AdminCreateUserRequest,
    AdminUpdateUserRequest,
    AdminResetPasswordRequest,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/users")
async def list_users(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: str = Query("", max_length=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    query = select(User)

    if search:
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(
            User.username.ilike(f"%{escaped}%", escape="\\")
            | User.email.ilike(f"%{escaped}%", escape="\\")
        )

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    result = await db.execute(
        query.order_by(User.created_at.desc()).offset(offset).limit(limit)
    )
    users = result.scalars().all()

    return {
        "users": [AdminUserResponse.model_validate(u) for u in users],
        "total": total,
    }


@router.post("/users", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    data: AdminCreateUserRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    # Check unique username
    existing = (await db.execute(
        select(User).where(User.username == data.username)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")

    # Check unique email
    existing_email = (await db.execute(
        select(User).where(User.email == data.email)
    )).scalar_one_or_none()
    if existing_email:
        raise HTTPException(status_code=400, detail="邮箱已被使用")

    user = User(
        username=data.username,
        email=data.email,
        hashed_password=hash_password(data.password),
        is_admin=data.is_admin,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return AdminUserResponse.model_validate(user)


@router.put("/users/{user_id}", response_model=AdminUserResponse)
async def update_user(
    user_id: int,
    data: AdminUpdateUserRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if user_id == admin.id and data.is_admin is False:
        raise HTTPException(status_code=400, detail="不能取消自己的管理员权限")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    update_data = data.model_dump(exclude_unset=True)
    # Whitelist allowed fields to prevent unsafe setattr on sensitive columns
    ALLOWED_ADMIN_FIELDS = {"is_active", "is_admin", "email"}
    update_data = {k: v for k, v in update_data.items() if k in ALLOWED_ADMIN_FIELDS}
    for key, value in update_data.items():
        setattr(user, key, value)

    await db.commit()
    await db.refresh(user)
    return AdminUserResponse.model_validate(user)


@router.post("/users/{user_id}/reset-password")
async def reset_password(
    user_id: int,
    data: AdminResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    user.hashed_password = hash_password(data.new_password)
    await db.commit()
    return {"message": "密码已重置"}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="不能删除自己的账户")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    user.is_active = False
    await db.commit()
    return {"message": "用户已禁用"}
