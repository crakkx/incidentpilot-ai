import os
from functools import lru_cache

from sentence_transformers import SentenceTransformer

from app.core.config import settings


os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

EMBEDDING_DIMENSIONS = settings.embedding_dimensions


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    return SentenceTransformer(
        settings.embedding_model_name,
        device="cpu",
    )


def _validate_embedding(embedding: list[float]) -> list[float]:
    if len(embedding) != EMBEDDING_DIMENSIONS:
        raise ValueError(
            f"Expected embedding dimension {EMBEDDING_DIMENSIONS}, "
            f"got {len(embedding)}."
        )

    return embedding


def embed_text(text: str) -> list[float]:
    embeddings = embed_texts([text])

    if not embeddings:
        return [0.0] * EMBEDDING_DIMENSIONS

    return embeddings[0]


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    cleaned_texts = [
        text.strip()
        for text in texts
    ]

    model = get_embedding_model()

    embeddings = model.encode(
        cleaned_texts,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )

    results = []

    for embedding in embeddings:
        values = [
            float(value)
            for value in embedding.tolist()
        ]

        results.append(_validate_embedding(values))

    return results