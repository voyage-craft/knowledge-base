"""Tests for Tags API: CRUD, assignment, validation, isolation."""

import pytest


async def _login(client, username="admin", password="test-admin-password-123"):
    await client.get("/api/health")
    resp = await client.post("/api/auth/login", json={
        "username": username, "password": password,
    })
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _create_user_and_login(client, admin_headers, username, password="pass123"):
    await client.post("/api/admin/users", json={
        "username": username, "email": f"{username}@test.com",
        "password": password, "is_admin": False,
    }, headers=admin_headers)
    return await _login(client, username, password)


# ── Create Tag ──────────────────────────────────────────────────────────

class TestCreateTag:

    @pytest.mark.asyncio
    async def test_create_tag_success(self, async_client):
        headers = await _login(async_client)
        resp = await async_client.post("/api/tags", json={
            "name": "python", "color": "#FF5733",
        }, headers=headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "python"
        assert data["color"] == "#FF5733"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_tag_default_color(self, async_client):
        headers = await _login(async_client)
        resp = await async_client.post("/api/tags", json={"name": "default-color"}, headers=headers)
        assert resp.status_code == 201
        assert resp.json()["color"] == "#3B82F6"

    @pytest.mark.asyncio
    async def test_create_tag_duplicate_name_returns_409(self, async_client):
        headers = await _login(async_client)
        await async_client.post("/api/tags", json={"name": "unique-tag"}, headers=headers)
        resp = await async_client.post("/api/tags", json={"name": "unique-tag"}, headers=headers)
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_create_tag_invalid_color_format(self, async_client):
        headers = await _login(async_client)
        resp = await async_client.post("/api/tags", json={
            "name": "bad-color", "color": "red",
        }, headers=headers)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_tag_empty_name(self, async_client):
        headers = await _login(async_client)
        resp = await async_client.post("/api/tags", json={"name": ""}, headers=headers)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_tag_requires_auth(self, async_client):
        resp = await async_client.post("/api/tags", json={"name": "no-auth"})
        assert resp.status_code == 401


# ── List Tags ───────────────────────────────────────────────────────────

class TestListTags:

    @pytest.mark.asyncio
    async def test_list_tags_empty(self, async_client):
        headers = await _login(async_client)
        resp = await async_client.get("/api/tags", headers=headers)
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_list_tags_returns_user_tags_only(self, async_client):
        admin_headers = await _login(async_client)
        user2_headers = await _create_user_and_login(async_client, admin_headers, "taguser2")

        await async_client.post("/api/tags", json={"name": "admin-tag"}, headers=admin_headers)
        await async_client.post("/api/tags", json={"name": "user2-tag"}, headers=user2_headers)

        admin_resp = await async_client.get("/api/tags", headers=admin_headers)
        user2_resp = await async_client.get("/api/tags", headers=user2_headers)

        admin_names = [t["name"] for t in admin_resp.json()]
        user2_names = [t["name"] for t in user2_resp.json()]
        assert "admin-tag" in admin_names
        assert "admin-tag" not in user2_names
        assert "user2-tag" in user2_names

    @pytest.mark.asyncio
    async def test_list_tags_sorted_by_name(self, async_client):
        headers = await _login(async_client)
        await async_client.post("/api/tags", json={"name": "zebra"}, headers=headers)
        await async_client.post("/api/tags", json={"name": "alpha"}, headers=headers)
        resp = await async_client.get("/api/tags", headers=headers)
        names = [t["name"] for t in resp.json()]
        assert names == sorted(names)


# ── Delete Tag ──────────────────────────────────────────────────────────

class TestDeleteTag:

    @pytest.mark.asyncio
    async def test_delete_tag_success(self, async_client):
        headers = await _login(async_client)
        create = await async_client.post("/api/tags", json={"name": "to-delete"}, headers=headers)
        tag_id = create.json()["id"]
        resp = await async_client.delete(f"/api/tags/{tag_id}", headers=headers)
        assert resp.status_code == 200
        # Verify gone
        tags = await async_client.get("/api/tags", headers=headers)
        assert all(t["id"] != tag_id for t in tags.json())

    @pytest.mark.asyncio
    async def test_delete_nonexistent_tag_returns_404(self, async_client):
        headers = await _login(async_client)
        resp = await async_client.delete("/api/tags/99999", headers=headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_other_users_tag_returns_404(self, async_client):
        admin_headers = await _login(async_client)
        user2_headers = await _create_user_and_login(async_client, admin_headers, "tagthief")

        create = await async_client.post("/api/tags", json={"name": "admin-owns-this"}, headers=admin_headers)
        tag_id = create.json()["id"]

        resp = await async_client.delete(f"/api/tags/{tag_id}", headers=user2_headers)
        assert resp.status_code == 404


# ── Assign Tags to Document ─────────────────────────────────────────────

class TestAssignTags:

    @pytest.mark.asyncio
    async def test_assign_tags_to_document(self, async_client):
        headers = await _login(async_client)
        # Create document
        doc = await async_client.post("/api/documents", json={"title": "Tagged Doc"}, headers=headers)
        doc_id = doc.json()["id"]
        # Create tags
        t1 = await async_client.post("/api/tags", json={"name": "tag1"}, headers=headers)
        t2 = await async_client.post("/api/tags", json={"name": "tag2"}, headers=headers)
        tag_ids = [t1.json()["id"], t2.json()["id"]]

        resp = await async_client.put(f"/api/tags/assign/{doc_id}", json={"tag_ids": tag_ids}, headers=headers)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_assign_empty_tag_list_clears_tags(self, async_client):
        headers = await _login(async_client)
        doc = await async_client.post("/api/documents", json={"title": "Clear Tags"}, headers=headers)
        doc_id = doc.json()["id"]

        resp = await async_client.put(f"/api/tags/assign/{doc_id}", json={"tag_ids": []}, headers=headers)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_assign_tags_to_nonexistent_document(self, async_client):
        headers = await _login(async_client)
        resp = await async_client.put("/api/tags/assign/99999", json={"tag_ids": []}, headers=headers)
        assert resp.status_code == 404
