"""Tests for embedding service: cosine similarity, singleton behavior, error handling."""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock

from app.services.embedding_service import EmbeddingService, cosine_similarity


# ── Cosine Similarity ───────────────────────────────────────────────────

class TestCosineSimilarity:

    def test_identical_vectors(self):
        a = [1.0, 0.0, 0.0]
        assert cosine_similarity(a, a) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(-1.0)

    def test_similar_vectors(self):
        a = [1.0, 1.0, 0.0]
        b = [1.0, 0.9, 0.1]
        score = cosine_similarity(a, b)
        assert 0.9 < score < 1.0

    def test_empty_vectors(self):
        assert cosine_similarity([], []) == 0.0

    def test_different_lengths(self):
        assert cosine_similarity([1.0, 2.0], [1.0]) == 0.0

    def test_zero_vector(self):
        assert cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0

    def test_both_zero_vectors(self):
        assert cosine_similarity([0.0, 0.0], [0.0, 0.0]) == 0.0

    def test_none_input(self):
        assert cosine_similarity(None, [1.0]) == 0.0
        assert cosine_similarity([1.0], None) == 0.0

    def test_high_dimensional(self):
        """Verify correctness with realistic embedding dimensions."""
        import random
        random.seed(42)
        a = [random.gauss(0, 1) for _ in range(1024)]
        b = [random.gauss(0, 1) for _ in range(1024)]
        score = cosine_similarity(a, b)
        assert -1.0 <= score <= 1.0


# ── EmbeddingService Unit Tests ─────────────────────────────────────────

class TestEmbeddingService:

    def test_initial_state(self):
        svc = EmbeddingService()
        assert svc.is_loaded() is False

    @pytest.mark.asyncio
    async def test_unload(self):
        svc = EmbeddingService()
        svc._model = MagicMock()
        svc._model_name = "test"
        await svc.unload()
        assert svc._model is None
        assert svc._model_name is None

    @pytest.mark.asyncio
    async def test_embed_with_mock_model(self):
        """Test embed() with a mocked sentence-transformers model."""
        svc = EmbeddingService()
        import numpy as np
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]])
        svc._model = mock_model
        svc._model_name = "test-model"

        result = await svc.embed(["hello", "world"])
        assert len(result) == 2
        assert len(result[0]) == 3
        mock_model.encode.assert_called_once()

    @pytest.mark.asyncio
    async def test_embed_query_delegates_to_embed(self):
        svc = EmbeddingService()
        import numpy as np
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([[0.5, 0.6, 0.7]])
        svc._model = mock_model
        svc._model_name = "test-model"

        result = await svc.embed_query("single query")
        assert len(result) == 3
        assert result[0] == pytest.approx(0.5)

    @pytest.mark.asyncio
    async def test_load_model_import_error(self):
        """When sentence-transformers is not installed, should raise RuntimeError."""
        svc = EmbeddingService()
        with patch.dict("sys.modules", {"sentence_transformers": None}):
            with pytest.raises(RuntimeError, match="嵌入模型未安装"):
                await svc._load_model("nonexistent-model")
