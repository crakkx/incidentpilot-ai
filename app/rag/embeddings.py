import hashlib
import math
import re


EMBEDDING_DIMENSIONS = 64

_TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9_-]+")

_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "i",
    "if",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "the",
    "to",
    "what",
    "when",
    "with",
}


def tokenize(text: str) -> list[str]:
    tokens = _TOKEN_PATTERN.findall(text.lower())

    return [
        token
        for token in tokens
        if token not in _STOPWORDS and len(token) > 1
    ]


def embed_text(text: str) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSIONS
    tokens = tokenize(text)

    if not tokens:
        return vector

    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], byteorder="big") % EMBEDDING_DIMENSIONS
        vector[index] += 1.0

    norm = math.sqrt(sum(value * value for value in vector))

    if norm == 0:
        return vector

    return [value / norm for value in vector]
