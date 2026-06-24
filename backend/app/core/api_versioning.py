"""
API版本控制工具

提供API版本管理功能，支持向后兼容。
当前版本: v1 (默认)

使用方式:
    from app.core.api_versioning import create_versioned_router

    router = create_versioned_router("documents", tags=["documents"])
    # 等价于 APIRouter(prefix="/api/v1/documents", tags=["documents"])
"""
from fastapi import APIRouter


def create_versioned_router(
    name: str,
    version: str = "v1",
    tags: list[str] | None = None,
    **kwargs,
) -> APIRouter:
    """Create a router with version prefix.

    Args:
        name: Router name (e.g., "documents", "auth")
        version: API version (default: "v1")
        tags: OpenAPI tags
        **kwargs: Additional APIRouter arguments

    Returns:
        APIRouter with /api/{version}/{name} prefix
    """
    prefix = f"/api/{version}/{name}"
    return APIRouter(prefix=prefix, tags=tags or [name], **kwargs)


def create_compat_router(
    name: str,
    version: str = "v1",
    tags: list[str] | None = None,
    **kwargs,
) -> APIRouter:
    """Create a router that supports both versioned and unversioned paths.

    This creates a router at /api/v1/{name} that also responds to /api/{name}
    for backward compatibility.

    Note: This creates TWO routers. Include both in your app.

    Returns:
        Tuple of (versioned_router, compat_router)
    """
    versioned = APIRouter(
        prefix=f"/api/{version}/{name}",
        tags=tags or [name],
        **kwargs,
    )
    compat = APIRouter(
        prefix=f"/api/{name}",
        tags=tags or [name],
        **kwargs,
    )
    return versioned, compat


# Current API version
API_VERSION = "v1"

# Version deprecation schedule
VERSION_SCHEDULE = {
    "v1": {"status": "current", "deprecated": None, "sunset": None},
}
