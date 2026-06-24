import os
import logging
from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)

# Disable rate limiting in test mode (detected by test database URL)
_is_testing = "test" in os.environ.get("DATABASE_URL", "")

# Rate limit strategies
RATE_LIMIT_STRATEGIES = {
    "default": "100/minute",      # Default for most endpoints
    "auth_login": "5/minute",     # Login attempts
    "auth_register": "3/minute",  # Registration
    "ai_generate": "10/minute",   # AI generation requests
    "ai_stream": "5/minute",      # AI streaming requests
    "upload": "20/minute",        # File uploads
    "export": "30/minute",        # Export requests
}

def _get_key_func(request):
    """Get rate limit key - uses user ID if authenticated, otherwise IP."""
    # Try to get user ID from request state
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"user:{user_id}"
    return get_remote_address(request)

limiter = Limiter(
    key_func=_get_key_func,
    enabled=not _is_testing,
    default_limits=[RATE_LIMIT_STRATEGIES["default"]],
)

if _is_testing:
    logger.info("Rate limiting disabled for testing")
else:
    logger.info("Rate limiting enabled with default: %s", RATE_LIMIT_STRATEGIES["default"])
