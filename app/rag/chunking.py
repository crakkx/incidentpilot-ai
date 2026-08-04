DEFAULT_MAX_WORDS = 120
DEFAULT_OVERLAP_WORDS = 30


def chunk_text(
    text: str,
    max_words: int = DEFAULT_MAX_WORDS,
    overlap_words: int = DEFAULT_OVERLAP_WORDS,
) -> list[str]:
    cleaned_text = text.strip()

    if not cleaned_text:
        return []

    if max_words <= 0:
        raise ValueError("max_words must be positive")

    if overlap_words < 0:
        raise ValueError("overlap_words cannot be negative")

    if overlap_words >= max_words:
        raise ValueError(
            "overlap_words must be smaller than max_words"
        )

    words = cleaned_text.split()

    if len(words) <= max_words:
        return [cleaned_text]

    chunks: list[str] = []
    step = max_words - overlap_words
    start = 0

    while start < len(words):
        end = start + max_words
        chunk = " ".join(words[start:end])
        chunks.append(chunk)

        if end >= len(words):
            break

        start += step

    return chunks