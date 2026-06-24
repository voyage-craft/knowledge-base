"""Embedding service for RAG using sentence-transformers.

Lazily loads the configured embedding model on first use.
Supports BAAI/bge-m3 (default) or any HuggingFace model via sentence-transformers.
"""

import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# Dedicated thread pool for embedding operations (scale to CPU cores)
import os
_embedding_executor = ThreadPoolExecutor(
    max_workers=min(8, os.cpu_count() or 4),
    thread_name_prefix="embedding",
)


class EmbeddingService:
    """Singleton embedding service with lazy model loading."""

    def __init__(self):
        self._model = None
        self._model_name: str | None = None
        self._lock = asyncio.Lock()

    async def _load_model(self, model_name: str | None = None):
        """Lazy-load the sentence-transformers model."""
        async with self._lock:
            if self._model and (model_name is None or model_name == self._model_name):
                return self._model

            name = model_name or await self._get_configured_model()
            logger.info("Loading embedding model: %s", name)

            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(name)
                self._model_name = name
                logger.info("Embedding model loaded: %s", name)
                return self._model
            except ImportError:
                logger.error("sentence-transformers not installed. Run: pip install sentence-transformers")
                raise RuntimeError(
                    "嵌入模型未安装。请运行: pip install sentence-transformers"
                )
            except Exception as e:
                logger.error("Failed to load embedding model: %s", e)
                raise RuntimeError(f"嵌入模型加载失败: {e}")

    async def _get_configured_model(self) -> str:
        """Get the embedding model name from system settings."""
        model = "BAAI/bge-m3"  # default
        try:
            from sqlalchemy import select
            from app.core.database import AsyncSessionLocal
            from app.models.system_settings import SystemSetting

            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(SystemSetting).where(SystemSetting.key == "embedding_model")
                )
                setting = result.scalar_one_or_none()
                if setting and setting.value:
                    model = setting.value
        except Exception:
            pass
        return model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts."""
        model = await self._load_model()
        # sentence-transformers encode runs in a thread — run in dedicated executor
        loop = asyncio.get_running_loop()
        embeddings = await loop.run_in_executor(
            _embedding_executor, lambda: model.encode(texts, normalize_embeddings=True).tolist()
        )
        return embeddings

    async def embed_query(self, text: str) -> list[float]:
        """Generate embedding for a single query text."""
        results = await self.embed([text])
        return results[0]

    def is_loaded(self) -> bool:
        return self._model is not None

    async def unload(self):
        """Unload the model to free memory."""
        self._model = None
        self._model_name = None


embedding_service = EmbeddingService()


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
