import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import (
    hash_password, verify_password, create_access_token, create_refresh_token,
    decode_token, validate_password_strength, blacklist_token
)
from app.core.config import get_settings
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, UserResponse, RefreshRequest
from app.core.limiter import limiter
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()

# Security scheme for JWT authentication
security_scheme = HTTPBearer(auto_error=False)

# Dependency for getting current user from JWT
async def get_current_user_dep(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未认证")

    try:
        payload = decode_token(credentials.credentials)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效或过期的Token")

    # Validate token type - only access tokens allowed
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的Token类型"
        )

    try:
        user_id = int(payload["sub"])
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的Token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账户已禁用")

    # Enforce password change if required (except for auth endpoints which handle this themselves)
    if getattr(user, "must_change_password", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要修改密码，请先修改密码后再继续操作",
        )

    return user


async def get_current_user_allow_password_change(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Like get_current_user_dep but allows access when must_change_password is True.
    Used only for the change-password endpoint."""
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未认证")

    try:
        payload = decode_token(credentials.credentials)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效或过期的Token")

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的Token类型"
        )

    try:
        user_id = int(payload["sub"])
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的Token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账户已禁用")

    return user

@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    # Find user
    result = await db.execute(select(User).where(User.username == data.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已禁用",
        )

    access_token = create_access_token({"sub": str(user.id), "username": user.username})
    refresh_token = create_refresh_token({"sub": str(user.id), "username": user.username})

    logger.info("用户 %s 登录成功", user.username)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    data: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        payload = decode_token(data.refresh_token, check_blacklist=False)
        if payload.get("type") != "refresh":
            raise ValueError("Not a refresh token")
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效或过期的刷新Token")

    # Verify user still exists and is active
    user_id = int(payload["sub"])
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户已禁用或不存在")

    # Blacklist old refresh token to prevent reuse (token rotation)
    blacklist_token(data.refresh_token)

    access_token = create_access_token({"sub": payload["sub"], "username": payload["username"]})
    new_refresh = create_refresh_token({"sub": payload["sub"], "username": payload["username"]})

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

@router.get("/me", response_model=UserResponse)
async def get_current_user(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        is_admin=current_user.is_admin,
    )

class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)

@router.post("/change-password")
@limiter.limit("10/minute")
async def change_password(
    request: Request,
    data: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_allow_password_change),
):
    if not verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="当前密码错误")

    # Validate new password strength
    is_valid, error_msg = validate_password_strength(data.new_password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)

    # Prevent reusing same password
    if verify_password(data.new_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="新密码不能与当前密码相同")

    current_user.hashed_password = hash_password(data.new_password)
    # Clear the must_change_password flag
    if hasattr(current_user, "must_change_password"):
        current_user.must_change_password = False
    await db.commit()

    logger.info("Password changed for user %s", current_user.username)
    return {"message": "密码修改成功"}


@router.post("/logout")
async def logout(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False)),
):
    """Logout by blacklisting the current access token."""
    if credentials and credentials.credentials:
        blacklist_token(credentials.credentials)
    return {"message": "已退出登录"}

# Auto-create admin on first startup
async def ensure_admin_user(db: AsyncSession):
    result = await db.execute(select(User).where(User.is_admin == True))
    admin = result.scalar_one_or_none()
    if not admin:
        import secrets
        import os

        # Get initial password from environment or generate random
        initial_password = os.environ.get("ADMIN_INITIAL_PASSWORD", "")
        password_was_generated = False
        if not initial_password:
            initial_password = secrets.token_urlsafe(16)
            password_was_generated = True
            logger.warning(
                "Initial admin password generated. Set ADMIN_INITIAL_PASSWORD env var to specify your own. "
                "Check the startup output or reset via admin API."
            )
            # Print to stdout for first-run discovery (not logged to file)
            print(f"[STARTUP] Initial admin password: {initial_password} (change immediately!)")

        try:
            admin = User(
                username="admin",
                email="admin@localhost",
                hashed_password=hash_password(initial_password),
                is_admin=True,
                is_active=True,
                # Only force password change when auto-generated; env var passwords
                # were deliberately set by the operator
                must_change_password=password_was_generated,
            )
            db.add(admin)
            await db.commit()
        except Exception:
            # Another worker may have created the admin concurrently
            await db.rollback()
