import jwt
import json
import secrets
import logging
import asyncio
from pathlib import Path
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from app.core.config import get_settings

logger = logging.getLogger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
settings = get_settings()

# Token blacklist with file-based persistence
# Survives server restarts; for multi-worker, use Redis
_BLACKLIST_FILE = Path("data/token_blacklist.json")
_token_blacklist: dict[str, float] = {}  # token JTI -> expiry timestamp

def _load_blacklist() -> None:
    """Load blacklist from disk on startup."""
    global _token_blacklist
    try:
        if _BLACKLIST_FILE.exists():
            data = json.loads(_BLACKLIST_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                _token_blacklist = data
                logger.info("Loaded %d blacklisted tokens from disk", len(_token_blacklist))
    except Exception as e:
        logger.warning("Failed to load token blacklist: %s", e)
        _token_blacklist = {}

def _save_blacklist() -> None:
    """Persist blacklist to disk."""
    try:
        _BLACKLIST_FILE.parent.mkdir(parents=True, exist_ok=True)
        _BLACKLIST_FILE.write_text(json.dumps(_token_blacklist), encoding="utf-8")
    except Exception as e:
        logger.error("Failed to save token blacklist: %s", e)

# Load on module import
_load_blacklist()

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
    """Add token to blacklist using JTI (for logout). Persists to disk."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM], options={"verify_signature": False})
        jti = payload.get("jti", "")
        exp = payload.get("exp", 0)
    except Exception:
        jti = token[-32:]  # Fallback: use last 32 chars as pseudo-JTI
        exp = datetime.now(timezone.utc).timestamp() + (settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400)

    if not jti:
        jti = token[-32:]

    _token_blacklist[jti] = exp
    _save_blacklist()
    logger.info("Token blacklisted (JTI: %s, expires: %s)", jti[:8], datetime.fromtimestamp(exp, tz=timezone.utc))

    if len(_token_blacklist) > 1000:
        _cleanup_expired_tokens()

def is_token_blacklisted(token: str) -> bool:
    """Check if token is blacklisted by JTI or full token."""
    # Try extracting JTI first
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM], options={"verify_signature": False})
        jti = payload.get("jti", "")
        if jti and jti in _token_blacklist:
            exp = _token_blacklist[jti]
            if datetime.now(timezone.utc).timestamp() > exp:
                del _token_blacklist[jti]
                _save_blacklist()
                return False
            return True
    except Exception:
        pass

    # Fallback: check full token as key
    if token in _token_blacklist:
        exp = _token_blacklist[token]
        if datetime.now(timezone.utc).timestamp() > exp:
            del _token_blacklist[token]
            _save_blacklist()
            return False
        return True

    return False

def _cleanup_expired_tokens() -> None:
    """Remove expired tokens from blacklist and persist."""
    now = datetime.now(timezone.utc).timestamp()
    expired = [t for t, exp in _token_blacklist.items() if now > exp]
    for t in expired:
        del _token_blacklist[t]
    if expired:
        _save_blacklist()
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
