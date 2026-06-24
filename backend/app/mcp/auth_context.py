"""Context propagation for the MCP server.

The SSE middleware (main.py) authenticates the bearer token and sets
``request.state.user_id``. FastMCP tool functions don't receive the request,
so we mirror that identity into a ContextVar that tools read to scope every
query by the calling user. This closes the MCP IDOR gap (any caller could
otherwise read/write every user's documents).

Usage in a tool::

    from app.mcp.auth_context import require_user_id

    async def my_tool(...):
        user_id = require_user_id()  # raises if not authenticated
        ... where(Document.user_id == user_id) ...
"""

from contextvars import ContextVar
from typing import Optional

# The authenticated user id for the current MCP request, or None for the
# stdio transport (local-only, trusted).
current_user_id: ContextVar[Optional[int]] = ContextVar("mcp_current_user_id", default=None)


def set_user_id(user_id: Optional[int]) -> None:
    """Set the current user id (called from auth middleware / stdio server)."""
    current_user_id.set(user_id)


def get_user_id() -> Optional[int]:
    """Return the current user id, or None when unauthenticated/stdio."""
    return current_user_id.get()


def require_user_id() -> int:
    """Return the current user id, raising if absent.

    For the stdio transport (no HTTP request, local-only) the value defaults
    to 1 (first admin) for backward compatibility with Claude Desktop etc.
    """
    uid = current_user_id.get()
    if uid is not None:
        return uid
    # Stdio / local fallback: act as the first admin user. This transport is
    # documented as local-only and trusted, so broad access is acceptable.
    return 1
