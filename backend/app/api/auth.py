from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from app.core.config import get_settings
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, UserResponse, RefreshRequest
from app.core.limiter import limiter
from pydantic import BaseModel, Field

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
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        payload = decode_token(credentials.credentials)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    # Validate token type - only access tokens allowed
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type. Only access tokens are allowed."
        )

    result = await db.execute(select(User).where(User.id == int(payload["sub"])))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")

    return user

@router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
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
            detail="Invalid credentials",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    access_token = create_access_token({"sub": str(user.id), "username": user.username})
    refresh_token = create_refresh_token({"sub": str(user.id), "username": user.username})

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
        payload = decode_token(data.refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError("Not a refresh token")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    # Verify user still exists and is active
    user_id = int(payload["sub"])
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户已禁用或不存在")

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
    new_password: str = Field(..., min_length=6, max_length=128)

@router.post("/change-password")
async def change_password(
    data: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_dep),
):
    if not verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="当前密码错误")

    current_user.hashed_password = hash_password(data.new_password)
    await db.commit()
    return {"message": "密码修改成功"}

# Auto-create admin on first startup
async def ensure_admin_user(db: AsyncSession):
    result = await db.execute(select(User).where(User.is_admin == True))
    admin = result.scalar_one_or_none()
    if not admin:
        import secrets
        import os

        # Get initial password from environment or generate random
        initial_password = os.environ.get("ADMIN_INITIAL_PASSWORD", "")
        if not initial_password:
            initial_password = secrets.token_urlsafe(16)
            print(f"\n[SECURITY] Generated initial admin password: {initial_password}")
            print("[SECURITY] Change this password immediately after first login.\n")

        try:
            admin = User(
                username="admin",
                email="admin@localhost",
                hashed_password=hash_password(initial_password),
                is_admin=True,
                is_active=True,
                must_change_password=True,
            )
            db.add(admin)
            await db.commit()
        except Exception:
            # Another worker may have created the admin concurrently
            await db.rollback()
