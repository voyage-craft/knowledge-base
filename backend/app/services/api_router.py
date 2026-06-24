"""API Router - Smart dispatch with failover and health tracking."""

import asyncio
import os
import time
import logging
import ipaddress
from urllib.parse import urlparse
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator, Optional

from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.api_endpoint import ApiEndpoint, ApiRoutingRule
from app.services.llm_service import LLMProviderError

logger = logging.getLogger(__name__)

# Maximum number of cached API clients before LRU eviction
MAX_CLIENT_CACHE_SIZE = 50


def validate_base_url(url: Optional[str]) -> Optional[str]:
    """Validate a user-configured LLM base_url to prevent SSRF.

    Rejects non-http(s) schemes and disallows link-local / private addresses
    unless explicitly allow-listed in SSRF_ALLOWED_HOSTS. Loopback is allowed
    by default so local LLMs (Ollama on 127.0.0.1:11434) keep working.
    Returns the safe URL or raises ValueError.
    """
    if not url:
        return url

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Disallowed URL scheme: {parsed.scheme!r}")

    host = parsed.hostname or ""
    if not host:
        raise ValueError("URL has no host")

    allow_env = os.environ.get("SSRF_ALLOWED_HOSTS", "")
    allowed = {h.strip().lower() for h in allow_env.split(",") if h.strip()}

    # Allow explicit allow-list (e.g. extra internal hosts)
    if host.lower() in allowed:
        return url

    # Loopback is allowed by default so local LLMs (Ollama on 127.0.0.1:11434)
    # keep working. Link-local (169.254.x.x cloud metadata), other private
    # ranges, and unspecified/reserved IPs remain blocked.
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_loopback:
            return url
        if ip.is_link_local or ip.is_private or ip.is_unspecified or ip.is_reserved:
            raise ValueError(f"Internal/private address not allowed: {host}")
    except ValueError:
        # host is a DNS name, not an IP — allow it (common providers)
        pass

    return url


class ApiRouter:
    """Smart API routing with failover, health tracking, and auto-freeze."""

    # LRU client cache: key = (protocol, base_url, api_key[:8]) -> client instance
    _client_cache: OrderedDict[str, object] = OrderedDict()

    # Freeze durations for progressive backoff
    FREEZE_LEVELS = [
        timedelta(minutes=2),   # 1st freeze: 2 min
        timedelta(minutes=10),  # 2nd freeze: 10 min
        timedelta(minutes=30),  # 3rd freeze: 30 min
        timedelta(hours=2),     # 4th+: 2 hours
    ]

    CONSECUTIVE_ERROR_DEGRADED = 3
    CONSECUTIVE_ERROR_FREEZE = 5

    def _get_client_key(self, ep: ApiEndpoint) -> str:
        """Generate a cache key for an endpoint's client."""
        key_prefix = (ep.api_key or "")[:8]
        return f"{ep.protocol}:{ep.base_url}:{key_prefix}"

    def _get_or_create_client(self, ep: ApiEndpoint):
        """Get a cached client or create a new one (LRU eviction at maxsize)."""
        cache_key = self._get_client_key(ep)
        client = self._client_cache.get(cache_key)
        if client is not None:
            # Move to end (most recently used)
            self._client_cache.move_to_end(cache_key)
            return client

        # Defense-in-depth SSRF check before opening an outbound connection
        validate_base_url(ep.base_url)

        # Evict oldest entries if at capacity
        while len(self._client_cache) >= MAX_CLIENT_CACHE_SIZE:
            evicted_key, evicted_client = self._client_cache.popitem(last=False)
            logger.debug("LRU evicted client: %s", evicted_key)
            # Schedule close in background (don't block)
            try:
                asyncio.get_running_loop().create_task(self._safe_close(evicted_client))
            except RuntimeError:
                pass  # No event loop, just discard

        if ep.protocol == "anthropic":
            from anthropic import AsyncAnthropic
            client = AsyncAnthropic(api_key=ep.api_key)
            if ep.base_url and "anthropic.com" not in ep.base_url:
                client.base_url = ep.base_url
        else:
            from openai import AsyncOpenAI
            kwargs = {"api_key": ep.api_key or "dummy"}
            if ep.base_url:
                kwargs["base_url"] = ep.base_url
            client = AsyncOpenAI(**kwargs)

        self._client_cache[cache_key] = client
        return client

    @staticmethod
    async def _safe_close(client):
        """Safely close a client, ignoring errors."""
        try:
            await client.close()
        except Exception:
            pass

    async def close_all_clients(self):
        """Close all cached clients (call on shutdown)."""
        for client in self._client_cache.values():
            try:
                await client.close()
            except Exception:
                pass
        self._client_cache.clear()

    async def _evict_client(self, ep: ApiEndpoint):
        """Remove and close a cached client for an endpoint (e.g., after auth failure)."""
        cache_key = self._get_client_key(ep)
        client = self._client_cache.pop(cache_key, None)
        if client:
            await self._safe_close(client)

    async def resolve(self, model_id: str) -> list[ApiEndpoint]:
        """Resolve available endpoints for a model_id, sorted by health score."""
        async with AsyncSessionLocal() as session:
            # Check for locked rule
            result = await session.execute(
                select(ApiRoutingRule).where(
                    ApiRoutingRule.model_id == model_id,
                    ApiRoutingRule.is_locked == True,
                    ApiRoutingRule.is_active == True,
                )
            )
            locked_rule = result.scalar_one_or_none()
            if locked_rule and locked_rule.endpoint_id:
                ep_result = await session.execute(
                    select(ApiEndpoint).where(ApiEndpoint.id == locked_rule.endpoint_id)
                )
                ep = ep_result.scalar_one_or_none()
                if ep and ep.is_active:
                    return [ep]

            # Find all endpoints supporting this model
            result = await session.execute(
                select(ApiEndpoint).where(
                    ApiEndpoint.is_active == True,
                    ApiEndpoint.status != "disabled",
                )
            )
            all_endpoints = result.scalars().all()

            # Filter by model support (empty supported_models = supports all)
            now = datetime.now(timezone.utc)
            candidates = []
            for ep in all_endpoints:
                # Check frozen
                if ep.frozen_until and ep.frozen_until > now:
                    continue
                models = ep.supported_models or []
                if not models or model_id in models or any(
                    model_id.startswith(m.split("/")[0]) if "/" in m else model_id == m
                    for m in models
                ):
                    candidates.append(ep)

            # Sort by health score
            candidates.sort(key=lambda ep: self._score_endpoint(ep), reverse=True)
            return candidates

    def _score_endpoint(self, ep: ApiEndpoint) -> float:
        """Calculate health score: higher is better."""
        stats = ep.stats_json or {}
        total = stats.get("total_requests", 0)
        success = stats.get("success_count", 0)
        avg_latency = stats.get("avg_latency_ms", 0)

        # Success rate (0-1), default to 0.9 for new endpoints
        if total > 0:
            success_rate = success / total
        else:
            success_rate = 0.9

        # Speed score: lower latency = higher score
        # Normalize: 0ms=1.0, 5000ms=0.5, 10000ms+=0.1
        if avg_latency > 0:
            speed_score = max(0.1, 1.0 - (avg_latency / 15000))
        else:
            speed_score = 0.8

        # Priority score: lower priority number = higher score
        priority_score = max(0, 1.0 - (ep.priority / 200))

        # Degraded penalty
        if ep.status == "degraded":
            success_rate *= 0.5

        return success_rate * 0.6 + speed_score * 0.3 + priority_score * 0.1

    async def call_with_failover(
        self,
        model_id: str,
        messages: list[dict],
        system: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        """Non-streaming call with automatic failover."""
        endpoints = await self.resolve(model_id)
        if not endpoints:
            raise LLMProviderError(f"无可用端点支持模型: {model_id}")

        errors = []
        for ep in endpoints:
            try:
                result = await self._call_endpoint(ep, model_id, messages, system, max_tokens, temperature)
                await self._record_success(ep.id)
                return result
            except Exception as e:
                logger.warning("Endpoint %s (%s) failed: %s", ep.name, ep.id, e)
                errors.append(f"{ep.name}: {e}")
                await self._record_failure(ep.id, str(e))

        raise LLMProviderError(f"所有端点均失败: {model_id}: " + "; ".join(errors))

    async def stream_with_failover(
        self,
        model_id: str,
        messages: list[dict],
        system: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        """Streaming call with automatic failover."""
        endpoints = await self.resolve(model_id)
        if not endpoints:
            raise LLMProviderError(f"无可用端点支持模型: {model_id}")

        for ep in endpoints:
            try:
                async for token in self._stream_endpoint(ep, model_id, messages, system, max_tokens, temperature):
                    yield token
                await self._record_success(ep.id)
                return
            except Exception as e:
                logger.warning("Stream endpoint %s (%s) failed: %s", ep.name, ep.id, e)
                await self._record_failure(ep.id, str(e))
                continue

        raise LLMProviderError(f"所有端点均失败: {model_id}")

    async def _call_endpoint(
        self,
        ep: ApiEndpoint,
        model_id: str,
        messages: list[dict],
        system: str,
        max_tokens: int,
        temperature: float,
    ) -> str:
        """Call a single endpoint (non-streaming) with client caching."""
        timeout_sec = ep.timeout_ms / 1000
        client = self._get_or_create_client(ep)

        if ep.protocol == "anthropic":
            response = await asyncio.wait_for(
                client.messages.create(
                    model=model_id,
                    system=system or "You are a helpful assistant.",
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                ),
                timeout=timeout_sec,
            )
            return response.content[0].text
        else:
            # Determine protocol mode
            protocol_mode = ep.protocol_mode or "auto"
            if protocol_mode == "auto":
                stats = ep.stats_json or {}
                protocol_mode = stats.get("detected_protocol_mode", "completions")

            if protocol_mode == "responses":
                # Responses API
                resp = await asyncio.wait_for(
                    client.responses.create(
                        model=model_id,
                        input=[{"role": m["role"], "content": m["content"]} for m in messages],
                        instructions=system or "You are a helpful assistant.",
                        max_output_tokens=max_tokens,
                    ),
                    timeout=timeout_sec,
                )
                return resp.output_text or ""
            else:
                # Chat Completions API (default)
                response = await asyncio.wait_for(
                    client.chat.completions.create(
                        model=model_id,
                        messages=[{"role": "system", "content": system}] + messages if system else messages,
                        max_tokens=max_tokens,
                        temperature=temperature,
                    ),
                    timeout=timeout_sec,
                )
                return response.choices[0].message.content or ""

    async def _stream_endpoint(
        self,
        ep: ApiEndpoint,
        model_id: str,
        messages: list[dict],
        system: str,
        max_tokens: int,
        temperature: float,
    ) -> AsyncGenerator[str, None]:
        """Stream from a single endpoint with client caching."""
        timeout_sec = ep.timeout_ms / 1000
        client = self._get_or_create_client(ep)

        if ep.protocol == "anthropic":
            stream = await asyncio.wait_for(
                client.messages.create(
                    model=model_id,
                    system=system or "You are a helpful assistant.",
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    stream=True,
                ),
                timeout=timeout_sec,
            )
            async for event in stream:
                if event.type == "content_block_delta":
                    yield event.delta.text
        else:
            # Determine protocol mode
            protocol_mode = ep.protocol_mode or "auto"
            if protocol_mode == "auto":
                stats = ep.stats_json or {}
                protocol_mode = stats.get("detected_protocol_mode", "completions")

            if protocol_mode == "responses":
                # Responses API streaming
                resp = await asyncio.wait_for(
                    client.responses.create(
                        model=model_id,
                        input=[{"role": m["role"], "content": m["content"]} for m in messages],
                        instructions=system or "You are a helpful assistant.",
                        max_output_tokens=max_tokens,
                        stream=True,
                    ),
                    timeout=timeout_sec,
                )
                async for event in resp:
                    if hasattr(event, 'delta') and hasattr(event.delta, 'text'):
                        yield event.delta.text
            else:
                # Chat Completions API streaming (default)
                stream = await asyncio.wait_for(
                    client.chat.completions.create(
                        model=model_id,
                        messages=[{"role": "system", "content": system}] + messages if system else messages,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        stream=True,
                    ),
                    timeout=timeout_sec,
                )
                async for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content

    async def _record_success(self, endpoint_id: int, db=None):
        """Record a successful request. Accepts optional db session for reuse."""
        async def _do_record(session):
            result = await session.execute(
                select(ApiEndpoint).where(ApiEndpoint.id == endpoint_id)
            )
            ep = result.scalar_one_or_none()
            if not ep:
                return
            stats = ep.stats_json or {}
            total = stats.get("total_requests", 0) + 1
            success = stats.get("success_count", 0) + 1
            ep.stats_json = {
                **stats,
                "total_requests": total,
                "success_count": success,
                "consecutive_errors": 0,
                "last_tested_at": datetime.now(timezone.utc).isoformat(),
            }
            if ep.status in ("degraded",):
                ep.status = "healthy"
            await session.commit()

        if db is not None:
            await _do_record(db)
        else:
            async with AsyncSessionLocal() as session:
                await _do_record(session)

    async def _record_failure(self, endpoint_id: int, error_msg: str, db=None):
        """Record a failed request, potentially degrading or freezing.
        Evicts cached client on auth-related failures. Accepts optional db session."""
        # Evict cached client on auth failures (401/403)
        error_lower = error_msg.lower()
        if "401" in error_lower or "403" in error_lower or "unauthorized" in error_lower or "invalid" in error_lower:
            if db is not None:
                result = await db.execute(
                    select(ApiEndpoint).where(ApiEndpoint.id == endpoint_id)
                )
                ep = result.scalar_one_or_none()
                if ep:
                    await self._evict_client(ep)
                    logger.info("Evicted cached client for endpoint %s due to auth failure", ep.name)
            else:
                async with AsyncSessionLocal() as session:
                    result = await session.execute(
                        select(ApiEndpoint).where(ApiEndpoint.id == endpoint_id)
                    )
                    ep = result.scalar_one_or_none()
                    if ep:
                        await self._evict_client(ep)

        async def _do_record(session):
            result = await session.execute(
                select(ApiEndpoint).where(ApiEndpoint.id == endpoint_id)
            )
            ep = result.scalar_one_or_none()
            if not ep:
                return
            stats = ep.stats_json or {}
            total = stats.get("total_requests", 0) + 1
            consec = stats.get("consecutive_errors", 0) + 1
            ep.stats_json = {
                **stats,
                "total_requests": total,
                "consecutive_errors": consec,
                "last_error": error_msg[:500],
                "last_tested_at": datetime.now(timezone.utc).isoformat(),
            }

            if consec >= self.CONSECUTIVE_ERROR_FREEZE:
                ep.status = "frozen"
                level = min(consec // self.CONSECUTIVE_ERROR_FREEZE - 1, len(self.FREEZE_LEVELS) - 1)
                ep.frozen_until = datetime.now(timezone.utc) + self.FREEZE_LEVELS[level]
                logger.warning("Endpoint %s frozen for %s (consecutive errors: %d)",
                             ep.name, self.FREEZE_LEVELS[level], consec)
            elif consec >= self.CONSECUTIVE_ERROR_DEGRADED:
                ep.status = "degraded"

            await session.commit()

        if db is not None:
            await _do_record(db)
        else:
            async with AsyncSessionLocal() as session:
                await _do_record(session)

    async def test_endpoint(self, ep: ApiEndpoint, model: str = "", protocol_mode: str = "completions") -> dict:
        """Test an endpoint's connectivity and latency."""
        test_model = model or (ep.supported_models[0] if ep.supported_models else "gpt-4o-mini")
        start = time.monotonic()
        try:
            result = await self._call_endpoint(
                ep, test_model,
                [{"role": "user", "content": "Hi, respond with one word."}],
                "", 10, 0.5,
            )
            latency = (time.monotonic() - start) * 1000
            return {
                "success": True,
                "latency_ms": round(latency),
                "response": result[:200],
                "model_used": test_model,
            }
        except Exception as e:
            latency = (time.monotonic() - start) * 1000
            return {
                "success": False,
                "latency_ms": round(latency),
                "error": str(e)[:500],
                "model_used": test_model,
            }

    async def get_all_models(self) -> list[str]:
        """Get all supported model IDs across all active endpoints."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ApiEndpoint).where(ApiEndpoint.is_active == True)
            )
            endpoints = result.scalars().all()
            models = set()
            for ep in endpoints:
                for m in (ep.supported_models or []):
                    models.add(m)
            return sorted(models)


api_router = ApiRouter()
