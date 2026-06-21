"""Tests for RAG API: embed, search, status, delete embeddings."""

import pytest
import json
from unittest.mock import patch, AsyncMock, MagicMock

import numpy as np


async def _login(client, username="admin", password="test-admin-password-123"):
    await client.get("/api/health")
    resp = await client.post("/api/auth/login", json={
        "username": username, "password": password,
    })
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _make_mock_embed_service():
    """Create a mock embedding service that returns deterministic embeddings."""
    mock_service = AsyncMock()

    async def fake_embed(texts):
        return [np.random.rand(1024).tolist() for _ in texts]

    async def fake_embed_query(text):
        return np.random.rand(1024).tolist()

    mock_service.embed = fake_embed
    mock_service.embed_query = fake_embed_query
    return mock_service


# ── Embed Document ──────────────────────────────────────────────────────

class TestEmbedDocument:

    @pytest.mark.asyncio
    async def test_embed_document_accepted(self, async_client):
        headers = await _login(async_client)
        doc = await async_client.post("/api/documents", json={
            "title": "Embeddable",
            "content_json": {"type": "doc", "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "Some content to embed."}]},
            ]},
        }, headers=headers)
        doc_id = doc.json()["id"]

        resp = await async_client.post(f"/api/rag/embed/{doc_id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["document_id"] == doc_id

    @pytest.mark.asyncio
    async def test_embed_nonexistent_document(self, async_client):
        headers = await _login(async_client)
        resp = await async_client.post("/api/rag/embed/99999", headers=headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_embed_requires_auth(self, async_client):
        resp = await async_client.post("/api/rag/embed/1")
        assert resp.status_code == 401


# ── Batch Embed ─────────────────────────────────────────────────────────

class TestEmbedBatch:

    @pytest.mark.asyncio
    async def test_embed_batch_submits_all_docs(self, async_client):
        headers = await _login(async_client)
        for i in range(3):
            await async_client.post("/api/documents", json={"title": f"Doc {i}"}, headers=headers)

        resp = await async_client.post("/api/rag/embed-batch", json={}, headers=headers)
        assert resp.status_code == 200
        assert "3" in resp.json()["message"]

    @pytest.mark.asyncio
    async def test_embed_batch_empty(self, async_client):
        headers = await _login(async_client)
        resp = await async_client.post("/api/rag/embed-batch", json={}, headers=headers)
        assert resp.status_code == 200
        assert "0" in resp.json()["message"]


# ── Delete Embeddings ───────────────────────────────────────────────────

class TestDeleteEmbeddings:

    @pytest.mark.asyncio
    async def test_delete_embeddings(self, async_client):
        headers = await _login(async_client)
        doc = await async_client.post("/api/documents", json={"title": "De Embed"}, headers=headers)
        doc_id = doc.json()["id"]

        resp = await async_client.delete(f"/api/rag/embeddings/{doc_id}", headers=headers)
        assert resp.status_code == 200


# ── Status ──────────────────────────────────────────────────────────────

class TestRAGStatus:

    @pytest.mark.asyncio
    async def test_status_returns_counts(self, async_client):
        headers = await _login(async_client)
        await async_client.post("/api/documents", json={"title": "Status Doc"}, headers=headers)

        resp = await async_client.get("/api/rag/status", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_documents" in data
        assert "embedded_documents" in data
        assert "total_chunks" in data
        assert data["total_documents"] >= 1

    @pytest.mark.asyncio
    async def test_status_requires_auth(self, async_client):
        resp = await async_client.get("/api/rag/status")
        assert resp.status_code == 401


# ── Search ──────────────────────────────────────────────────────────────

class TestRAGSearch:

    @pytest.mark.asyncio
    async def test_search_no_embeddings_returns_empty(self, async_client):
        headers = await _login(async_client)
        mock_svc = _make_mock_embed_service()
        with patch("app.api.rag.embedding_service", mock_svc):
            resp = await async_client.get("/api/rag/search?q=test+query", headers=headers)
            assert resp.status_code == 200
            assert resp.json()["results"] == []

    @pytest.mark.asyncio
    async def test_search_empty_query_rejected(self, async_client):
        headers = await _login(async_client)
        resp = await async_client.get("/api/rag/search?q=", headers=headers)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_search_respects_top_k(self, async_client):
        headers = await _login(async_client)
        mock_svc = _make_mock_embed_service()
        with patch("app.api.rag.embedding_service", mock_svc):
            resp = await async_client.get("/api/rag/search?q=test&top_k=3", headers=headers)
            assert resp.status_code == 200
            assert len(resp.json()["results"]) <= 3

    @pytest.mark.asyncio
    async def test_search_invalid_top_k(self, async_client):
        headers = await _login(async_client)
        resp = await async_client.get("/api/rag/search?q=test&top_k=0", headers=headers)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_search_threshold_filtering(self, async_client):
        headers = await _login(async_client)
        mock_svc = _make_mock_embed_service()
        with patch("app.api.rag.embedding_service", mock_svc):
            resp = await async_client.get("/api/rag/search?q=test&threshold=0.99", headers=headers)
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_search_embedding_service_unavailable(self, async_client):
        headers = await _login(async_client)
        mock_svc = AsyncMock()
        mock_svc.embed_query = AsyncMock(side_effect=RuntimeError("Model not installed"))
        with patch("app.api.rag.embedding_service", mock_svc):
            resp = await async_client.get("/api/rag/search?q=test", headers=headers)
            assert resp.status_code == 503
