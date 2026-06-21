import pytest

@pytest.mark.asyncio
async def test_login_success(async_client):
    # First, the admin user should be auto-created on startup
    # We need to trigger the lifespan first by making a request
    await async_client.get("/api/health")

    response = await async_client.post("/api/auth/login", json={
        "username": "admin",
        "password": "test-admin-password-123",
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"

@pytest.mark.asyncio
async def test_login_wrong_password(async_client):
    await async_client.get("/api/health")

    response = await async_client.post("/api/auth/login", json={
        "username": "admin",
        "password": "wrongpassword",
    })
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_login_nonexistent_user(async_client):
    response = await async_client.post("/api/auth/login", json={
        "username": "nobody",
        "password": "test123",
    })
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_protected_endpoint_no_token(async_client):
    response = await async_client.get("/api/documents")
    assert response.status_code == 401
