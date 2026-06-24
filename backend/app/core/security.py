import jwt
import secrets
import logging
import asyncio
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from app.core.config import get_settings

logger = logging.getLogger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
settings = get_settings()

# In-memory token blacklist with expiry tracking (for logout/invalidation)
# In production, use Redis for distributed blacklist
_token_blacklist: dict[str, float] = {}  # token -> expiry timestamp
_blacklist_cleanup_interval: int = 3600  # Cleanup every hour

def hash_password(password: str) -> str:
    """Hash password with bcrypt."""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash."""
    return pwd_context.verify(plain_password, hashed_password)

def validate_password_strength(password: str) -> tuple[bool, str]:
    """Validate password meets security requirements.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if len(password) < 8:
        return False, "密码长度至少8个字符"
    if len(password) > 128:
        return False, "密码长度不能超过128个字符"
    if not any(c.isupper() for c in password):
        return False, "密码必须包含至少一个大写字母"
    if not any(c.islower() for c in password):
        return False, "密码必须包含至少一个小写字母"
    if not any(c.isdigit() for c in password):
        return False, "密码必须包含至少一个数字"
    return True, ""

def blacklist_token(token: str) -> None:
    """Add token to blacklist (for logout) with expiry tracking."""
    try:
        # Decode without verification to get expiry
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM], options={"verify_signature": False})
        exp = payload.get("exp", 0)
    except Exception:
        # If can't decode, use max expiry (refresh token max)
        exp = datetime.now(timezone.utc).timestamp() + (settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400)

    _token_blacklist[token] = exp
    logger.info("Token blacklisted (expires: %s)", datetime.fromtimestamp(exp, tz=timezone.utc))

    # Trigger cleanup if blacklist is large
    if len(_token_blacklist) > 1000:
        _cleanup_expired_tokens()

def is_token_blacklisted(token: str) -> bool:
    """Check if token is blacklisted."""
    if token not in _token_blacklist:
        return False

    # Check if blacklist entry has expired
    exp = _token_blacklist[token]
    if datetime.now(timezone.utc).timestamp() > exp:
        del _token_blacklist[token]
        return False

    return True

def _cleanup_expired_tokens() -> None:
    """Remove expired tokens from blacklist."""
    now = datetime.now(timezone.utc).timestamp()
    expired = [t for t, exp in _token_blacklist.items() if now > exp]
    for t in expired:
        del _token_blacklist[t]
    if expired:
        logger.info("Cleaned up %d expired tokens from blacklist", len(expired))

def get_blacklist_size() -> int:
    """Get current blacklist size (for monitoring)."""
    return len(_token_blacklist)

def create_access_token(data: dict) -> str:
    """Create JWT access token with JTI for blacklisting support."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({
        "exp": expire,
        "type": "access",
        "jti": secrets.token_hex(16),  # Unique token ID
        "iat": datetime.now(timezone.utc),
    })
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def create_refresh_token(data: dict) -> str:
    """Create JWT refresh token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({
        "exp": expire,
        "type": "refresh",
        "jti": secrets.token_hex(16),
        "iat": datetime.now(timezone.utc),
    })
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def decode_token(token: str, check_blacklist: bool = True) -> dict:
    """Decode and validate JWT token.

    Args:
        token: JWT token string
        check_blacklist: Whether to check token blacklist

    Returns:
        Decoded payload

    Raises:
        ValueError: If token is invalid, expired, or blacklisted
    """
    try:
        # Check blacklist first
        if check_blacklist and is_token_blacklisted(token):
            raise ValueError("Token has been revoked")

        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("Token expired")
    except jwt.InvalidTokenError:
        raise ValueError("Invalid token")
