from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from slowapi.middleware import SlowAPIMiddleware
from contextlib import asynccontextmanager
from app.core.database import init_db, AsyncSessionLocal
from app.core.limiter import limiter
from app.api.auth import ensure_admin_user
from app.models.system_settings import SystemSetting  # noqa: F401 — ensure table is registered
from app.schemas.common import ErrorResponse, ErrorDetail, ErrorCode
import time
import uuid
import logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup — fast path, no blocking operations
    await init_db()
    async with AsyncSessionLocal() as session:
        await ensure_admin_user(session)

    # Load workflow plugins (builtin + third-party)
    # This replaces the old decorator-based registration in nodes/__init__.py
    # Plugin loader registers processors via register_with_metadata() for tracking
    try:
        from app.services.plugin_loader import plugin_loader
        plugin_loader.load_all()
    except Exception as e:
        logger.error("Plugin loading failed: %s", e)
        # Fallback: use decorator-based registration if plugin loader fails
        import app.services.workflow.nodes  # noqa: F401

    # Embedding model loads lazily on first RAG request (not at startup)
    logger.info("Application started. Embedding model will load on first use.")

    yield

    # Shutdown
    from app.services.llm_service import llm_service
    await llm_service.close()
    from app.services.api_router import api_router
    await api_router.close_all_clients()


def create_app() -> FastAPI:
    from app.core.config import get_settings as _get_settings
    _settings = _get_settings()

    # Disable API docs in production
    docs_url = "/api/docs" if _settings.DEBUG else None
    redoc_url = "/api/redoc" if _settings.DEBUG else None

    from app.core.version import SYSTEM_VERSION

    app = FastAPI(
        title="Knowledge Base API",
        version=SYSTEM_VERSION,
        description="AI知识库管理系统 API - 提供文档管理、AI分析、RAG搜索、知识图谱、工作流编排等功能",
        docs_url=docs_url,
        redoc_url=redoc_url,
        lifespan=lifespan,
        contact={"name": "KB Team"},
        license_info={"name": "MIT"},
    )

    # Combined middleware: request ID + security headers + performance tracking
    # Using @app.middleware("http") avoids BaseHTTPMiddleware buffering issues
    @app.middleware("http")
    async def app_middleware(request: Request, call_next):
        # Request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        # Performance tracking
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start

        # Response headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{duration:.4f}"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "0"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # HSTS only in production (skip for localhost/development)
        if not _settings.DEBUG:
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"

        # Log slow requests (> 2 seconds)
        if duration > 2.0:
            logger.warning("Slow request: %s %s took %.2fs", request.method, request.url.path, duration)

        return response

    # GZip compression middleware
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # CORS
    from app.core.config import get_settings as _get_settings
    _settings = _get_settings()
    cors_origins = [o.strip() for o in _settings.CORS_ORIGINS.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        max_age=600,
    )

    # Rate limiting
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)

    # Include routers
    from app.api.auth import router as auth_router
    from app.api.documents import router as documents_router
    from app.api.ai import router as ai_router
    from app.api.settings import router as settings_router
    from app.api.folders import router as folders_router
    from app.api.tags import router as tags_router
    from app.api.admin import router as admin_router
    from app.api.graph import router as graph_router
    from app.api.import_batch import router as import_batch_router
    from app.api.rag import router as rag_router
    from app.api.workflows import router as workflows_router
    from app.api.api_routes import router as api_routes_router
    from app.api.recommendations import router as recommendations_router
    from app.api.comments import router as comments_router
    from app.api.approval import router as approval_router
    from app.api.prompts import router as prompts_router
    from app.api.plugins import router as plugins_router
    from app.api.maintenance import router as maintenance_router
    from app.api.batch_tools import router as batch_tools_router

    app.include_router(auth_router)
    app.include_router(documents_router)
    app.include_router(ai_router)
    app.include_router(settings_router)
    app.include_router(folders_router)
    app.include_router(tags_router)
    app.include_router(admin_router)
    app.include_router(graph_router)
    app.include_router(import_batch_router)
    app.include_router(rag_router)
    app.include_router(workflows_router)
    app.include_router(api_routes_router)
    app.include_router(recommendations_router)
    app.include_router(comments_router)
    app.include_router(approval_router)
    app.include_router(prompts_router)
    app.include_router(plugins_router)
    app.include_router(maintenance_router)
    app.include_router(batch_tools_router)

    # Mount MCP server with authentication (SSE transport at /mcp/sse)
    try:
        from starlette.middleware.base import BaseHTTPMiddleware as _BaseHTTPMiddleware
        from starlette.responses import JSONResponse as _JSONResponse

        class MCPAuthMiddleware(_BaseHTTPMiddleware):
            """Require a valid *access* Bearer token for SSE MCP transport."""
            async def dispatch(self, request, call_next):
                from app.mcp.auth_context import set_user_id

                auth = request.headers.get("Authorization", "")
                if not auth.startswith("Bearer "):
                    return _JSONResponse({"error": "Unauthorized"}, status_code=401)
                token = auth[7:]
                try:
                    from app.core.security import decode_token
                    payload = decode_token(token)

                    # Reject refresh tokens — only access tokens authenticate MCP
                    if payload.get("type") != "access":
                        return _JSONResponse({"error": "Invalid token type"}, status_code=401)

                    user_id = payload.get("sub")
                    if not user_id:
                        return _JSONResponse({"error": "Invalid token"}, status_code=401)

                    # Confirm the user still exists and is active
                    from app.core.database import AsyncSessionLocal
                    from app.models.user import User
                    from sqlalchemy import select
                    try:
                        uid = int(user_id)
                    except (TypeError, ValueError):
                        return _JSONResponse({"error": "Invalid token"}, status_code=401)
                    async with AsyncSessionLocal() as session:
                        row = await session.execute(
                            select(User.is_active).where(User.id == uid)
                        )
                        rec = row.first()
                        if not rec or not rec[0]:
                            return _JSONResponse({"error": "User disabled"}, status_code=401)

                    request.state.user_id = user_id
                    # Propagate identity to MCP tools via contextvar (closes IDOR)
                    set_user_id(uid)
                except Exception:
                    set_user_id(None)
                    return _JSONResponse({"error": "Invalid token"}, status_code=401)
                try:
                    return await call_next(request)
                finally:
                    # Reset after the request so nothing leaks across requests
                    set_user_id(None)

        from app.mcp.server import mcp as mcp_server
        app.mount("/mcp", MCPAuthMiddleware(mcp_server.sse_app()))
        logger.info("MCP server mounted at /mcp (auth required)")
    except Exception as e:
        logger.warning("Could not mount MCP server: %s", e)

    # Global exception handlers
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        request_id = getattr(request.state, "request_id", None)
        errors = exc.errors()
        messages = []
        details = []
        for err in errors:
            loc = err.get("loc", [])
            msg = err.get("msg", "Validation error")
            field = loc[-1] if len(loc) > 1 else ""
            messages.append(f"{field}: {msg}" if field else msg)
            details.append(ErrorDetail(
                field=str(field) if field else None,
                message=msg,
                code=err.get("type"),
            ))

        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                code=ErrorCode.VALIDATION_ERROR.value,
                message="; ".join(messages),
                details=details,
                request_id=request_id,
            ).model_dump(),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        request_id = getattr(request.state, "request_id", None)
        detail = str(exc.detail)

        # Map HTTP status to error code
        code_map = {
            400: ErrorCode.VALIDATION_ERROR,
            403: ErrorCode.AUTH_INSUFFICIENT_PERMISSION,
            404: ErrorCode.RESOURCE_NOT_FOUND,
            409: ErrorCode.RESOURCE_CONFLICT,
            429: ErrorCode.RATE_LIMIT_EXCEEDED,
            500: ErrorCode.INTERNAL_ERROR,
        }

        if exc.status_code == 401:
            # Distinguish between credential errors and token errors
            if "credential" in detail.lower() or "密码" in detail or "用户名" in detail:
                error_code = ErrorCode.AUTH_INVALID_CREDENTIALS
            elif "not authenticated" in detail.lower() or "not found" in detail.lower():
                error_code = ErrorCode.AUTH_TOKEN_INVALID
            else:
                error_code = ErrorCode.AUTH_INVALID_CREDENTIALS
        else:
            error_code = code_map.get(exc.status_code, ErrorCode.INTERNAL_ERROR)

        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                code=error_code.value,
                message=str(exc.detail),
                request_id=request_id,
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", None)
        logger.exception("Unhandled exception: %s", exc)

        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                code=ErrorCode.INTERNAL_ERROR.value,
                message="Internal server error",
                request_id=request_id,
            ).model_dump(),
        )

    return app

app = create_app()

@app.get("/api/health")
async def health_check():
    """Health check endpoint with system status."""
    from app.core.version import SYSTEM_VERSION
    from app.core.database import AsyncSessionLocal
    from sqlalchemy import text

    health_status = {
        "status": "ok",
        "version": SYSTEM_VERSION,
        "timestamp": time.time(),
        "checks": {}
    }

    # Database check
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        health_status["checks"]["database"] = "ok"
    except Exception as e:
        health_status["checks"]["database"] = f"error: {str(e)}"
        health_status["status"] = "degraded"

    # LLM service check (non-blocking)
    try:
        from app.services.llm_service import llm_service
        health_status["checks"]["llm_configured"] = True
    except Exception:
        health_status["checks"]["llm_configured"] = False

    return health_status
