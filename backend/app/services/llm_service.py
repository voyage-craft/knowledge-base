from typing import AsyncGenerator
from app.core.config import get_settings
import asyncio
import time
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

# Cache for LLM config with TTL - using lock for thread safety
_config_cache: dict | None = None
_config_cache_time: float = 0
_config_cache_lock: asyncio.Lock = asyncio.Lock()
CONFIG_CACHE_TTL: int = 60  # seconds

# Cache for routing endpoints check with TTL
_routing_check_cache: bool | None = None
_routing_check_time: float = 0
_routing_check_lock: asyncio.Lock = asyncio.Lock()
ROUTING_CHECK_TTL: int = 30  # seconds

# Default request timeout in seconds
DEFAULT_REQUEST_TIMEOUT: int = 30

# Max retry attempts for transient errors
MAX_RETRIES: int = 3
RETRY_DELAY: float = 1.0  # seconds


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


class LLMError(Exception):
    """Base exception for LLM service errors."""
    pass


class LLMNotConfiguredError(LLMError):
    """Raised when LLM provider is not configured."""
    pass


class LLMProviderError(LLMError):
    """Raised when LLM provider returns an error."""
    pass


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
        self._active_base_url: str | None = None
        self._lock = asyncio.Lock()

    async def _has_routing_endpoints(self) -> bool:
        """Check if any active API routing endpoints exist (cached with 30s TTL)."""
        global _routing_check_cache, _routing_check_time

        # Fast path - return cached value if valid
        if _routing_check_cache is not None and (time.time() - _routing_check_time) < ROUTING_CHECK_TTL:
            return _routing_check_cache

        # Slow path - acquire lock and refresh cache
        async with _routing_check_lock:
            # Double-check after acquiring lock
            if _routing_check_cache is not None and (time.time() - _routing_check_time) < ROUTING_CHECK_TTL:
                return _routing_check_cache

            try:
                from sqlalchemy import select, func
                from app.core.database import AsyncSessionLocal
                from app.models.api_endpoint import ApiEndpoint
                async with AsyncSessionLocal() as session:
                    result = await session.execute(
                        select(func.count()).select_from(ApiEndpoint).where(ApiEndpoint.is_active == True)
                    )
                    count = result.scalar()
                    has_endpoints = count > 0
                    _routing_check_cache = has_endpoints
                    _routing_check_time = time.time()
                    return has_endpoints
            except Exception as e:
                logger.warning("Failed to check routing endpoints: %s", e)
                _routing_check_cache = False
                _routing_check_time = time.time()
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

            # Resolve effective base_url
            if provider in OPENAI_COMPAT_PROVIDERS:
                base_url = config.get("openai_base_url", "") or PROVIDER_DEFAULT_BASE_URLS.get(provider, "")
            elif provider == "anthropic":
                base_url = config.get("anthropic_base_url", "")
            elif provider == "ollama":
                base_url = config.get("ollama_base_url", "http://localhost:11434")
            else:
                base_url = ""

            # Reset client if provider, model, API key, or base_url changed
            if self._client and (
                self._active_provider != provider or
                self._active_model != model or
                self._active_api_key != api_key or
                self._active_base_url != base_url
            ):
                await self.close()

            if self._client:
                return self._client

            if provider in OPENAI_COMPAT_PROVIDERS:
                api_key = config.get("openai_api_key", "")
                if not api_key:
                    raise LLMNotConfiguredError(f"{provider} API Key 未配置")
                from openai import AsyncOpenAI
                kwargs = {"api_key": api_key, "timeout": DEFAULT_REQUEST_TIMEOUT}
                if base_url:
                    kwargs["base_url"] = base_url
                self._client = AsyncOpenAI(**kwargs)
            elif provider == "anthropic":
                api_key = config.get("anthropic_api_key", "")
                if not api_key:
                    raise LLMNotConfiguredError("Anthropic API Key 未配置")
                from anthropic import AsyncAnthropic
                kwargs = {"api_key": api_key, "timeout": DEFAULT_REQUEST_TIMEOUT}
                if base_url:
                    kwargs["base_url"] = base_url
                self._client = AsyncAnthropic(**kwargs)
            elif provider == "ollama":
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(
                    api_key="ollama",
                    base_url=f"{base_url}/v1",
                    timeout=DEFAULT_REQUEST_TIMEOUT,
                )
            else:
                raise LLMNotConfiguredError(f"不支持的提供商: {provider}")

            self._active_provider = provider
            self._active_model = model
            self._active_api_key = api_key
            self._active_base_url = base_url
            return self._client

    async def close(self):
        """Close the HTTP client, release connections, and invalidate all caches."""
        if self._client:
            try:
                await self._client.close()
            except Exception:
                pass
            self._client = None
            self._active_provider = None
            self._active_model = None
            self._active_api_key = None
            self._active_base_url = None
        # Always invalidate caches so next request reloads from DB
        self.invalidate_config_cache()
        global _routing_check_cache, _routing_check_time
        _routing_check_cache = None
        _routing_check_time = 0

    async def generate(self, messages: list[dict], system: str = "", max_tokens: int = 4096) -> str:
        """Generate a complete response with retry logic.

        Uses API router if endpoints are configured, otherwise falls back to legacy mode.

        Raises:
            LLMNotConfiguredError: if LLM provider is not configured
            LLMProviderError: if the provider returns an error after retries
        """
        config = await self._load_config()
        model = config["model"]
        temperature = config.get("temperature", 0.7)

        # Try API routing first
        if await self._has_routing_endpoints():
            from app.services.api_router import api_router
            return await api_router.call_with_failover(
                model, messages, system, max_tokens, temperature
            )

        # Legacy fallback with retry
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                client = await self._get_client(config)
                if not client:
                    raise LLMNotConfiguredError("LLM 提供商未配置")

                provider = config["provider"]

                if provider in OPENAI_COMPAT_PROVIDERS or provider == "ollama":
                    response = await asyncio.wait_for(
                        client.chat.completions.create(
                            model=model,
                            messages=[{"role": "system", "content": system}] + messages if system else messages,
                            max_tokens=max_tokens,
                            temperature=temperature,
                        ),
                        timeout=DEFAULT_REQUEST_TIMEOUT,
                    )
                    return response.choices[0].message.content or ""

                elif provider == "anthropic":
                    response = await asyncio.wait_for(
                        client.messages.create(
                            model=model,
                            system=system or "You are a helpful assistant.",
                            messages=messages,
                            max_tokens=max_tokens,
                            temperature=temperature,
                        ),
                        timeout=DEFAULT_REQUEST_TIMEOUT,
                    )
                    return response.content[0].text

                raise LLMNotConfiguredError("LLM 提供商未配置")

            except (LLMNotConfiguredError, LLMError):
                raise
            except asyncio.TimeoutError:
                last_error = f"LLM 请求超时（{DEFAULT_REQUEST_TIMEOUT}s）"
                logger.warning("LLM request timeout on attempt %d/%d", attempt + 1, MAX_RETRIES)
            except Exception as e:
                last_error = str(e)
                logger.warning("LLM generate error on attempt %d/%d: %s", attempt + 1, MAX_RETRIES, e)

            # Wait before retry (exponential backoff)
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY * (2 ** attempt))

        raise LLMProviderError(f"LLM 请求失败（已重试{MAX_RETRIES}次）: {last_error}")

    async def stream(self, messages: list[dict], system: str = "", max_tokens: int = 4096) -> AsyncGenerator[str, None]:
        """Stream response tokens with retry logic.

        Uses API router if endpoints are configured, otherwise falls back to legacy mode.

        Raises:
            LLMNotConfiguredError: if LLM provider is not configured
            LLMProviderError: if the provider returns an error
        """
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

        # Legacy fallback with retry
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                client = await self._get_client(config)
                if not client:
                    raise LLMNotConfiguredError("LLM 提供商未配置")

                provider = config["provider"]

                if provider in OPENAI_COMPAT_PROVIDERS or provider == "ollama":
                    stream = await asyncio.wait_for(
                        client.chat.completions.create(
                            model=model,
                            messages=[{"role": "system", "content": system}] + messages if system else messages,
                            max_tokens=max_tokens,
                            temperature=temperature,
                            stream=True,
                        ),
                        timeout=DEFAULT_REQUEST_TIMEOUT,
                    )
                    async for chunk in stream:
                        if chunk.choices[0].delta.content:
                            yield chunk.choices[0].delta.content
                    return  # Success - exit retry loop

                elif provider == "anthropic":
                    stream = await asyncio.wait_for(
                        client.messages.create(
                            model=model,
                            system=system or "You are a helpful assistant.",
                            messages=messages,
                            max_tokens=max_tokens,
                            temperature=temperature,
                            stream=True,
                        ),
                        timeout=DEFAULT_REQUEST_TIMEOUT,
                    )
                    async for event in stream:
                        if event.type == "content_block_delta":
                            yield event.delta.text
                    return  # Success - exit retry loop

                raise LLMNotConfiguredError("LLM 提供商未配置")

            except (LLMNotConfiguredError, LLMError):
                raise
            except asyncio.TimeoutError:
                last_error = f"LLM 流式请求超时（{DEFAULT_REQUEST_TIMEOUT}s）"
                logger.warning("LLM stream timeout on attempt %d/%d", attempt + 1, MAX_RETRIES)
            except Exception as e:
                last_error = str(e)
                logger.warning("LLM stream error on attempt %d/%d: %s", attempt + 1, MAX_RETRIES, e)

            # Wait before retry
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY * (2 ** attempt))

        raise LLMProviderError(f"LLM 流式请求失败（已重试{MAX_RETRIES}次）: {last_error}")


llm_service = LLMService()
