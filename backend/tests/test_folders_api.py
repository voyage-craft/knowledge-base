"""Tests for Folders API: CRUD, nesting, document moving, edge cases."""

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


# ── Create Folder ───────────────────────────────────────────────────────

class TestCreateFolder:

    @pytest.mark.asyncio
    async def test_create_root_folder(self, async_client):
        headers = await _login(async_client)
        resp = await async_client.post("/api/folders", json={"name": "My Folder"}, headers=headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "My Folder"
        assert data["parent_id"] is None

    @pytest.mark.asyncio
    async def test_create_nested_folder(self, async_client):
        headers = await _login(async_client)
        parent = await async_client.post("/api/folders", json={"name": "Parent"}, headers=headers)
        parent_id = parent.json()["id"]
        child = await async_client.post("/api/folders", json={
            "name": "Child", "parent_id": parent_id,
        }, headers=headers)
        assert child.status_code == 201
        assert child.json()["parent_id"] == parent_id

    @pytest.mark.asyncio
    async def test_create_folder_invalid_parent(self, async_client):
        headers = await _login(async_client)
        resp = await async_client.post("/api/folders", json={
            "name": "Orphan", "parent_id": 99999,
        }, headers=headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_create_folder_empty_name(self, async_client):
        headers = await _login(async_client)
        resp = await async_client.post("/api/folders", json={"name": ""}, headers=headers)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_folder_requires_auth(self, async_client):
        resp = await async_client.post("/api/folders", json={"name": "No Auth"})
        assert resp.status_code == 401


# ── List Folders ────────────────────────────────────────────────────────

class TestListFolders:

    @pytest.mark.asyncio
    async def test_list_empty_folders(self, async_client):
        headers = await _login(async_client)
        resp = await async_client.get("/api/folders", headers=headers)
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_list_folders_returns_user_folders_only(self, async_client):
        admin_headers = await _login(async_client)
        user2_headers = await _create_user_and_login(async_client, admin_headers, "folderuser2")

        await async_client.post("/api/folders", json={"name": "Admin Folder"}, headers=admin_headers)
        await async_client.post("/api/folders", json={"name": "User2 Folder"}, headers=user2_headers)

        admin_resp = await async_client.get("/api/folders", headers=admin_headers)
        user2_resp = await async_client.get("/api/folders", headers=user2_headers)

        admin_names = [f["name"] for f in admin_resp.json()]
        user2_names = [f["name"] for f in user2_resp.json()]
        assert "Admin Folder" in admin_names
        assert "Admin Folder" not in user2_names


# ── Rename Folder ───────────────────────────────────────────────────────

class TestRenameFolder:

    @pytest.mark.asyncio
    async def test_rename_folder(self, async_client):
        headers = await _login(async_client)
        create = await async_client.post("/api/folders", json={"name": "Old Name"}, headers=headers)
        folder_id = create.json()["id"]
        resp = await async_client.put(f"/api/folders/{folder_id}", json={"name": "New Name"}, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"

    @pytest.mark.asyncio
    async def test_rename_nonexistent_folder(self, async_client):
        headers = await _login(async_client)
        resp = await async_client.put("/api/folders/99999", json={"name": "X"}, headers=headers)
        assert resp.status_code == 404


# ── Delete Folder ───────────────────────────────────────────────────────

class TestDeleteFolder:

    @pytest.mark.asyncio
    async def test_delete_folder_moves_docs_to_root(self, async_client):
        headers = await _login(async_client)
        # Create folder
        folder = await async_client.post("/api/folders", json={"name": "To Delete"}, headers=headers)
        folder_id = folder.json()["id"]
        # Create document in folder
        doc = await async_client.post("/api/documents", json={
            "title": "Doc in Folder", "folder_id": folder_id,
        }, headers=headers)
        doc_id = doc.json()["id"]

        # Delete folder
        resp = await async_client.delete(f"/api/folders/{folder_id}", headers=headers)
        assert resp.status_code == 200

        # Document should still exist but with folder_id=None
        doc_resp = await async_client.get(f"/api/documents/{doc_id}", headers=headers)
        assert doc_resp.status_code == 200
        assert doc_resp.json()["folder_id"] is None

    @pytest.mark.asyncio
    async def test_delete_folder_reparents_children(self, async_client):
        headers = await _login(async_client)
        parent = await async_client.post("/api/folders", json={"name": "Parent"}, headers=headers)
        parent_id = parent.json()["id"]
        child = await async_client.post("/api/folders", json={
            "name": "Child", "parent_id": parent_id,
        }, headers=headers)
        child_id = child.json()["id"]

        # Delete parent
        await async_client.delete(f"/api/folders/{parent_id}", headers=headers)

        # Child should still exist but reparented to root
        folders = await async_client.get("/api/folders", headers=headers)
        child_folder = next((f for f in folders.json() if f["id"] == child_id), None)
        assert child_folder is not None
        assert child_folder["parent_id"] is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_folder(self, async_client):
        headers = await _login(async_client)
        resp = await async_client.delete("/api/folders/99999", headers=headers)
        assert resp.status_code == 404


# ── Move Document ───────────────────────────────────────────────────────

class TestMoveDocument:

    @pytest.mark.asyncio
    async def test_move_document_to_folder(self, async_client):
        headers = await _login(async_client)
        folder = await async_client.post("/api/folders", json={"name": "Target"}, headers=headers)
        folder_id = folder.json()["id"]
        doc = await async_client.post("/api/documents", json={"title": "Movable"}, headers=headers)
        doc_id = doc.json()["id"]

        resp = await async_client.post(f"/api/folders/move-document/{doc_id}", json={
            "folder_id": folder_id,
        }, headers=headers)
        assert resp.status_code == 200

        doc_resp = await async_client.get(f"/api/documents/{doc_id}", headers=headers)
        assert doc_resp.json()["folder_id"] == folder_id

    @pytest.mark.asyncio
    async def test_move_document_to_root(self, async_client):
        headers = await _login(async_client)
        folder = await async_client.post("/api/folders", json={"name": "Temp"}, headers=headers)
        folder_id = folder.json()["id"]
        doc = await async_client.post("/api/documents", json={
            "title": "Move to Root", "folder_id": folder_id,
        }, headers=headers)
        doc_id = doc.json()["id"]

        resp = await async_client.post(f"/api/folders/move-document/{doc_id}", json={
            "folder_id": None,
        }, headers=headers)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_move_nonexistent_document(self, async_client):
        headers = await _login(async_client)
        resp = await async_client.post("/api/folders/move-document/99999", json={
            "folder_id": None,
        }, headers=headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_move_to_nonexistent_folder(self, async_client):
        headers = await _login(async_client)
        doc = await async_client.post("/api/documents", json={"title": "X"}, headers=headers)
        doc_id = doc.json()["id"]
        resp = await async_client.post(f"/api/folders/move-document/{doc_id}", json={
            "folder_id": 99999,
        }, headers=headers)
        assert resp.status_code == 404


# ── Deep Nesting ────────────────────────────────────────────────────────

class TestDeepNesting:

    @pytest.mark.asyncio
    async def test_create_deeply_nested_folders(self, async_client):
        """Create a 5-level deep folder hierarchy."""
        headers = await _login(async_client)
        parent_id = None
        created_ids = []
        for i in range(5):
            resp = await async_client.post("/api/folders", json={
                "name": f"Level {i}", "parent_id": parent_id,
            }, headers=headers)
            assert resp.status_code == 201
            parent_id = resp.json()["id"]
            created_ids.append(parent_id)

        # All should be listed
        folders = await async_client.get("/api/folders", headers=headers)
        assert len(folders.json()) == 5

    @pytest.mark.asyncio
    async def test_delete_middle_folder_in_hierarchy(self, async_client):
        """Deleting a middle folder should reparent its children, not cascade delete."""
        headers = await _login(async_client)
        root = (await async_client.post("/api/folders", json={"name": "Root"}, headers=headers)).json()["id"]
        middle = (await async_client.post("/api/folders", json={"name": "Middle", "parent_id": root}, headers=headers)).json()["id"]
        leaf = (await async_client.post("/api/folders", json={"name": "Leaf", "parent_id": middle}, headers=headers)).json()["id"]

        await async_client.delete(f"/api/folders/{middle}", headers=headers)

        folders = await async_client.get("/api/folders", headers=headers)
        leaf_folder = next(f for f in folders.json() if f["id"] == leaf)
        assert leaf_folder["parent_id"] is None  # Reparented to root
