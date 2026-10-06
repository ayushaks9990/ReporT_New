"""CPU semantic embeddings; the model cache contains weights, not dataset vectors."""
from __future__ import annotations

import math
import threading

from backend.config import settings


EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIMENSIONS = 384
INDEX_VERSION = "minilm-records-v1"
_model = None
_model_lock = threading.Lock()


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    # Bound CPU and memory, including simultaneous uploads and report requests.
    with _model_lock:
        global _model
        if _model is None:
            from fastembed import TextEmbedding

            _model = TextEmbedding(
                model_name=EMBEDDING_MODEL,
                cache_dir=str(settings.embedding_cache_dir),
                threads=settings.embedding_threads,
                local_files_only=settings.embedding_local_files_only,
            )
        vectors = list(_model.embed(texts, batch_size=settings.embedding_batch_size))
    if len(vectors) != len(texts):
        raise ValueError("Embedding model returned an unexpected number of vectors")
    result = []
    for vector in vectors:
        values = [float(value) for value in vector]
        if len(values) != EMBEDDING_DIMENSIONS or not all(math.isfinite(value) for value in values):
            raise ValueError("Embedding model returned an invalid vector")
        norm = math.sqrt(sum(value * value for value in values))
        if norm <= 0:
            raise ValueError("Embedding model returned a zero vector")
        result.append([value / norm for value in values])
    return result


if __name__ == "__main__":
    # Run during the Docker build, so Render startup never downloads model files.
    embed_texts(["Sales and marketing business performance"])
    print(f"Embedding model ready: {EMBEDDING_MODEL} ({EMBEDDING_DIMENSIONS} dimensions)")
