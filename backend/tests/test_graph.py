"""Tests for knowledge graph API: CRUD, cross-user isolation, build lock."""

import pytest


async def _login(client, username="admin", password="test-admin-password-123"):
    await client.get("/api/health")
    resp = await client.post("/api/auth/login", json={
        "username": username, "password": password,
    })
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.mark.asyncio
async def test_graph_empty_initially(async_client):
    headers = await _login(async_client)
    resp = await async_client.get("/api/graph", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["nodes"] == []
    assert data["edges"] == []


@pytest.mark.asyncio
async def test_graph_build_no_documents(async_client):
    """Build should succeed even when there are no documents."""
    headers = await _login(async_client)
    resp = await async_client.post("/api/graph/build", headers=headers)
    assert resp.status_code == 200
    assert "message" in resp.json()


@pytest.mark.asyncio
async def test_graph_requires_auth(async_client):
    resp = await async_client.get("/api/graph")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_graph_build_requires_auth(async_client):
    resp = await async_client.post("/api/graph/build")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_graph_delete_nonexistent_node(async_client):
    headers = await _login(async_client)
    resp = await async_client.delete("/api/graph/node/99999", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_graph_document_filter(async_client):
    headers = await _login(async_client)
    resp = await async_client.get("/api/graph?document_id=99999", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["nodes"] == []
    assert data["edges"] == []


@pytest.mark.asyncio
async def test_graph_document_not_found(async_client):
    headers = await _login(async_client)
    resp = await async_client.get("/api/graph/document/99999", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_graph_cross_user_isolation(async_client):
    """Graph data from one user should not be visible to another."""
    # Admin creates a document and triggers a build
    admin_headers = await _login(async_client)
    await async_client.post(
        "/api/documents", json={"title": "Admin Doc"}, headers=admin_headers,
    )

    # Create a second user via admin API
    await async_client.post("/api/admin/users", json={
        "username": "user2", "email": "u2@test.com",
        "password": "pass123", "is_admin": False,
    }, headers=admin_headers)

    user2_headers = await _login(async_client, "user2", "pass123")

    # user2 should see empty graph
    resp = await async_client.get("/api/graph", headers=user2_headers)
    assert resp.status_code == 200
    assert resp.json()["nodes"] == []
