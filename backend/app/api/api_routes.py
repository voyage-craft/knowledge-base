"""API Routes management endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone

from sqlalchemy import select, delete
from app.core.database import AsyncSessionLocal, get_db
from app.api.auth import get_current_user_dep
from app.core.deps import require_admin
from app.models.user import User
from app.models.api_endpoint import ApiEndpoint, ApiRoutingRule
from app.services.api_router import api_router
from app.services.provider_templates import get_all_templates, get_template

router = APIRouter(prefix="/api/api-routes", tags=["api-routes"])


# ── Pydantic schemas ──

class EndpointCreate(BaseModel):
    name: str
    provider: str
    base_url: str
    api_key: str = ""
    protocol: str = "openai"
    supported_models: list[str] = []
    priority: int = 100
    timeout_ms: int = 60000
    protocol_mode: str = "auto"  # "auto", "completions", "responses"

class EndpointUpdate(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    supported_models: Optional[list[str]] = None
    priority: Optional[int] = None
    timeout_ms: Optional[int] = None
    is_active: Optional[bool] = None
    protocol_mode: Optional[str] = None

class RuleCreate(BaseModel):
    model_id: str
    endpoint_id: Optional[int] = None
    is_locked: bool = False
    priority: int = 100
    max_requests_per_minute: Optional[int] = None

class RuleLock(BaseModel):
    model_id: str
    endpoint_id: int


def endpoint_to_dict(ep: ApiEndpoint, mask_key: bool = True) -> dict:
    api_key = ep.api_key
    if mask_key:
        # Never return any portion of the key over HTTP; only a presence flag
        api_key = "set" if api_key else ""
    return {
        "id": ep.id,
        "name": ep.name,
        "provider": ep.provider,
        "base_url": ep.base_url,
        "api_key": api_key,
        "protocol": ep.protocol,
        "supported_models": ep.supported_models or [],
        "is_active": ep.is_active,
        "priority": ep.priority,
        "status": ep.status,
        "stats_json": ep.stats_json or {},
        "frozen_until": ep.frozen_until.isoformat() if ep.frozen_until else None,
        "timeout_ms": ep.timeout_ms,
        "protocol_mode": ep.protocol_mode or "auto",
        "created_at": ep.created_at.isoformat() if ep.created_at else None,
        "updated_at": ep.updated_at.isoformat() if ep.updated_at else None,
    }


def endpoint_to_public_dict(ep: ApiEndpoint) -> dict:
    """Minimal, infrastructure-safe representation for non-admin users.

    Excludes base_url, stats, errors, frozen state — only what the UI needs to
    show which models are available.
    """
    return {
        "id": ep.id,
        "name": ep.name,
        "provider": ep.provider,
        "supported_models": ep.supported_models or [],
        "is_active": ep.is_active,
        "status": ep.status,
        "priority": ep.priority,
    }

@router.get("/providers")
async def list_providers(user=Depends(get_current_user_dep)):
    return get_all_templates()


# ── Endpoints CRUD ──

@router.get("/endpoints")
async def list_endpoints(user=Depends(get_current_user_dep)):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(ApiEndpoint).order_by(ApiEndpoint.priority, ApiEndpoint.id))
        endpoints = result.scalars().all()
        is_admin = getattr(user, "is_admin", False)
        if is_admin:
            return [endpoint_to_dict(ep) for ep in endpoints]
        # Non-admins only see a minimal, infrastructure-safe view
        return [endpoint_to_public_dict(ep) for ep in endpoints]


@router.post("/endpoints")
async def create_endpoint(data: EndpointCreate, user=Depends(require_admin)):
    # SSRF guard: reject disallowed base_url schemes / internal addresses
    try:
        from app.services.api_router import validate_base_url
        validate_base_url(data.base_url)
    except ValueError as exc:
        raise HTTPException(400, f"无效的 base_url: {exc}")

    async with AsyncSessionLocal() as session:
        ep = ApiEndpoint(
            name=data.name,
            provider=data.provider,
            base_url=data.base_url,
            api_key=data.api_key,
            protocol=data.protocol,
            supported_models=data.supported_models,
            priority=data.priority,
            timeout_ms=data.timeout_ms,
            protocol_mode=data.protocol_mode,
        )
        session.add(ep)
        await session.commit()
        await session.refresh(ep)
        return endpoint_to_dict(ep)


@router.put("/endpoints/{endpoint_id}")
async def update_endpoint(endpoint_id: int, data: EndpointUpdate, user=Depends(require_admin)):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(ApiEndpoint).where(ApiEndpoint.id == endpoint_id))
        ep = result.scalar_one_or_none()
        if not ep:
            raise HTTPException(404, "端点不存在")

        # SSRF guard: reject disallowed base_url schemes / internal addresses
        if data.base_url is not None:
            try:
                from app.services.api_router import validate_base_url
                validate_base_url(data.base_url)
            except ValueError as exc:
                raise HTTPException(400, f"无效的 base_url: {exc}")

        # Evict cached client if API key is being changed
        if data.api_key:
            await api_router._evict_client(ep)

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(ep, field, value)

        await session.commit()
        await session.refresh(ep)
        return endpoint_to_dict(ep)


@router.delete("/endpoints/{endpoint_id}")
async def delete_endpoint(endpoint_id: int, user=Depends(require_admin)):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(ApiEndpoint).where(ApiEndpoint.id == endpoint_id))
        ep = result.scalar_one_or_none()
        if not ep:
            raise HTTPException(404, "端点不存在")
        await session.delete(ep)
        # Also delete related routing rules
        await session.execute(
            delete(ApiRoutingRule).where(ApiRoutingRule.endpoint_id == endpoint_id)
        )
        await session.commit()
        return {"success": True}


@router.post("/endpoints/{endpoint_id}/test")
async def test_endpoint(endpoint_id: int, model: str = "", user=Depends(require_admin)):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(ApiEndpoint).where(ApiEndpoint.id == endpoint_id))
        ep = result.scalar_one_or_none()
        if not ep:
            raise HTTPException(404, "端点不存在")

        # Auto-detect protocol mode if set to "auto"
        detected_mode = ep.protocol_mode
        if detected_mode == "auto" and ep.protocol != "anthropic":
            detected_mode = await _detect_protocol_mode(ep, model)

        test_result = await api_router.test_endpoint(ep, model, protocol_mode=detected_mode)

        # Update stats and record detected protocol mode
        stats = ep.stats_json or {}
        stats["last_tested_at"] = datetime.now(timezone.utc).isoformat()
        if test_result["success"]:
            stats["avg_latency_ms"] = test_result["latency_ms"]
            if ep.status in ("frozen", "degraded", "disabled"):
                ep.status = "healthy"
                ep.frozen_until = None
            # Save detected protocol mode for auto mode
            if ep.protocol_mode == "auto" and detected_mode:
                stats["detected_protocol_mode"] = detected_mode
        else:
            stats["last_error"] = test_result.get("error", "")[:500]
        ep.stats_json = stats
        await session.commit()

        return test_result


async def _detect_protocol_mode(ep: ApiEndpoint, model: str) -> str:
    """Auto-detect whether an endpoint supports Responses API or Chat Completions API."""
    import asyncio
    from openai import AsyncOpenAI

    test_model = model or (ep.supported_models[0] if ep.supported_models else "gpt-4o-mini")
    kwargs = {"api_key": ep.api_key or "dummy"}
    if ep.base_url:
        kwargs["base_url"] = ep.base_url
    client = AsyncOpenAI(**kwargs)

    # Try Chat Completions first (most common)
    try:
        resp = await asyncio.wait_for(
            client.chat.completions.create(
                model=test_model,
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=5,
            ),
            timeout=10.0,
        )
        await client.close()
        return "completions"
    except Exception:
        pass

    # Try Responses API
    try:
        resp = await asyncio.wait_for(
            client.responses.create(
                model=test_model,
                input=[{"role": "user", "content": "Hi"}],
                max_output_tokens=5,
            ),
            timeout=10.0,
        )
        await client.close()
        return "responses"
    except Exception:
        pass

    await client.close()
    return "completions"  # Default to completions


@router.post("/endpoints/{endpoint_id}/toggle")
async def toggle_endpoint(endpoint_id: int, user=Depends(require_admin)):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(ApiEndpoint).where(ApiEndpoint.id == endpoint_id))
        ep = result.scalar_one_or_none()
        if not ep:
            raise HTTPException(404, "端点不存在")
        ep.is_active = not ep.is_active
        if not ep.is_active:
            ep.status = "disabled"
        else:
            ep.status = "healthy"
            ep.frozen_until = None
        await session.commit()
        return {"is_active": ep.is_active, "status": ep.status}


@router.post("/endpoints/{endpoint_id}/unfreeze")
async def unfreeze_endpoint(endpoint_id: int, user=Depends(require_admin)):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(ApiEndpoint).where(ApiEndpoint.id == endpoint_id))
        ep = result.scalar_one_or_none()
        if not ep:
            raise HTTPException(404, "端点不存在")
        ep.frozen_until = None
        ep.status = "healthy"
        stats = ep.stats_json or {}
        stats["consecutive_errors"] = 0
        ep.stats_json = stats
        await session.commit()
        return {"success": True, "status": ep.status}


# ── Health dashboard ──

@router.get("/health")
async def health_dashboard(user=Depends(require_admin)):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(ApiEndpoint).order_by(ApiEndpoint.id))
        endpoints = result.scalars().all()
        now = datetime.now(timezone.utc)

        summary = {"total": 0, "healthy": 0, "degraded": 0, "frozen": 0, "disabled": 0}
        details = []

        for ep in endpoints:
            summary["total"] += 1
            status = ep.status
            if ep.frozen_until and ep.frozen_until > now:
                status = "frozen"
            summary[status] = summary.get(status, 0) + 1

            stats = ep.stats_json or {}
            total = stats.get("total_requests", 0)
            success = stats.get("success_count", 0)
            success_rate = round(success / total * 100, 1) if total > 0 else None

            details.append({
                "id": ep.id,
                "name": ep.name,
                "provider": ep.provider,
                "status": status,
                "success_rate": success_rate,
                "avg_latency_ms": stats.get("avg_latency_ms", 0),
                "total_requests": total,
                "consecutive_errors": stats.get("consecutive_errors", 0),
                "last_error": stats.get("last_error"),
                "last_tested_at": stats.get("last_tested_at"),
                "frozen_until": ep.frozen_until.isoformat() if ep.frozen_until else None,
            })

        return {"summary": summary, "endpoints": details}


# ── Routing Rules ──

@router.get("/rules")
async def list_rules(user=Depends(require_admin)):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ApiRoutingRule).order_by(ApiRoutingRule.priority, ApiRoutingRule.id)
        )
        rules = result.scalars().all()
        return [
            {
                "id": r.id,
                "model_id": r.model_id,
                "endpoint_id": r.endpoint_id,
                "is_locked": r.is_locked,
                "priority": r.priority,
                "is_active": r.is_active,
                "max_requests_per_minute": r.max_requests_per_minute,
            }
            for r in rules
        ]


@router.post("/rules")
async def create_rule(data: RuleCreate, user=Depends(require_admin)):
    async with AsyncSessionLocal() as session:
        rule = ApiRoutingRule(
            model_id=data.model_id,
            endpoint_id=data.endpoint_id,
            is_locked=data.is_locked,
            priority=data.priority,
            max_requests_per_minute=data.max_requests_per_minute,
        )
        session.add(rule)
        await session.commit()
        await session.refresh(rule)
        return {"id": rule.id, "model_id": rule.model_id}


@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: int, user=Depends(require_admin)):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(ApiRoutingRule).where(ApiRoutingRule.id == rule_id))
        rule = result.scalar_one_or_none()
        if not rule:
            raise HTTPException(404, "规则不存在")
        await session.delete(rule)
        await session.commit()
        return {"success": True}


@router.post("/rules/lock")
async def lock_model(data: RuleLock, user=Depends(require_admin)):
    """Lock a model_id to a specific endpoint."""
    async with AsyncSessionLocal() as session:
        # Remove existing lock for this model
        existing = await session.execute(
            select(ApiRoutingRule).where(
                ApiRoutingRule.model_id == data.model_id,
                ApiRoutingRule.is_locked == True,
            )
        )
        old_rule = existing.scalar_one_or_none()
        if old_rule:
            await session.delete(old_rule)

        # Create new locked rule
        rule = ApiRoutingRule(
            model_id=data.model_id,
            endpoint_id=data.endpoint_id,
            is_locked=True,
            priority=0,
        )
        session.add(rule)
        await session.commit()
        return {"success": True, "model_id": data.model_id, "endpoint_id": data.endpoint_id}


# ── Resolve (for frontend AI calls) ──

@router.get("/resolve")
async def resolve_model(model: str, user=Depends(get_current_user_dep)):
    """Resolve the best endpoint for a model. Returns endpoint config for Vercel AI SDK."""
    endpoints = await api_router.resolve(model)
    if not endpoints:
        # Return 404 as JSON (not exception) so frontend can handle gracefully
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=404,
            content={"message": f"无可用端点支持模型: {model}"},
        )

    best = endpoints[0]
    # Use the first supported model from the endpoint, or fall back to the requested model
    best_models = best.supported_models or []
    resolved_model = best_models[0] if best_models else model

    # Determine effective protocol mode
    protocol_mode = best.protocol_mode or "auto"
    if protocol_mode == "auto":
        stats = best.stats_json or {}
        protocol_mode = stats.get("detected_protocol_mode", "completions")

    # API key is NOT returned — credentials stay server-side
    # The streaming endpoints (/api/ai/chat/stream, /api/ai/edit/stream) handle LLM calls internally
    return {
        "endpoint_id": best.id,
        "provider": best.provider,
        "protocol": best.protocol,
        "base_url": best.base_url,
        "model": resolved_model,
        "protocol_mode": protocol_mode,
        "candidates": len(endpoints),
    }


# ── All models ──

@router.get("/models")
async def list_models(user=Depends(get_current_user_dep)):
    models = await api_router.get_all_models()
    return models
