"""Edge case tests: malformed content_json, large payloads, concurrent operations."""

import pytest
import json
import asyncio


async def _login(client, username="admin", password="test-admin-password-123"):
    await client.get("/api/health")
    resp = await client.post("/api/auth/login", json={
        "username": username, "password": password,
    })
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ── Malformed content_json ──────────────────────────────────────────────

class TestMalformedContentJson:

    @pytest.mark.asyncio
    async def test_create_with_none_content_json(self, async_client):
        headers = await _login(async_client)
        resp = await async_client.post("/api/documents", json={
            "title": "No Content", "content_json": None,
        }, headers=headers)
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_create_with_empty_dict_content(self, async_client):
        headers = await _login(async_client)
        resp = await async_client.post("/api/documents", json={
            "title": "Empty Content", "content_json": {},
        }, headers=headers)
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_create_with_malformed_tiptap(self, async_client):
        """content_json with wrong structure should not crash the server."""
        headers = await _login(async_client)
        resp = await async_client.post("/api/documents", json={
            "title": "Malformed",
            "content_json": {"wrong": "structure", "content": "not an array"},
        }, headers=headers)
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_export_with_malformed_content(self, async_client):
        """Exporting a document with bad content_json should not crash."""
        headers = await _login(async_client)
        create = await async_client.post("/api/documents", json={
            "title": "Bad Export",
            "content_json": {"type": "doc", "content": [
                {"type": "paragraph"},  # Missing 'content' key
            ]},
        }, headers=headers)
        doc_id = create.json()["id"]

        for fmt in ["markdown", "html", "latex", "docx"]:
            resp = await async_client.get(f"/api/documents/{doc_id}/export?format={fmt}", headers=headers)
            assert resp.status_code == 200, f"Export format {fmt} failed with malformed content"

    @pytest.mark.asyncio
    async def test_update_with_string_content_json(self, async_client):
        """content_json as a JSON string (double-serialized) should be handled."""
        headers = await _login(async_client)
        create = await async_client.post("/api/documents", json={
            "title": "String JSON",
        }, headers=headers)
        doc_id = create.json()["id"]

        # Send content_json as a string (simulating old client behavior)
        tiptap = json.dumps({"type": "doc", "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "Recovered"}]},
        ]})
        resp = await async_client.put(f"/api/documents/{doc_id}", json={
            "content_json": tiptap,
        }, headers=headers)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_export_empty_doc(self, async_client):
        headers = await _login(async_client)
        create = await async_client.post("/api/documents", json={
            "title": "Empty Export",
            "content_json": {"type": "doc", "content": []},
        }, headers=headers)
        doc_id = create.json()["id"]

        for fmt in ["markdown", "html", "latex", "docx"]:
            resp = await async_client.get(f"/api/documents/{doc_id}/export?format={fmt}", headers=headers)
            assert resp.status_code == 200


# ── Large Payloads ──────────────────────────────────────────────────────

class TestLargePayloads:

    @pytest.mark.asyncio
    async def test_create_document_with_large_content(self, async_client):
        """Create a document with substantial content (100KB)."""
        headers = await _login(async_client)
        large_text = "x" * 100000
        content_json = {
            "type": "doc",
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": large_text}]},
            ],
        }
        resp = await async_client.post("/api/documents", json={
            "title": "Large Document",
            "content_json": content_json,
        }, headers=headers)
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_create_document_with_many_headings(self, async_client):
        """Document with 100 heading nodes."""
        headers = await _login(async_client)
        content = {
            "type": "doc",
            "content": [
                {"type": "heading", "attrs": {"level": (i % 6) + 1}, "content": [
                    {"type": "text", "text": f"Heading {i}"},
                ]}
                for i in range(100)
            ],
        }
        resp = await async_client.post("/api/documents", json={
            "title": "Many Headings",
            "content_json": content,
        }, headers=headers)
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_export_large_document_docx(self, async_client):
        """Exporting a large document to DOCX should not timeout."""
        headers = await _login(async_client)
        large_content = "Paragraph content. " * 1000
        content_json = {
            "type": "doc",
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": large_content}]}
                for _ in range(10)
            ],
        }
        create = await async_client.post("/api/documents", json={
            "title": "Large Export",
            "content_json": content_json,
        }, headers=headers)
        doc_id = create.json()["id"]

        resp = await async_client.get(f"/api/documents/{doc_id}/export?format=docx", headers=headers)
        assert resp.status_code == 200
        assert len(resp.content) > 1000  # Should be a real file


# ── Concurrent Operations ───────────────────────────────────────────────

class TestConcurrentOperations:

    @pytest.mark.asyncio
    async def test_concurrent_document_creation(self, async_client):
        """Create multiple documents concurrently."""
        headers = await _login(async_client)

        async def create_doc(i):
            return await async_client.post("/api/documents", json={
                "title": f"Concurrent Doc {i}",
            }, headers=headers)

        results = await asyncio.gather(*[create_doc(i) for i in range(10)])
        for resp in results:
            assert resp.status_code == 201

        # Verify all created
        list_resp = await async_client.get("/api/documents", headers=headers)
        assert list_resp.json()["total"] == 10

    @pytest.mark.asyncio
    async def test_concurrent_tag_creation(self, async_client):
        """Create multiple tags concurrently."""
        headers = await _login(async_client)

        async def create_tag(i):
            return await async_client.post("/api/tags", json={
                "name": f"concurrent-tag-{i}",
            }, headers=headers)

        results = await asyncio.gather(*[create_tag(i) for i in range(10)])
        success_count = sum(1 for r in results if r.status_code == 201)
        assert success_count == 10

    @pytest.mark.asyncio
    async def test_concurrent_folder_creation(self, async_client):
        """Create multiple folders concurrently."""
        headers = await _login(async_client)

        async def create_folder(i):
            return await async_client.post("/api/folders", json={
                "name": f"Concurrent Folder {i}",
            }, headers=headers)

        results = await asyncio.gather(*[create_folder(i) for i in range(10)])
        for resp in results:
            assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_concurrent_update_same_document(self, async_client):
        """Multiple concurrent updates to the same document — all should succeed (last-write-wins)."""
        headers = await _login(async_client)
        create = await async_client.post("/api/documents", json={
            "title": "Race Condition Doc",
        }, headers=headers)
        doc_id = create.json()["id"]

        async def update_doc(i):
            return await async_client.put(f"/api/documents/{doc_id}", json={
                "title": f"Updated by {i}",
            }, headers=headers)

        results = await asyncio.gather(*[update_doc(i) for i in range(5)])
        for resp in results:
            assert resp.status_code == 200


# ── Unicode and Special Characters ──────────────────────────────────────

class TestUnicodeHandling:

    @pytest.mark.asyncio
    async def test_chinese_document_title(self, async_client):
        headers = await _login(async_client)
        resp = await async_client.post("/api/documents", json={
            "title": "中文文档标题",
        }, headers=headers)
        assert resp.status_code == 201
        assert resp.json()["title"] == "中文文档标题"

    @pytest.mark.asyncio
    async def test_emoji_in_title(self, async_client):
        headers = await _login(async_client)
        resp = await async_client.post("/api/documents", json={
            "title": "Document with emoji 🚀",
        }, headers=headers)
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_mixed_language_content(self, async_client):
        headers = await _login(async_client)
        content = {
            "type": "doc",
            "content": [
                {"type": "paragraph", "content": [
                    {"type": "text", "text": "English text 中文文本 Japanese: 日本語 Korean: 한국어"},
                ]},
            ],
        }
        resp = await async_client.post("/api/documents", json={
            "title": "Multilingual",
            "content_json": content,
        }, headers=headers)
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_special_chars_in_tag_name(self, async_client):
        headers = await _login(async_client)
        resp = await async_client.post("/api/tags", json={
            "name": "C++ / C#",
        }, headers=headers)
        assert resp.status_code == 201
        assert resp.json()["name"] == "C++ / C#"

    @pytest.mark.asyncio
    async def test_long_tag_name(self, async_client):
        headers = await _login(async_client)
        long_name = "a" * 100
        resp = await async_client.post("/api/tags", json={"name": long_name}, headers=headers)
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_tag_name_exceeds_max_length(self, async_client):
        headers = await _login(async_client)
        too_long = "a" * 101
        resp = await async_client.post("/api/tags", json={"name": too_long}, headers=headers)
        assert resp.status_code == 422
