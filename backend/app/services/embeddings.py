"""Local multilingual embeddings via sentence-transformers.

Uses paraphrase-multilingual-MiniLM-L12-v2 (384-dim, supports Thai + English).
Model is lazy-loaded on first use.
"""
import logging
from functools import lru_cache
from typing import List

logger = logging.getLogger(__name__)

EMBEDDING_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIM = 384


@lru_cache(maxsize=1)
def _get_model():
    from sentence_transformers import SentenceTransformer

    logger.info(f"Loading embedding model: {EMBEDDING_MODEL_NAME}")
    return SentenceTransformer(EMBEDDING_MODEL_NAME)


def embed(text: str) -> List[float]:
    """Embed a single string to a 384-dim vector."""
    model = _get_model()
    vec = model.encode(text, normalize_embeddings=True, convert_to_numpy=True)
    return vec.tolist()


def embed_batch(texts: List[str]) -> List[List[float]]:
    """Embed a batch of strings."""
    model = _get_model()
    vecs = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
    return [v.tolist() for v in vecs]
