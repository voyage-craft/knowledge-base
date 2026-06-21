from typing import AsyncGenerator
from app.core.config import get_settings
import asyncio
import time
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

# Cache for LLM config with TTL
_config_cache: dict | None = None
_config_cache_time: float = 0
CONFIG_CACHE_TTL: int = 60  # seconds


# Default base URLs for OpenAI-compatible providers
PROVIDER_DEFAULT_BASE_URLS: dict[str, str] = {
    "glm": "https://open.bigmodel.cn/api/paas/v4",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "mimo": "https://api.xiaomi.com/v1",
    "moonshot": "https://api.moonshot.cn/v1",
    "siliconflow": "https://api.siliconflow.cn/v1",
}

# All OpenAI-compatible provider keys
OPENAI_COMPAT_PROVIDERS = {"openai", "glm", "qwen", "deepseek", "mimo", "moonshot", "siliconflow"}


class LLMService:
    """Unified LLM service supporting OpenAI-compatible, Anthropic, and Ollama providers.

    When API routing endpoints are configured, uses the smart router
    with failover and health tracking. Falls back to legacy single-provider
    mode when no endpoints exist.
    """

    def __init__(self):
        self._client = None
        self._active_provider: str | None = None
        self._active_model: str | None = None
        self._active_api_key: str | None = None
        self._lock = asyncio.Lock()

    async def _has_routing_endpoints(self) -> bool:
        """Check if any active API routing endpoints exist."""
        try:
            from sqlalchemy import select, func
            from app.core.database import AsyncSessionLocal
            from app.models.api_endpoint import ApiEndpoint
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(func.count()).select_from(ApiEndpoint).where(ApiEndpoint.is_active == True)
                )
                count = result.scalar()
                return count > 0
        except Exception:
            return False

    async def _load_config(self) -> dict:
        """Load LLM config from DB settings table with TTL cache."""
        global _config_cache, _config_cache_time

        # Return cached config if still valid
        if _config_cache and (time.time() - _config_cache_time) < CONFIG_CACHE_TTL:
            return _config_cache

        # Guard cache refresh with lock to prevent concurrent DB reads
        async with self._lock:
            # Double-check after acquiring lock
            if _config_cache and (time.time() - _config_cache_time) < CONFIG_CACHE_TTL:
                return _config_cache

            config = {
            "provider": settings.LLM_PROVIDER,
            "model": settings.LLM_MODEL,
            "openai_api_key": settings.OPENAI_API_KEY,
            "openai_base_url": "",
            "anthropic_api_key": settings.ANTHROPIC_API_KEY,
            "anthropic_base_url": "",
            "ollama_base_url": settings.OLLAMA_BASE_URL,
            "temperature": 0.7,
        }
        try:
            from sqlalchemy import select
            from app.core.database import AsyncSessionLocal
            from app.models.system_settings import SystemSetting

            async with AsyncSessionLocal() as session:
                result = await session.execute(select(SystemSetting))
                for s in result.scalars().all():
                    if s.key == "llm_provider" and s.value:
                        config["provider"] = s.value
                    elif s.key == "llm_model" and s.value:
                        config["model"] = s.value
                    elif s.key == "openai_api_key" and s.value:
                        config["openai_api_key"] = s.value
                    elif s.key == "openai_base_url" and s.value:
                        config["openai_base_url"] = s.value
                    elif s.key == "anthropic_api_key" and s.value:
                        config["anthropic_api_key"] = s.value
                    elif s.key == "anthropic_base_url" and s.value:
                        config["anthropic_base_url"] = s.value
                    elif s.key == "ollama_base_url" and s.value:
                        config["ollama_base_url"] = s.value
                    elif s.key == "llm_temperature" and s.value:
                        try:
                            config["temperature"] = float(s.value)
                        except ValueError:
                            pass
        except Exception as e:
            logger.debug("Could not load DB config (first run?): %s", e)

        # Update cache
        _config_cache = config
        _config_cache_time = time.time()

        return config

    def invalidate_config_cache(self):
        """Invalidate the config cache to force reload on next access."""
        global _config_cache, _config_cache_time
        _config_cache = None
        _config_cache_time = 0

    async def _get_client(self, config: dict):
        """Get or recreate the API client based on current config (thread-safe)."""
        async with self._lock:
            provider = config["provider"]
            model = config["model"]
            api_key = config.get(f"{provider}_api_key", "")

            # Reset client if provider, model, or API key changed
            if self._client and (
                self._active_provider != provider or
                self._active_model != model or
                self._active_api_key != api_key
            ):
                await self.close()

            if self._client:
                return self._client

            if provider in OPENAI_COMPAT_PROVIDERS:
                api_key = config.get("openai_api_key", "")
                if not api_key:
                    raise RuntimeError(f"{provider} API Key 未配置")
                from openai import AsyncOpenAI
                kwargs = {"api_key": api_key}
                base_url = config.get("openai_base_url", "") or PROVIDER_DEFAULT_BASE_URLS.get(provider, "")
                if base_url:
                    kwargs["base_url"] = base_url
                self._client = AsyncOpenAI(**kwargs)
            elif provider == "anthropic":
                api_key = config.get("anthropic_api_key", "")
                if not api_key:
                    raise RuntimeError("Anthropic API Key 未配置")
                from anthropic import AsyncAnthropic
                kwargs = {"api_key": api_key}
                base_url = config.get("anthropic_base_url", "")
                if base_url:
                    kwargs["base_url"] = base_url
                self._client = AsyncAnthropic(**kwargs)
            elif provider == "ollama":
                base_url = config.get("ollama_base_url", "http://localhost:11434")
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(
                    api_key="ollama",
                    base_url=f"{base_url}/v1",
                )
            else:
                raise RuntimeError(f"不支持的提供商: {provider}")

            self._active_provider = provider
            self._active_model = model
            self._active_api_key = api_key
            return self._client

    async def close(self):
        """Close the HTTP client, release connections, and invalidate config cache."""
        if self._client:
            try:
                await self._client.close()
            except Exception:
                pass
            self._client = None
            self._active_provider = None
            self._active_model = None
            self._active_api_key = None
        # Always invalidate config cache so next request reloads from DB
        self.invalidate_config_cache()

    async def generate(self, messages: list[dict], system: str = "", max_tokens: int = 4096) -> str:
        """Generate a complete response. Uses API router if endpoints are configured."""
        config = await self._load_config()
        model = config["model"]
        temperature = config.get("temperature", 0.7)

        # Try API routing first
        if await self._has_routing_endpoints():
            from app.services.api_router import api_router
            return await api_router.call_with_failover(
                model, messages, system, max_tokens, temperature
            )

        # Legacy fallback
        try:
            client = await self._get_client(config)
        except RuntimeError as e:
            logger.warning("LLM not configured: %s", e)
            return f"[LLM 未配置: {e}]"

        if not client:
            return "[LLM 提供商未配置]"

        provider = config["provider"]

        try:
            if provider in OPENAI_COMPAT_PROVIDERS or provider == "ollama":
                response = await client.chat.completions.create(
                    model=model,
                    messages=[{"role": "system", "content": system}] + messages if system else messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                return response.choices[0].message.content or ""

            elif provider == "anthropic":
                response = await client.messages.create(
                    model=model,
                    system=system or "You are a helpful assistant.",
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                return response.content[0].text

            return "[LLM 提供商未配置]"
        except Exception as e:
            logger.error("LLM generate error: %s", e)
            return f"[LLM 错误: {e}]"

    async def stream(self, messages: list[dict], system: str = "", max_tokens: int = 4096) -> AsyncGenerator[str, None]:
        """Stream response tokens. Uses API router if endpoints are configured."""
        config = await self._load_config()
        model = config["model"]
        temperature = config.get("temperature", 0.7)

        # Try API routing first
        if await self._has_routing_endpoints():
            from app.services.api_router import api_router
            async for token in api_router.stream_with_failover(
                model, messages, system, max_tokens, temperature
            ):
                yield token
            return

        # Legacy fallback
        try:
            client = await self._get_client(config)
        except RuntimeError as e:
            yield f"[LLM 未配置: {e}]"
            return

        if not client:
            yield "[LLM 提供商未配置]"
            return

        provider = config["provider"]

        try:
            if provider in OPENAI_COMPAT_PROVIDERS or provider == "ollama":
                stream = await client.chat.completions.create(
                    model=model,
                    messages=[{"role": "system", "content": system}] + messages if system else messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    stream=True,
                )
                async for chunk in stream:
                    if chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content

            elif provider == "anthropic":
                stream = await client.messages.create(
                    model=model,
                    system=system or "You are a helpful assistant.",
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    stream=True,
                )
                async for event in stream:
                    if event.type == "content_block_delta":
                        yield event.delta.text
        except Exception as e:
            logger.error("LLM stream error: %s", e)
            yield f"\n\n[流式传输错误: {e}]"


llm_service = LLMService()
