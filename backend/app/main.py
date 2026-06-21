from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
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


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Add request ID to all requests for tracing."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "0"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return response


class PerformanceMiddleware(BaseHTTPMiddleware):
    """Track request processing time and log slow requests."""

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start

        # Add processing time header
        response.headers["X-Process-Time"] = f"{duration:.4f}"

        # Log slow requests (> 2 seconds)
        if duration > 2.0:
            logger.warning(
                "Slow request: %s %s took %.2fs",
                request.method,
                request.url.path,
                duration,
            )

        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    async with AsyncSessionLocal() as session:
        await ensure_admin_user(session)

    # Pre-load embedding model if configured
    try:
        from app.services.embedding_service import embedding_service
        await embedding_service._load_model()
        logger.info("Embedding model pre-loaded successfully")
    except Exception as e:
        logger.warning("Could not pre-load embedding model: %s", e)

    yield

    # Shutdown
    from app.services.llm_service import llm_service
    await llm_service.close()
    from app.services.api_router import api_router
    await api_router.close_all_clients()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Knowledge Base API",
        version="0.1.0",
        description="AI知识库管理系统 API - 提供文档管理、AI分析、RAG搜索、知识图谱、工作流编排等功能",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        lifespan=lifespan,
        contact={"name": "KB Team"},
        license_info={"name": "MIT"},
    )

    # Request ID middleware (must be first)
    app.add_middleware(RequestIDMiddleware)

    # Security headers middleware
    app.add_middleware(SecurityHeadersMiddleware)

    # Performance monitoring middleware
    app.add_middleware(PerformanceMiddleware)

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

    # Mount MCP server with authentication (SSE transport at /mcp/sse)
    try:
        from starlette.middleware.base import BaseHTTPMiddleware
        from starlette.requests import Request as StarletteRequest
        from starlette.responses import JSONResponse

        class MCPAuthMiddleware(BaseHTTPMiddleware):
            """Require Bearer token for SSE MCP transport."""
            async def dispatch(self, request: StarletteRequest, call_next):
                auth = request.headers.get("Authorization", "")
                if not auth.startswith("Bearer "):
                    return JSONResponse({"error": "Unauthorized"}, status_code=401)
                token = auth[7:]
                try:
                    from app.core.security import decode_token
                    payload = decode_token(token)
                    request.state.user_id = payload.get("sub")
                except Exception:
                    return JSONResponse({"error": "Invalid token"}, status_code=401)
                return await call_next(request)

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
    return {"status": "ok", "version": "0.1.0"}
