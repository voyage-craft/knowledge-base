import pytest

@pytest.mark.asyncio
async def test_create_document(async_client):
    # Login first
    await async_client.get("/api/health")
    login = await async_client.post("/api/auth/login", json={
        "username": "admin",
        "password": "test-admin-password-123",
    })
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create document
    response = await async_client.post(
        "/api/documents",
        json={"title": "Test Document"},
        headers=headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Document"
    assert data["status"] == "draft"
    assert data["version"] == 1

@pytest.mark.asyncio
async def test_list_documents(async_client):
    await async_client.get("/api/health")
    login = await async_client.post("/api/auth/login", json={
        "username": "admin", "password": "test-admin-password-123",
    })
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create 3 documents
    for i in range(3):
        await async_client.post(
            "/api/documents",
            json={"title": f"Document {i}"},
            headers=headers,
        )

    # List
    response = await async_client.get("/api/documents", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["documents"]) == 3

@pytest.mark.asyncio
async def test_update_document(async_client):
    await async_client.get("/api/health")
    login = await async_client.post("/api/auth/login", json={
        "username": "admin", "password": "test-admin-password-123",
    })
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create
    create = await async_client.post(
        "/api/documents",
        json={"title": "Original Title"},
        headers=headers,
    )
    doc_id = create.json()["id"]

    # Update
    response = await async_client.put(
        f"/api/documents/{doc_id}",
        json={"title": "Updated Title", "content_json": '{"type":"doc","content":[]}'},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Updated Title"
    assert response.json()["version"] == 2

@pytest.mark.asyncio
async def test_delete_document(async_client):
    await async_client.get("/api/health")
    login = await async_client.post("/api/auth/login", json={
        "username": "admin", "password": "test-admin-password-123",
    })
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create
    create = await async_client.post(
        "/api/documents",
        json={"title": "To Delete"},
        headers=headers,
    )
    doc_id = create.json()["id"]

    # Delete (soft)
    response = await async_client.delete(f"/api/documents/{doc_id}", headers=headers)
    assert response.status_code == 200

    # Verify not in list
    list_resp = await async_client.get("/api/documents", headers=headers)
    assert list_resp.json()["total"] == 0

@pytest.mark.asyncio
async def test_search_documents(async_client):
    await async_client.get("/api/health")
    login = await async_client.post("/api/auth/login", json={
        "username": "admin", "password": "test-admin-password-123",
    })
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    await async_client.post("/api/documents", json={"title": "Python Tutorial"}, headers=headers)
    await async_client.post("/api/documents", json={"title": "LaTeX Guide"}, headers=headers)
    await async_client.post("/api/documents", json={"title": "Python Advanced"}, headers=headers)

    response = await async_client.get("/api/documents?search=Python", headers=headers)
    assert response.status_code == 200
    assert response.json()["total"] == 2

@pytest.mark.asyncio
async def test_empty_title_rejected(async_client):
    await async_client.get("/api/health")
    login = await async_client.post("/api/auth/login", json={
        "username": "admin", "password": "test-admin-password-123",
    })
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = await async_client.post(
        "/api/documents",
        json={"title": ""},
        headers=headers,
    )
    assert response.status_code == 422
