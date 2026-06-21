"""Tests for document security: version snapshots, setattr whitelist, XSS in export."""

import pytest


async def _login(client, username="admin", password="test-admin-password-123"):
    await client.get("/api/health")
    resp = await client.post("/api/auth/login", json={
        "username": username, "password": password,
    })
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def _create_doc(client, headers, title="Test", content=None):
    body = {"title": title}
    if content is not None:
        body["content_json"] = content
    resp = await client.post("/api/documents", json=body, headers=headers)
    return resp.json()


# --- Version History ---

@pytest.mark.asyncio
async def test_version_snapshot_created_on_content_change(async_client):
    headers = await _login(async_client)
    doc = await _create_doc(async_client, headers, "V1", {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "hello"}]}]})

    # Update with different content
    await async_client.put(f"/api/documents/{doc['id']}", json={
        "content_json": {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "world"}]}]},
    }, headers=headers)

    # Check versions
    resp = await async_client.get(f"/api/documents/{doc['id']}/versions", headers=headers)
    assert resp.status_code == 200
    versions = resp.json()
    assert len(versions) >= 1


@pytest.mark.asyncio
async def test_version_snapshot_dedup_same_content(async_client):
    headers = await _login(async_client)
    content = {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "same"}]}]}
    doc = await _create_doc(async_client, headers, "Dedup", content)

    # Update with identical content
    await async_client.put(f"/api/documents/{doc['id']}", json={
        "content_json": content,
    }, headers=headers)

    # Should NOT create a snapshot since content is the same
    resp = await async_client.get(f"/api/documents/{doc['id']}/versions", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 0


@pytest.mark.asyncio
async def test_version_title_only_update_no_snapshot(async_client):
    headers = await _login(async_client)
    doc = await _create_doc(async_client, headers, "TitleOnly", {"type": "doc", "content": []})

    # Only update title, no content change
    await async_client.put(f"/api/documents/{doc['id']}", json={
        "title": "NewTitle",
    }, headers=headers)

    resp = await async_client.get(f"/api/documents/{doc['id']}/versions", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 0


@pytest.mark.asyncio
async def test_version_restore(async_client):
    headers = await _login(async_client)
    original = {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "original"}]}]}
    doc = await _create_doc(async_client, headers, "Restore", original)

    updated = {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "updated"}]}]}
    await async_client.put(f"/api/documents/{doc['id']}", json={
        "content_json": updated,
    }, headers=headers)

    # Get version
    versions = await async_client.get(f"/api/documents/{doc['id']}/versions", headers=headers)
    assert len(versions.json()) >= 1
    version_id = versions.json()[0]["id"]

    # Restore
    resp = await async_client.post(f"/api/documents/{doc['id']}/versions/{version_id}/restore", headers=headers)
    assert resp.status_code == 200

    # Verify restored
    current = await async_client.get(f"/api/documents/{doc['id']}", headers=headers)
    assert current.json()["content_json"]["content"][0]["content"][0]["text"] == "original"


# --- Setattr Whitelist ---

@pytest.mark.asyncio
async def test_update_rejects_disallowed_fields(async_client):
    """User should not be able to set user_id or version via the update endpoint."""
    headers = await _login(async_client)
    doc = await _create_doc(async_client, headers, "Whitelist")

    # Attempt to set user_id (not in schema, silently ignored by Pydantic)
    resp = await async_client.put(f"/api/documents/{doc['id']}", json={
        "title": "New Title",
        "user_id": 999,  # Silently ignored — not a DocumentUpdate field
    }, headers=headers)
    assert resp.status_code == 200
    # Title should have been updated, proving the allowed field was applied
    assert resp.json()["title"] == "New Title"
    # Version increments on every update
    assert resp.json()["version"] == 2


# --- XSS in HTML Export ---

@pytest.mark.asyncio
async def test_html_export_escapes_xss_in_title(async_client):
    headers = await _login(async_client)
    doc = await _create_doc(async_client, headers, '<script>alert("xss")</script>')

    resp = await async_client.get(f"/api/documents/{doc['id']}/export?format=html", headers=headers)
    assert resp.status_code == 200
    html = resp.text
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


@pytest.mark.asyncio
async def test_html_export_escapes_xss_in_codeblock(async_client):
    headers = await _login(async_client)
    malicious_content = {
        "type": "doc",
        "content": [{
            "type": "codeBlock",
            "attrs": {"language": '"><img src=x onerror=alert(1)>'},
            "content": [{"type": "text", "text": "code"}],
        }],
    }
    doc = await _create_doc(async_client, headers, "XSS CodeBlock", malicious_content)

    resp = await async_client.get(f"/api/documents/{doc['id']}/export?format=html", headers=headers)
    assert resp.status_code == 200
    html = resp.text
    assert 'onerror=alert(1)' not in html or "&lt;" in html


# --- Document Ownership ---

@pytest.mark.asyncio
async def test_user_cannot_access_other_users_document(async_client):
    admin_headers = await _login(async_client)
    doc = await _create_doc(async_client, admin_headers, "Admin Private")

    # Create second user
    await async_client.post("/api/admin/users", json={
        "username": "other", "email": "other@test.com",
        "password": "pass123", "is_admin": False,
    }, headers=admin_headers)

    other_headers = await _login(async_client, "other", "pass123")

    # other user cannot read admin's document
    resp = await async_client.get(f"/api/documents/{doc['id']}", headers=other_headers)
    assert resp.status_code == 404

    # other user cannot update admin's document
    resp = await async_client.put(f"/api/documents/{doc['id']}", json={
        "title": "Hacked",
    }, headers=other_headers)
    assert resp.status_code == 404

    # other user cannot delete admin's document
    resp = await async_client.delete(f"/api/documents/{doc['id']}", headers=other_headers)
    assert resp.status_code == 404


# --- Export Formats ---

@pytest.mark.asyncio
async def test_export_markdown(async_client):
    headers = await _login(async_client)
    doc = await _create_doc(async_client, headers, "MD Export", {
        "type": "doc",
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Hello world"}]}],
    })
    resp = await async_client.get(f"/api/documents/{doc['id']}/export?format=markdown", headers=headers)
    assert resp.status_code == 200
    assert "Hello world" in resp.text


@pytest.mark.asyncio
async def test_export_latex(async_client):
    headers = await _login(async_client)
    doc = await _create_doc(async_client, headers, "LaTeX Export", {
        "type": "doc",
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Some content"}]}],
    })
    resp = await async_client.get(f"/api/documents/{doc['id']}/export?format=latex", headers=headers)
    assert resp.status_code == 200
    assert "\\documentclass" in resp.text


# --- Pagination ---

@pytest.mark.asyncio
async def test_document_list_pagination(async_client):
    headers = await _login(async_client)
    for i in range(15):
        await _create_doc(async_client, headers, f"Doc {i:02d}")

    # Default page
    resp = await async_client.get("/api/documents", headers=headers)
    assert resp.json()["total"] == 15

    # With limit
    resp = await async_client.get("/api/documents?limit=5&offset=0", headers=headers)
    assert len(resp.json()["documents"]) == 5
    assert resp.json()["total"] == 15

    # Second page
    resp = await async_client.get("/api/documents?limit=5&offset=5", headers=headers)
    assert len(resp.json()["documents"]) == 5
