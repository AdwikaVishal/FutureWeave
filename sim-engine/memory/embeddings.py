"""
Embedding service for FutureWeave memory system.
Generates embeddings for simulation context, decisions, and user profiles.
"""
import json
import logging
import hashlib
from typing import List, Optional

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self._model = None

    def _lazy_load(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer("all-MiniLM-L6-v2")
                logger.info("[Embeddings] Loaded sentence-transformers model")
            except ImportError:
                logger.warning("[Embeddings] sentence-transformers not available — using hash-based embeddings")
                self._model = None

    def embed(self, text: str) -> List[float]:
        self._lazy_load()
        if self._model:
            return self._model.encode(text).tolist()
        return self._hash_embed(text)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        self._lazy_load()
        if self._model:
            return self._model.encode(texts).tolist()
        return [self._hash_embed(t) for t in texts]

    def _hash_embed(self, text: str) -> List[float]:
        h = hashlib.sha256(text.encode()).hexdigest()
        seed = int(h[:8], 16)
        import random as rng
        rng.seed(seed)
        vec = [rng.gauss(0, 1) for _ in range(self.dimension)]
        magnitude = sum(x*x for x in vec) ** 0.5
        return [x / magnitude for x in vec]


_default_service = None


def get_embedding_service() -> EmbeddingService:
    global _default_service
    if _default_service is None:
        _default_service = EmbeddingService()
    return _default_service


def embed_text(text: str) -> List[float]:
    return get_embedding_service().embed(text)


def embed_batch(texts: List[str]) -> List[List[float]]:
    return get_embedding_service().embed_batch(texts)
