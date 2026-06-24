import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from app.core.database import get_db
from app.api.auth import get_current_user_dep
from app.core.deps import require_admin
from app.models.user import User
from app.models.system_settings import SystemSetting

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])

# Default settings that can be configured
DEFAULT_SETTINGS = {
    "llm_provider": "openai",
    "llm_model": "gpt-4o",
    "openai_api_key": "",
    "openai_base_url": "",
    "anthropic_api_key": "",
    "anthropic_base_url": "",
    "ollama_base_url": "http://localhost:11434",
    "llm_temperature": "0.7",
    "app_name": "知识库",
}


class SettingItem(BaseModel):
    key: str
    value: str


class SettingsResponse(BaseModel):
    settings: dict[str, str]


class SettingsUpdateRequest(BaseModel):
    settings: dict[str, str]


class TestLLMRequest(BaseModel):
    provider: str
    model: str
    api_key: str = ""
    base_url: str = ""


class TestLLMResponse(BaseModel):
    success: bool
    response: str = ""
    error: str = ""


@router.get("/system", response_model=SettingsResponse)
async def get_system_settings(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(SystemSetting))
    db_settings = {s.key: s.value for s in result.scalars().all()}

    # Merge with defaults (DB values override defaults)
    merged = {**DEFAULT_SETTINGS, **db_settings}
    return SettingsResponse(settings=merged)


@router.put("/system")
async def update_system_settings(
    data: SettingsUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    for key, value in data.settings.items():
        if key not in DEFAULT_SETTINGS:
            continue

        result = await db.execute(
            select(SystemSetting).where(SystemSetting.key == key)
        )
        setting = result.scalar_one_or_none()

        if setting:
            setting.value = value
        else:
            setting = SystemSetting(key=key, value=value)
            db.add(setting)

    await db.commit()

    # Invalidate LLM client cache so next request uses new config
    from app.services.llm_service import llm_service
    await llm_service.close()

    return {"message": "配置已更新"}


@router.get("/llm-config")
async def get_llm_config(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user_dep),
):
    """Return AI-related config for frontend proxy routes (non-admin)."""
    result = await db.execute(select(SystemSetting))
    db_settings = {s.key: s.value for s in result.scalars().all()}

    llm_keys = [
        "llm_provider", "llm_model", "openai_api_key", "openai_base_url",
        "anthropic_api_key", "anthropic_base_url", "ollama_base_url", "llm_temperature",
    ]
    config = {k: DEFAULT_SETTINGS.get(k, "") for k in llm_keys}
    config.update({k: v for k, v in db_settings.items() if k in llm_keys})

    # Mask API keys — only show last 4 chars for verification
    for key in ("openai_api_key", "anthropic_api_key"):
        val = config.get(key, "")
        if val and len(val) > 4:
            config[key] = val[:4] + "****" + val[-4:]
        elif val:
            config[key] = "****"

    return config


@router.get("/llm-internal")
async def get_llm_internal(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Internal endpoint for server-side AI proxy routes. Returns full unmasked keys."""
    result = await db.execute(select(SystemSetting))
    db_settings = {s.key: s.value for s in result.scalars().all()}

    llm_keys = [
        "llm_provider", "llm_model", "openai_api_key", "openai_base_url",
        "anthropic_api_key", "anthropic_base_url", "ollama_base_url", "llm_temperature",
    ]
    config = {k: DEFAULT_SETTINGS.get(k, "") for k in llm_keys}
    config.update({k: v for k, v in db_settings.items() if k in llm_keys})
    return config


@router.post("/test-llm", response_model=TestLLMResponse)
async def test_llm_connection(
    data: TestLLMRequest,
    _: User = Depends(require_admin),
):
    """Test LLM connection with given config without saving."""
    import asyncio
    client = None
    try:
        # OpenAI-compatible providers: openai, glm, qwen, deepseek, mimo, moonshot, siliconflow
        openai_compat = {"openai", "glm", "qwen", "deepseek", "mimo", "moonshot", "siliconflow"}

        if data.provider in openai_compat:
            if not data.api_key:
                return TestLLMResponse(success=False, error="API Key 未提供")
            from openai import AsyncOpenAI
            kwargs = {"api_key": data.api_key}
            if data.base_url:
                kwargs["base_url"] = data.base_url
            client = AsyncOpenAI(**kwargs)

        elif data.provider == "anthropic":
            if not data.api_key:
                return TestLLMResponse(success=False, error="Anthropic API Key 未提供")
            from anthropic import AsyncAnthropic
            kwargs = {"api_key": data.api_key}
            if data.base_url:
                kwargs["base_url"] = data.base_url
            client = AsyncAnthropic(**kwargs)

        elif data.provider == "ollama":
            base_url = data.base_url or "http://localhost:11434"
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key="ollama", base_url=f"{base_url}/v1")

        else:
            return TestLLMResponse(success=False, error=f"不支持的提供商: {data.provider}")

        # Send a minimal test request with 15s timeout
        async def _test():
            if data.provider in openai_compat or data.provider == "ollama":
                resp = await client.chat.completions.create(
                    model=data.model,
                    messages=[{"role": "user", "content": "Hello"}],
                    max_tokens=20,
                )
                return resp.choices[0].message.content or ""
            else:  # anthropic
                resp = await client.messages.create(
                    model=data.model,
                    system="You are a helpful assistant.",
                    messages=[{"role": "user", "content": "Hello"}],
                    max_tokens=20,
                )
                return resp.content[0].text

        result = await asyncio.wait_for(_test(), timeout=15.0)
        return TestLLMResponse(success=True, response=result[:200])

    except asyncio.TimeoutError:
        return TestLLMResponse(success=False, error="连接超时 (15秒)，请检查地址和网络")
    except Exception as e:
        logger.error("LLM test failed: %s", e)
        # Sanitize: don't leak API key fragments or internal details
        error_msg = str(e)
        if "api" in error_msg.lower() and "key" in error_msg.lower():
            error_msg = "API Key 无效或权限不足"
        elif "auth" in error_msg.lower() or "401" in error_msg:
            error_msg = "认证失败，请检查 API Key"
        elif "not found" in error_msg.lower() or "404" in error_msg:
            error_msg = "模型或端点不存在"
        else:
            error_msg = "连接失败，请检查配置"
        return TestLLMResponse(success=False, error=error_msg)
    finally:
        if client:
            try:
                await client.close()
            except Exception:
                pass


# ── Prompt management ──────────────────────────────────────────────


@router.get("/prompts")
async def get_prompts(
    _: User = Depends(require_admin),
):
    """List all prompts with current values and defaults (admin only)."""
    from app.services.prompt_registry import get_all_prompts
    prompts = await get_all_prompts()
    return {"prompts": prompts}


@router.put("/prompts")
async def update_prompts(
    data: dict,
    _: User = Depends(require_admin),
):
    """Update one or more prompt values (admin only)."""
    from app.services.prompt_registry import save_prompts
    updates = data.get("updates", {})
    count = await save_prompts(updates)
    return {"message": f"已更新 {count} 个提示词"}


@router.post("/prompts/reset")
async def reset_prompts_to_default(
    data: dict,
    _: User = Depends(require_admin),
):
    """Reset prompts to their default values (admin only)."""
    from app.services.prompt_registry import reset_prompts
    keys = data.get("keys", [])
    count = await reset_prompts(keys)
    return {"message": f"已重置 {count} 个提示词"}


@router.get("/prompts-internal")
async def get_prompts_internal(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Internal endpoint for server-side AI routes. Returns prompt values as flat dict."""
    from app.services.prompt_registry import PROMPT_DEFAULTS
    result = await db.execute(select(SystemSetting))
    db_settings = {s.key: s.value for s in result.scalars().all()}

    prompts = {}
    for key, meta in PROMPT_DEFAULTS.items():
        prompts[key] = db_settings.get(key, meta["default"])
    return prompts
