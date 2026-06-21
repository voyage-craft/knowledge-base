"""Tests for admin API: user CRUD, require_admin, self-protection."""

import pytest


async def _login(client, username="admin", password="test-admin-password-123"):
    await client.get("/api/health")
    resp = await client.post("/api/auth/login", json={
        "username": username, "password": password,
    })
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.mark.asyncio
async def test_admin_list_users(async_client):
    headers = await _login(async_client)
    resp = await async_client.get("/api/admin/users", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert any(u["username"] == "admin" for u in data["users"])


@pytest.mark.asyncio
async def test_admin_create_user(async_client):
    headers = await _login(async_client)
    resp = await async_client.post("/api/admin/users", json={
        "username": "newuser",
        "email": "new@test.com",
        "password": "secure123",
        "is_admin": False,
    }, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "newuser"
    assert data["email"] == "new@test.com"
    assert data["is_admin"] is False
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_admin_create_duplicate_username(async_client):
    headers = await _login(async_client)
    await async_client.post("/api/admin/users", json={
        "username": "dupuser", "email": "dup1@test.com",
        "password": "pass123", "is_admin": False,
    }, headers=headers)
    resp = await async_client.post("/api/admin/users", json={
        "username": "dupuser", "email": "dup2@test.com",
        "password": "pass123", "is_admin": False,
    }, headers=headers)
    assert resp.status_code == 400
    assert "用户名已存在" in resp.json()["message"]


@pytest.mark.asyncio
async def test_admin_create_duplicate_email(async_client):
    headers = await _login(async_client)
    await async_client.post("/api/admin/users", json={
        "username": "emailuser1", "email": "same@test.com",
        "password": "pass123", "is_admin": False,
    }, headers=headers)
    resp = await async_client.post("/api/admin/users", json={
        "username": "emailuser2", "email": "same@test.com",
        "password": "pass123", "is_admin": False,
    }, headers=headers)
    assert resp.status_code == 400
    assert "邮箱已被使用" in resp.json()["message"]


@pytest.mark.asyncio
async def test_admin_update_user(async_client):
    headers = await _login(async_client)
    create = await async_client.post("/api/admin/users", json={
        "username": "updateme", "email": "up@test.com",
        "password": "pass123", "is_admin": False,
    }, headers=headers)
    uid = create.json()["id"]

    resp = await async_client.put(f"/api/admin/users/{uid}", json={
        "is_active": False,
    }, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_admin_cannot_demote_self(async_client):
    headers = await _login(async_client)
    # Get admin's own ID
    me = await async_client.get("/api/admin/users", headers=headers)
    admin_id = next(u["id"] for u in me.json()["users"] if u["username"] == "admin")

    resp = await async_client.put(f"/api/admin/users/{admin_id}", json={
        "is_admin": False,
    }, headers=headers)
    assert resp.status_code == 400
    assert "不能取消自己的管理员权限" in resp.json()["message"]


@pytest.mark.asyncio
async def test_admin_reset_password(async_client):
    headers = await _login(async_client)
    create = await async_client.post("/api/admin/users", json={
        "username": "resetme", "email": "reset@test.com",
        "password": "old123", "is_admin": False,
    }, headers=headers)
    uid = create.json()["id"]

    resp = await async_client.post(f"/api/admin/users/{uid}/reset-password", json={
        "new_password": "newpass456",
    }, headers=headers)
    assert resp.status_code == 200

    # Verify new password works
    login = await async_client.post("/api/auth/login", json={
        "username": "resetme", "password": "newpass456",
    })
    assert login.status_code == 200


@pytest.mark.asyncio
async def test_admin_disable_user(async_client):
    headers = await _login(async_client)
    create = await async_client.post("/api/admin/users", json={
        "username": "disableme", "email": "dis@test.com",
        "password": "pass123", "is_admin": False,
    }, headers=headers)
    uid = create.json()["id"]

    resp = await async_client.delete(f"/api/admin/users/{uid}", headers=headers)
    assert resp.status_code == 200

    # Disabled user cannot login
    login = await async_client.post("/api/auth/login", json={
        "username": "disableme", "password": "pass123",
    })
    assert login.status_code in (401, 403)


@pytest.mark.asyncio
async def test_admin_cannot_delete_self(async_client):
    headers = await _login(async_client)
    me = await async_client.get("/api/admin/users", headers=headers)
    admin_id = next(u["id"] for u in me.json()["users"] if u["username"] == "admin")

    resp = await async_client.delete(f"/api/admin/users/{admin_id}", headers=headers)
    assert resp.status_code == 400
    assert "不能删除自己的账户" in resp.json()["message"]


@pytest.mark.asyncio
async def test_non_admin_cannot_access_admin_api(async_client):
    headers = await _login(async_client)
    # Create a non-admin user
    await async_client.post("/api/admin/users", json={
        "username": "normie", "email": "norm@test.com",
        "password": "pass123", "is_admin": False,
    }, headers=headers)

    normie_headers = await _login(async_client, "normie", "pass123")

    resp = await async_client.get("/api/admin/users", headers=normie_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_search_users(async_client):
    headers = await _login(async_client)
    await async_client.post("/api/admin/users", json={
        "username": "searchable_alice", "email": "alice@test.com",
        "password": "pass123", "is_admin": False,
    }, headers=headers)

    resp = await async_client.get("/api/admin/users?search=alice", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1
    assert any("alice" in u["username"] for u in resp.json()["users"])


@pytest.mark.asyncio
async def test_admin_update_nonexistent_user(async_client):
    headers = await _login(async_client)
    resp = await async_client.put("/api/admin/users/99999", json={
        "is_active": False,
    }, headers=headers)
    assert resp.status_code == 404
