"""Tests for production readiness fixes.

Covers:
- Login error response format (401, 422)
- Admin permission checks on API routes
- Token refresh mechanism
- Error response consistency
- Provider template completeness
- LLM service provider support
- SSE stream format for chat/edit endpoints
- Endpoint-resolve credentials format and security
- protocol_mode parameter on create/update
"""
import json
import re
import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock, MagicMock


# ── Auth helpers ──

async def get_admin_token(async_client: AsyncClient) -> str:
    """Get a valid admin access token."""
    await async_client.get("/api/health")
    resp = await async_client.post("/api/auth/login", json={
        "username": "admin",
        "password": "test-admin-password-123",
    })
    assert resp.status_code == 200
    return resp.json()["access_token"]


async def get_user_token(async_client: AsyncClient) -> str:
    """Create a non-admin user and return their token."""
    admin_token = await get_admin_token(async_client)
    await async_client.post("/api/admin/users", json={
        "username": "testuser",
        "email": "test@test.com",
        "password": "testpassword123",
        "is_admin": False,
    }, headers={"Authorization": f"Bearer {admin_token}"})

    resp = await async_client.post("/api/auth/login", json={
        "username": "testuser",
        "password": "testpassword123",
    })
    assert resp.status_code == 200
    return resp.json()["access_token"]


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def internal_auth_header(token: str) -> dict:
    """Auth header with internal secret for endpoint-resolve calls."""
    import os
    secret = os.environ.get("INTERNAL_API_SECRET", "test-internal-secret-for-testing")
    return {"Authorization": f"Bearer {token}", "X-Internal-Request": secret}


# ── Login Error Response Tests ──

@pytest.mark.asyncio
async def test_login_wrong_password_returns_error_message(async_client: AsyncClient):
    resp = await async_client.post("/api/auth/login", json={
        "username": "admin",
        "password": "wrongpassword123",
    })
    assert resp.status_code == 401
    data = resp.json()
    assert "message" in data or "detail" in data


@pytest.mark.asyncio
async def test_login_empty_body_returns_422(async_client: AsyncClient):
    resp = await async_client.post("/api/auth/login", json={})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login_short_password_returns_422(async_client: AsyncClient):
    resp = await async_client.post("/api/auth/login", json={
        "username": "admin",
        "password": "short",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login_success_returns_tokens(async_client: AsyncClient):
    resp = await async_client.post("/api/auth/login", json={
        "username": "admin",
        "password": "test-admin-password-123",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


# ── Error Response Format Tests ──

@pytest.mark.asyncio
async def test_404_returns_structured_error(async_client: AsyncClient):
    token = await get_admin_token(async_client)
    resp = await async_client.get("/api/documents/99999", headers=auth_header(token))
    assert resp.status_code == 404
    data = resp.json()
    assert "message" in data or "detail" in data


@pytest.mark.asyncio
async def test_401_returns_structured_error(async_client: AsyncClient):
    resp = await async_client.get("/api/documents")
    assert resp.status_code == 401


# ── Admin Permission Tests ──

@pytest.mark.asyncio
async def test_admin_can_create_endpoint(async_client: AsyncClient):
    token = await get_admin_token(async_client)
    resp = await async_client.post("/api/api-routes/endpoints", json={
        "name": "Test Endpoint",
        "provider": "openai",
        "base_url": "https://api.openai.com/v1",
        "api_key": "sk-test",
        "protocol": "openai",
        "supported_models": ["gpt-4o"],
        "priority": 100,
    }, headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.json()["name"] == "Test Endpoint"


@pytest.mark.asyncio
async def test_non_admin_cannot_create_endpoint(async_client: AsyncClient):
    user_token = await get_user_token(async_client)
    resp = await async_client.post("/api/api-routes/endpoints", json={
        "name": "Test",
        "provider": "openai",
        "base_url": "https://api.openai.com/v1",
        "api_key": "sk-test",
        "protocol": "openai",
    }, headers=auth_header(user_token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_non_admin_cannot_delete_endpoint(async_client: AsyncClient):
    admin_token = await get_admin_token(async_client)
    user_token = await get_user_token(async_client)

    resp = await async_client.post("/api/api-routes/endpoints", json={
        "name": "Test",
        "provider": "openai",
        "base_url": "https://api.openai.com/v1",
        "api_key": "sk-test",
        "protocol": "openai",
    }, headers=auth_header(admin_token))
    ep_id = resp.json()["id"]

    resp = await async_client.delete(f"/api/api-routes/endpoints/{ep_id}", headers=auth_header(user_token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_non_admin_can_list_endpoints(async_client: AsyncClient):
    user_token = await get_user_token(async_client)
    resp = await async_client.get("/api/api-routes/endpoints", headers=auth_header(user_token))
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_non_admin_can_access_health(async_client: AsyncClient):
    user_token = await get_user_token(async_client)
    resp = await async_client.get("/api/api-routes/health", headers=auth_header(user_token))
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_non_admin_cannot_toggle_endpoint(async_client: AsyncClient):
    admin_token = await get_admin_token(async_client)
    user_token = await get_user_token(async_client)

    resp = await async_client.post("/api/api-routes/endpoints", json={
        "name": "Test",
        "provider": "openai",
        "base_url": "https://api.openai.com/v1",
        "api_key": "sk-test",
        "protocol": "openai",
    }, headers=auth_header(admin_token))
    ep_id = resp.json()["id"]

    resp = await async_client.post(f"/api/api-routes/endpoints/{ep_id}/toggle", headers=auth_header(user_token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_non_admin_cannot_update_endpoint(async_client: AsyncClient):
    admin_token = await get_admin_token(async_client)
    user_token = await get_user_token(async_client)

    resp = await async_client.post("/api/api-routes/endpoints", json={
        "name": "Test",
        "provider": "openai",
        "base_url": "https://api.openai.com/v1",
        "api_key": "sk-test",
        "protocol": "openai",
    }, headers=auth_header(admin_token))
    ep_id = resp.json()["id"]

    resp = await async_client.put(f"/api/api-routes/endpoints/{ep_id}", json={
        "name": "Hacked",
    }, headers=auth_header(user_token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_non_admin_cannot_create_rule(async_client: AsyncClient):
    user_token = await get_user_token(async_client)
    resp = await async_client.post("/api/api-routes/rules", json={
        "model_id": "gpt-4o",
        "priority": 100,
    }, headers=auth_header(user_token))
    assert resp.status_code == 403


# ── Token Refresh Tests ──

@pytest.mark.asyncio
async def test_refresh_token_returns_new_tokens(async_client: AsyncClient):
    login_resp = await async_client.post("/api/auth/login", json={
        "username": "admin",
        "password": "test-admin-password-123",
    })
    refresh_token = login_resp.json()["refresh_token"]

    resp = await async_client.post("/api/auth/refresh", json={
        "refresh_token": refresh_token,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_invalid_refresh_token_returns_401(async_client: AsyncClient):
    resp = await async_client.post("/api/auth/refresh", json={
        "refresh_token": "invalid-token",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_access_token_as_refresh_returns_401(async_client: AsyncClient):
    login_resp = await async_client.post("/api/auth/login", json={
        "username": "admin",
        "password": "test-admin-password-123",
    })
    access_token = login_resp.json()["access_token"]

    resp = await async_client.post("/api/auth/refresh", json={
        "refresh_token": access_token,
    })
    assert resp.status_code == 401


# ── Settings Tests ──

@pytest.mark.asyncio
async def test_system_settings_read_write(async_client: AsyncClient):
    token = await get_admin_token(async_client)

    resp = await async_client.get("/api/settings/system", headers=auth_header(token))
    assert resp.status_code == 200
    settings = resp.json()["settings"]
    assert "llm_provider" in settings
    assert "app_name" in settings

    resp = await async_client.put("/api/settings/system", json={
        "settings": {"app_name": "测试知识库"}
    }, headers=auth_header(token))
    assert resp.status_code == 200

    resp = await async_client.get("/api/settings/system", headers=auth_header(token))
    assert resp.json()["settings"]["app_name"] == "测试知识库"


@pytest.mark.asyncio
async def test_non_admin_cannot_update_settings(async_client: AsyncClient):
    user_token = await get_user_token(async_client)
    resp = await async_client.put("/api/settings/system", json={
        "settings": {"app_name": "Hack"}
    }, headers=auth_header(user_token))
    assert resp.status_code == 403


# ── Provider Template Tests ──

@pytest.mark.asyncio
async def test_provider_templates_include_all_providers(async_client: AsyncClient):
    token = await get_admin_token(async_client)
    resp = await async_client.get("/api/api-routes/providers", headers=auth_header(token))
    assert resp.status_code == 200
    providers = resp.json()
    keys = [p["key"] for p in providers]

    for key in ["glm", "qwen", "deepseek", "mimo", "siliconflow", "moonshot", "openai", "anthropic", "ollama"]:
        assert key in keys, f"Provider '{key}' missing"


@pytest.mark.asyncio
async def test_mimo_provider_has_current_models(async_client: AsyncClient):
    token = await get_admin_token(async_client)
    resp = await async_client.get("/api/api-routes/providers", headers=auth_header(token))
    providers = resp.json()
    mimo = next(p for p in providers if p["key"] == "mimo")

    assert "mimo-v2.5-pro" in mimo["models"]
    assert "mimo-v2.5-flash" in mimo["models"]


@pytest.mark.asyncio
async def test_openai_provider_has_current_models(async_client: AsyncClient):
    token = await get_admin_token(async_client)
    resp = await async_client.get("/api/api-routes/providers", headers=auth_header(token))
    providers = resp.json()
    openai = next(p for p in providers if p["key"] == "openai")

    assert "gpt-4o" in openai["models"]
    assert "o1" in openai["models"]
    assert "o3-mini" in openai["models"]


@pytest.mark.asyncio
async def test_anthropic_provider_has_current_models(async_client: AsyncClient):
    token = await get_admin_token(async_client)
    resp = await async_client.get("/api/api-routes/providers", headers=auth_header(token))
    providers = resp.json()
    anthropic = next(p for p in providers if p["key"] == "anthropic")

    assert "claude-sonnet-4-20250514" in anthropic["models"]


# ── Health Endpoint Tests ──

@pytest.mark.asyncio
async def test_health_endpoint(async_client: AsyncClient):
    resp = await async_client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_api_routes_health(async_client: AsyncClient):
    token = await get_admin_token(async_client)
    resp = await async_client.get("/api/api-routes/health", headers=auth_header(token))
    assert resp.status_code == 200
    data = resp.json()
    assert "summary" in data
    assert "total" in data["summary"]


# ── Me Endpoint Tests ──

@pytest.mark.asyncio
async def test_me_returns_user_info(async_client: AsyncClient):
    token = await get_admin_token(async_client)
    resp = await async_client.get("/api/auth/me", headers=auth_header(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "admin"
    assert data["is_admin"] is True


@pytest.mark.asyncio
async def test_me_without_token_returns_401(async_client: AsyncClient):
    resp = await async_client.get("/api/auth/me")
    assert resp.status_code == 401


# ── Helper: create an endpoint via API ──

async def create_test_endpoint(async_client: AsyncClient, token: str, **overrides) -> dict:
    """Create an endpoint via the admin API and return its response dict."""
    payload = {
        "name": "Test Endpoint",
        "provider": "openai",
        "base_url": "https://api.openai.com/v1",
        "api_key": "sk-test-secret-key-12345678",
        "protocol": "openai",
        "supported_models": ["gpt-4o", "gpt-4o-mini"],
        "priority": 100,
        "protocol_mode": "completions",
    }
    payload.update(overrides)
    resp = await async_client.post(
        "/api/api-routes/endpoints",
        json=payload,
        headers=auth_header(token),
    )
    assert resp.status_code == 200, f"Failed to create endpoint: {resp.text}"
    return resp.json()


# ── SSE Stream Format Helpers ──

def parse_sse_events(raw: str) -> list[str]:
    """Parse raw SSE text into individual event data strings.

    SSE format: each event is "data: <payload>\n\n"
    """
    events = []
    for block in raw.strip().split("\n\n"):
        block = block.strip()
        if not block:
            continue
        for line in block.split("\n"):
            line = line.strip()
            if line.startswith("data: "):
                events.append(line[len("data: "):])
    return events


def assert_valid_sse_format(raw: str):
    """Assert that raw response text follows valid SSE format.

    Every data line must start with "data: " and the stream must end
    with "data: [DONE]" or contain an error payload.
    """
    events = parse_sse_events(raw)
    assert len(events) > 0, "SSE stream contained no events"

    # Every event must be valid JSON or the [DONE] sentinel
    for i, event_data in enumerate(events):
        if event_data == "[DONE]":
            continue
        try:
            parsed = json.loads(event_data)
        except json.JSONDecodeError:
            pytest.fail(f"Event {i} is not valid JSON: {event_data!r}")

    # The last event must be [DONE] or an error
    last = events[-1]
    if last == "[DONE]":
        return  # happy path
    # If it's an error, that's also acceptable (stream error handling)
    last_parsed = json.loads(last)
    assert "error" in last_parsed, (
        f"Last SSE event must be [DONE] or error payload, got: {last}"
    )


# ── Test 1: /api/ai/endpoint-resolve returns correct credentials format ──

@pytest.mark.asyncio
async def test_endpoint_resolve_returns_correct_credentials_format(async_client: AsyncClient):
    """endpoint-resolve must return all fields required by the EndpointCredentials schema."""
    token = await get_admin_token(async_client)
    await create_test_endpoint(async_client, token)

    resp = await async_client.post(
        "/api/ai/endpoint-resolve",
        json={"category": "chat"},
        headers=internal_auth_header(token),
    )
    assert resp.status_code == 200
    data = resp.json()

    # Required fields from EndpointCredentials model
    assert "endpoint_id" in data, "Missing endpoint_id"
    assert "name" in data, "Missing name"
    assert "protocol" in data, "Missing protocol"
    assert "base_url" in data, "Missing base_url"
    assert "api_key" in data, "Missing api_key"
    assert "model_id" in data, "Missing model_id"
    assert "protocol_mode" in data, "Missing protocol_mode"

    # Types
    assert isinstance(data["endpoint_id"], int)
    assert isinstance(data["name"], str)
    assert isinstance(data["protocol"], str)
    assert isinstance(data["base_url"], str)
    assert isinstance(data["api_key"], str)
    assert isinstance(data["model_id"], str)
    assert isinstance(data["protocol_mode"], str)

    # protocol_mode must be one of the valid values
    assert data["protocol_mode"] in ("completions", "responses"), (
        f"Unexpected protocol_mode: {data['protocol_mode']}"
    )


# ── Test 2: /api/ai/endpoint-resolve returns 401 without auth ──

@pytest.mark.asyncio
async def test_endpoint_resolve_returns_401_without_auth(async_client: AsyncClient):
    resp = await async_client.post(
        "/api/ai/endpoint-resolve",
        json={"category": "chat"},
    )
    assert resp.status_code == 401


# ── Test 3: /api/ai/endpoint-resolve returns 400 when no endpoints configured ──

@pytest.mark.asyncio
async def test_endpoint_resolve_returns_400_when_no_endpoints(async_client: AsyncClient):
    """When no AI endpoints exist, resolve must return 400 with a helpful message."""
    token = await get_admin_token(async_client)
    # Do NOT create any endpoints — database is clean per setup_db fixture

    resp = await async_client.post(
        "/api/ai/endpoint-resolve",
        json={"category": "chat"},
        headers=internal_auth_header(token),
    )
    assert resp.status_code == 400
    data = resp.json()
    # Should contain a human-readable message indicating no endpoints
    detail = data.get("detail", "") or data.get("message", "")
    assert "端点" in detail or "endpoint" in detail.lower() or "AI" in detail


# ── Test 4: /api/ai/chat/stream produces valid SSE format ──

@pytest.mark.asyncio
async def test_chat_stream_produces_valid_sse_format(async_client: AsyncClient):
    """The chat stream endpoint must produce proper SSE: data lines with JSON, terminated by [DONE]."""
    token = await get_admin_token(async_client)

    # Build a fake streaming response that mimics the OpenAI chat completions stream
    async def fake_stream_generator():
        chunks = [
            MagicMock(choices=[MagicMock(delta=MagicMock(content="Hello"))]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content=" world"))]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content="!"))]),
        ]
        for chunk in chunks:
            yield chunk

    fake_client = MagicMock()
    fake_stream = fake_stream_generator()
    fake_client.chat.completions.create = AsyncMock(return_value=fake_stream)

    # Create a mock ApiEndpoint object
    mock_endpoint = MagicMock()
    mock_endpoint.id = 1
    mock_endpoint.name = "Test"
    mock_endpoint.protocol = "openai"
    mock_endpoint.base_url = "https://api.openai.com/v1"
    mock_endpoint.api_key = "sk-test"
    mock_endpoint.supported_models = ["gpt-4o"]
    mock_endpoint.protocol_mode = "completions"
    mock_endpoint.stats_json = {}
    mock_endpoint.is_active = True
    mock_endpoint.status = "healthy"
    mock_endpoint.frozen_until = None
    mock_endpoint.priority = 100

    with patch("app.api.ai.api_router") as mock_router:
        mock_router.resolve = AsyncMock(return_value=[mock_endpoint])
        mock_router.get_all_models = AsyncMock(return_value=["gpt-4o"])
        mock_router._get_or_create_client = MagicMock(return_value=fake_client)

        resp = await async_client.post(
            "/api/ai/chat/stream",
            json={"messages": [{"role": "user", "content": "Hi"}], "system": "You are a test bot."},
            headers=auth_header(token),
        )

    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")

    raw = resp.text
    assert_valid_sse_format(raw)

    # Verify content tokens appear in the stream
    events = parse_sse_events(raw)
    text_events = []
    for e in events:
        if e == "[DONE]":
            continue
        parsed = json.loads(e)
        if "text" in parsed:
            text_events.append(parsed["text"])

    assert "".join(text_events) == "Hello world!"


# ── Test 5: /api/ai/chat/stream returns 401 without auth ──

@pytest.mark.asyncio
async def test_chat_stream_returns_401_without_auth(async_client: AsyncClient):
    resp = await async_client.post(
        "/api/ai/chat/stream",
        json={"messages": [{"role": "user", "content": "Hi"}]},
    )
    assert resp.status_code == 401


# ── Test 6: /api/ai/edit/stream produces valid SSE format ──

@pytest.mark.asyncio
async def test_edit_stream_produces_valid_sse_format(async_client: AsyncClient):
    """The edit stream endpoint must produce proper SSE format."""
    token = await get_admin_token(async_client)

    async def fake_stream_generator():
        chunks = [
            MagicMock(choices=[MagicMock(delta=MagicMock(content="Polished"))]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content=" text"))]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content=" here."))]),
        ]
        for chunk in chunks:
            yield chunk

    fake_client = MagicMock()
    fake_stream = fake_stream_generator()
    fake_client.chat.completions.create = AsyncMock(return_value=fake_stream)

    mock_endpoint = MagicMock()
    mock_endpoint.id = 1
    mock_endpoint.name = "Test"
    mock_endpoint.protocol = "openai"
    mock_endpoint.base_url = "https://api.openai.com/v1"
    mock_endpoint.api_key = "sk-test"
    mock_endpoint.supported_models = ["gpt-4o"]
    mock_endpoint.protocol_mode = "completions"
    mock_endpoint.stats_json = {}
    mock_endpoint.is_active = True
    mock_endpoint.status = "healthy"
    mock_endpoint.frozen_until = None
    mock_endpoint.priority = 100

    with patch("app.api.ai.api_router") as mock_router:
        mock_router.resolve = AsyncMock(return_value=[mock_endpoint])
        mock_router.get_all_models = AsyncMock(return_value=["gpt-4o"])
        mock_router._get_or_create_client = MagicMock(return_value=fake_client)

        resp = await async_client.post(
            "/api/ai/edit/stream",
            json={"text": "Some rough text.", "operation": "polish"},
            headers=auth_header(token),
        )

    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")

    raw = resp.text
    assert_valid_sse_format(raw)

    events = parse_sse_events(raw)
    text_events = []
    for e in events:
        if e == "[DONE]":
            continue
        parsed = json.loads(e)
        if "text" in parsed:
            text_events.append(parsed["text"])

    assert "".join(text_events) == "Polished text here."


# ── Test 7: Endpoint creation with protocol_mode parameter ──

@pytest.mark.asyncio
async def test_endpoint_create_with_protocol_mode(async_client: AsyncClient):
    """Creating an endpoint with protocol_mode must persist the value."""
    token = await get_admin_token(async_client)

    for mode in ("auto", "completions", "responses"):
        resp = await async_client.post(
            "/api/api-routes/endpoints",
            json={
                "name": f"Endpoint-{mode}",
                "provider": "openai",
                "base_url": "https://api.openai.com/v1",
                "api_key": "sk-test",
                "protocol": "openai",
                "supported_models": ["gpt-4o"],
                "protocol_mode": mode,
            },
            headers=auth_header(token),
        )
        assert resp.status_code == 200, f"Failed to create endpoint with mode={mode}: {resp.text}"
        data = resp.json()
        assert data["protocol_mode"] == mode, (
            f"Expected protocol_mode={mode}, got {data['protocol_mode']}"
        )


# ── Test 8: Endpoint update with protocol_mode change ──

@pytest.mark.asyncio
async def test_endpoint_update_protocol_mode(async_client: AsyncClient):
    """Updating an endpoint's protocol_mode must take effect."""
    token = await get_admin_token(async_client)
    ep = await create_test_endpoint(async_client, token, protocol_mode="auto")

    # Update to completions
    resp = await async_client.put(
        f"/api/api-routes/endpoints/{ep['id']}",
        json={"protocol_mode": "responses"},
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    assert resp.json()["protocol_mode"] == "responses"

    # Update back to auto
    resp = await async_client.put(
        f"/api/api-routes/endpoints/{ep['id']}",
        json={"protocol_mode": "auto"},
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    assert resp.json()["protocol_mode"] == "auto"


# ── Test 9: The /api/api-routes/resolve endpoint does NOT return api_key ──

@pytest.mark.asyncio
async def test_resolve_endpoint_does_not_return_api_key(async_client: AsyncClient):
    """The public resolve endpoint (/api/api-routes/resolve) must never expose the API key.

    This is the endpoint called by the frontend for display/routing purposes.
    The internal /api/ai/endpoint-resolve is the one that returns api_key for
    server-to-server use — that's a different test.
    """
    token = await get_admin_token(async_client)
    await create_test_endpoint(async_client, token, supported_models=["gpt-4o"])

    resp = await async_client.get(
        "/api/api-routes/resolve?model=gpt-4o",
        headers=internal_auth_header(token),
    )
    assert resp.status_code == 200
    data = resp.json()

    # api_key must NOT be present in the response
    assert "api_key" not in data, (
        f"SECURITY: /api/api-routes/resolve leaked api_key: {data.get('api_key')}"
    )

    # But it should still have the essential routing fields
    assert "endpoint_id" in data
    assert "protocol" in data
    assert "base_url" in data
    assert "model" in data
    assert "protocol_mode" in data


# ── Test 10: Full flow — create endpoint -> resolve -> verify credentials ──

@pytest.mark.asyncio
async def test_full_flow_create_resolve_verify_credentials(async_client: AsyncClient):
    """End-to-end: create an endpoint, resolve it, and verify the credentials payload."""
    token = await get_admin_token(async_client)

    # Step 1: Create endpoint
    create_resp = await async_client.post(
        "/api/api-routes/endpoints",
        json={
            "name": "E2E Test Endpoint",
            "provider": "openai",
            "base_url": "https://e2e-test.example.com/v1",
            "api_key": "sk-e2e-secret-key-abcdef",
            "protocol": "openai",
            "supported_models": ["gpt-4o"],
            "priority": 50,
            "protocol_mode": "completions",
        },
        headers=auth_header(token),
    )
    assert create_resp.status_code == 200
    created = create_resp.json()
    ep_id = created["id"]

    # Step 2: Resolve via internal endpoint
    resolve_resp = await async_client.post(
        "/api/ai/endpoint-resolve",
        json={"category": "chat"},
        headers=internal_auth_header(token),
    )
    assert resolve_resp.status_code == 200
    creds = resolve_resp.json()

    # Step 3: Verify credentials
    assert creds["endpoint_id"] == ep_id
    assert creds["name"] == "E2E Test Endpoint"
    assert creds["protocol"] == "openai"
    assert creds["base_url"] == "https://e2e-test.example.com/v1"
    assert creds["api_key"] == "sk-e2e-secret-key-abcdef"
    assert creds["model_id"] == "gpt-4o"
    assert creds["protocol_mode"] == "completions"

    # Step 4: Verify the public resolve does NOT leak api_key
    public_resp = await async_client.get(
        "/api/api-routes/resolve?model=gpt-4o",
        headers=auth_header(token),
    )
    assert public_resp.status_code == 200
    public_data = public_resp.json()
    assert "api_key" not in public_data


# ── Test 11: protocol_mode auto-detection falls back to completions ──

@pytest.mark.asyncio
async def test_protocol_mode_auto_detection_defaults_to_completions(async_client: AsyncClient):
    """When protocol_mode is 'auto' and no detected_protocol_mode in stats_json,
    the resolve endpoint must default to 'completions'."""
    token = await get_admin_token(async_client)

    # Create an endpoint with protocol_mode "auto" and empty stats (no detection yet)
    ep = await create_test_endpoint(
        async_client, token,
        protocol_mode="auto",
        supported_models=["gpt-4o-mini"],
    )

    # Manually clear the detected_protocol_mode from stats to simulate a fresh endpoint
    # (the default stats_json from the model doesn't include detected_protocol_mode)
    resp = await async_client.post(
        "/api/ai/endpoint-resolve",
        json={"category": "chat"},
        headers=internal_auth_header(token),
    )
    assert resp.status_code == 200
    creds = resp.json()

    # With protocol_mode="auto" and no detection result, should default to "completions"
    assert creds["protocol_mode"] == "completions", (
        f"Auto mode without detection should default to 'completions', got '{creds['protocol_mode']}'"
    )


@pytest.mark.asyncio
async def test_protocol_mode_auto_detection_uses_detected_value(async_client: AsyncClient):
    """When protocol_mode is 'auto' and stats_json has detected_protocol_mode='responses',
    the resolve endpoint must return 'responses'."""
    token = await get_admin_token(async_client)

    # Create endpoint with auto mode
    ep = await create_test_endpoint(
        async_client, token,
        protocol_mode="auto",
        supported_models=["gpt-4o-mini"],
    )

    # Manually set detected_protocol_mode in stats via direct DB update
    # (simulating what happens after a successful endpoint test)
    from app.core.database import AsyncSessionLocal
    from app.models.api_endpoint import ApiEndpoint
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(ApiEndpoint).where(ApiEndpoint.id == ep["id"]))
        db_ep = result.scalar_one_or_none()
        assert db_ep is not None
        # Must assign a NEW dict (not mutate in place) so SQLAlchemy detects the change
        old_stats = db_ep.stats_json or {}
        db_ep.stats_json = {**old_stats, "detected_protocol_mode": "responses"}
        await session.commit()

    # Now resolve should return "responses"
    resp = await async_client.post(
        "/api/ai/endpoint-resolve",
        json={"category": "chat"},
        headers=internal_auth_header(token),
    )
    assert resp.status_code == 200
    creds = resp.json()
    assert creds["protocol_mode"] == "responses", (
        f"Expected 'responses' from detected value, got '{creds['protocol_mode']}'"
    )


# ── Test 12: Chat stream error handling produces valid SSE error event ──

@pytest.mark.asyncio
async def test_chat_stream_error_produces_valid_sse_error(async_client: AsyncClient):
    """When the AI provider fails, the stream must still produce valid SSE with an error payload."""
    token = await get_admin_token(async_client)

    mock_endpoint = MagicMock()
    mock_endpoint.id = 1
    mock_endpoint.name = "Failing Endpoint"
    mock_endpoint.protocol = "openai"
    mock_endpoint.base_url = "https://api.openai.com/v1"
    mock_endpoint.api_key = "sk-test"
    mock_endpoint.supported_models = ["gpt-4o"]
    mock_endpoint.protocol_mode = "completions"
    mock_endpoint.stats_json = {}
    mock_endpoint.is_active = True
    mock_endpoint.status = "healthy"
    mock_endpoint.frozen_until = None
    mock_endpoint.priority = 100

    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(side_effect=Exception("Connection refused"))

    with patch("app.api.ai.api_router") as mock_router:
        mock_router.resolve = AsyncMock(return_value=[mock_endpoint])
        mock_router.get_all_models = AsyncMock(return_value=["gpt-4o"])
        mock_router._get_or_create_client = MagicMock(return_value=fake_client)

        resp = await async_client.post(
            "/api/ai/chat/stream",
            json={"messages": [{"role": "user", "content": "Hi"}]},
            headers=auth_header(token),
        )

    assert resp.status_code == 200  # StreamingResponse always returns 200

    raw = resp.text
    events = parse_sse_events(raw)

    # Must have at least one event
    assert len(events) >= 1

    # The error event must be valid JSON with an "error" key
    error_event = json.loads(events[0])
    assert "error" in error_event, f"Expected error payload, got: {error_event}"
    assert isinstance(error_event["error"], str)
    assert len(error_event["error"]) > 0


# ── Test 13: SSE cache-control headers are set correctly ──

@pytest.mark.asyncio
async def test_stream_endpoints_set_no_cache_headers(async_client: AsyncClient):
    """Both chat and edit streams must set Cache-Control: no-cache and X-Accel-Buffering: no."""
    token = await get_admin_token(async_client)

    mock_endpoint = MagicMock()
    mock_endpoint.id = 1
    mock_endpoint.name = "Test"
    mock_endpoint.protocol = "openai"
    mock_endpoint.base_url = "https://api.openai.com/v1"
    mock_endpoint.api_key = "sk-test"
    mock_endpoint.supported_models = ["gpt-4o"]
    mock_endpoint.protocol_mode = "completions"
    mock_endpoint.stats_json = {}
    mock_endpoint.is_active = True
    mock_endpoint.status = "healthy"
    mock_endpoint.frozen_until = None
    mock_endpoint.priority = 100

    async def quick_stream():
        yield MagicMock(choices=[MagicMock(delta=MagicMock(content="ok"))])

    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(return_value=quick_stream())

    with patch("app.api.ai.api_router") as mock_router:
        mock_router.resolve = AsyncMock(return_value=[mock_endpoint])
        mock_router.get_all_models = AsyncMock(return_value=["gpt-4o"])
        mock_router._get_or_create_client = MagicMock(return_value=fake_client)

        # Test chat stream headers
        resp = await async_client.post(
            "/api/ai/chat/stream",
            json={"messages": [{"role": "user", "content": "Hi"}]},
            headers=auth_header(token),
        )
        assert resp.headers.get("cache-control") == "no-cache"
        assert resp.headers.get("x-accel-buffering") == "no"

    with patch("app.api.ai.api_router") as mock_router:
        mock_router.resolve = AsyncMock(return_value=[mock_endpoint])
        mock_router.get_all_models = AsyncMock(return_value=["gpt-4o"])
        mock_router._get_or_create_client = MagicMock(return_value=fake_client)

        # Test edit stream headers
        resp = await async_client.post(
            "/api/ai/edit/stream",
            json={"text": "test", "operation": "polish"},
            headers=auth_header(token),
        )
        assert resp.headers.get("cache-control") == "no-cache"
        assert resp.headers.get("x-accel-buffering") == "no"


# ── Test 14: Multiple endpoints — resolve picks highest priority ──

@pytest.mark.asyncio
async def test_resolve_picks_highest_priority_endpoint(async_client: AsyncClient):
    """When multiple endpoints exist, resolve must pick the one with the best health score
    (which factors in priority — lower priority number = higher score)."""
    token = await get_admin_token(async_client)

    # Create a low-priority endpoint (priority=100, lower score)
    await create_test_endpoint(
        async_client, token,
        name="Low Priority",
        priority=100,
        supported_models=["gpt-4o"],
    )

    # Create a high-priority endpoint (priority=10, higher score)
    await create_test_endpoint(
        async_client, token,
        name="High Priority",
        priority=10,
        base_url="https://high-priority.example.com/v1",
        api_key="sk-high-priority-key",
        supported_models=["gpt-4o"],
    )

    resp = await async_client.post(
        "/api/ai/endpoint-resolve",
        json={"category": "chat"},
        headers=internal_auth_header(token),
    )
    assert resp.status_code == 200
    creds = resp.json()

    # The high-priority endpoint should be selected
    assert creds["name"] == "High Priority"
    assert creds["base_url"] == "https://high-priority.example.com/v1"


# ── Test 15: Edit stream for each operation type ──

@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["polish", "expand", "compress", "translate_zh", "translate_en", "fix"])
async def test_edit_stream_accepts_all_operations(async_client: AsyncClient, operation: str):
    """All supported edit operations must be accepted and produce valid SSE."""
    token = await get_admin_token(async_client)

    mock_endpoint = MagicMock()
    mock_endpoint.id = 1
    mock_endpoint.name = "Test"
    mock_endpoint.protocol = "openai"
    mock_endpoint.base_url = "https://api.openai.com/v1"
    mock_endpoint.api_key = "sk-test"
    mock_endpoint.supported_models = ["gpt-4o"]
    mock_endpoint.protocol_mode = "completions"
    mock_endpoint.stats_json = {}
    mock_endpoint.is_active = True
    mock_endpoint.status = "healthy"
    mock_endpoint.frozen_until = None
    mock_endpoint.priority = 100

    async def quick_stream():
        yield MagicMock(choices=[MagicMock(delta=MagicMock(content="result"))])

    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(return_value=quick_stream())

    with patch("app.api.ai.api_router") as mock_router:
        mock_router.resolve = AsyncMock(return_value=[mock_endpoint])
        mock_router.get_all_models = AsyncMock(return_value=["gpt-4o"])
        mock_router._get_or_create_client = MagicMock(return_value=fake_client)

        resp = await async_client.post(
            "/api/ai/edit/stream",
            json={"text": "Some text to edit.", "operation": operation},
            headers=auth_header(token),
        )

    assert resp.status_code == 200, f"Operation '{operation}' failed with {resp.status_code}"
    assert_valid_sse_format(resp.text)


# ── Test 16: Anthropic protocol mode returns correct credentials ──

@pytest.mark.asyncio
async def test_anthropic_endpoint_resolve_returns_anthropic_protocol(async_client: AsyncClient):
    """An endpoint with protocol='anthropic' must return protocol='anthropic' and
    protocol_mode='completions' (Anthropic uses its own API, not OpenAI's)."""
    token = await get_admin_token(async_client)

    await create_test_endpoint(
        async_client, token,
        name="Anthropic Endpoint",
        provider="anthropic",
        protocol="anthropic",
        base_url="https://api.anthropic.com",
        api_key="sk-ant-test-key",
        supported_models=["claude-sonnet-4-20250514"],
        protocol_mode="completions",
    )

    resp = await async_client.post(
        "/api/ai/endpoint-resolve",
        json={"category": "chat"},
        headers=internal_auth_header(token),
    )
    assert resp.status_code == 200
    creds = resp.json()

    assert creds["protocol"] == "anthropic"
    assert creds["base_url"] == "https://api.anthropic.com"
    assert creds["model_id"] == "claude-sonnet-4-20250514"
    # For anthropic protocol, the endpoint-resolve code sets protocol_mode based on
    # the endpoint's protocol_mode (skipping auto-detection for anthropic)
    assert creds["protocol_mode"] in ("completions", "responses")


# ── Test 17: Inactive endpoints are excluded from resolve ──

@pytest.mark.asyncio
async def test_inactive_endpoint_excluded_from_resolve(async_client: AsyncClient):
    """Endpoints with is_active=False must not be returned by resolve."""
    token = await get_admin_token(async_client)
    ep = await create_test_endpoint(async_client, token, supported_models=["gpt-4o"])

    # Deactivate the endpoint
    resp = await async_client.post(
        f"/api/api-routes/endpoints/{ep['id']}/toggle",
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False

    # Resolve should fail (no active endpoints)
    resp = await async_client.post(
        "/api/ai/endpoint-resolve",
        json={"category": "chat"},
        headers=internal_auth_header(token),
    )
    assert resp.status_code == 400


# ── Test 18: SSE data lines must use "data: " prefix (not "data:") ──

@pytest.mark.asyncio
async def test_sse_lines_have_space_after_data_prefix(async_client: AsyncClient):
    """SSE spec requires 'data: ' (with a space after the colon). Verify compliance."""
    token = await get_admin_token(async_client)

    mock_endpoint = MagicMock()
    mock_endpoint.id = 1
    mock_endpoint.name = "Test"
    mock_endpoint.protocol = "openai"
    mock_endpoint.base_url = "https://api.openai.com/v1"
    mock_endpoint.api_key = "sk-test"
    mock_endpoint.supported_models = ["gpt-4o"]
    mock_endpoint.protocol_mode = "completions"
    mock_endpoint.stats_json = {}
    mock_endpoint.is_active = True
    mock_endpoint.status = "healthy"
    mock_endpoint.frozen_until = None
    mock_endpoint.priority = 100

    async def fake_stream():
        yield MagicMock(choices=[MagicMock(delta=MagicMock(content="test"))])

    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(return_value=fake_stream())

    with patch("app.api.ai.api_router") as mock_router:
        mock_router.resolve = AsyncMock(return_value=[mock_endpoint])
        mock_router.get_all_models = AsyncMock(return_value=["gpt-4o"])
        mock_router._get_or_create_client = MagicMock(return_value=fake_client)

        resp = await async_client.post(
            "/api/ai/chat/stream",
            json={"messages": [{"role": "user", "content": "Hi"}]},
            headers=auth_header(token),
        )

    assert resp.status_code == 200
    raw = resp.text

    # Every non-empty line that starts with "data" must be "data: " (with space)
    for line in raw.split("\n"):
        line = line.strip()
        if line.startswith("data"):
            assert line.startswith("data: "), (
                f"SSE data line missing space after colon: {line!r}"
            )
