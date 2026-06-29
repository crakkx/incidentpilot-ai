def chunk_text(
    text: str,
    max_words: int = 80,
    overlap_words: int = 20,
) -> list[str]:
    cleaned_text = text.strip()

    if not cleaned_text:
        return []

    words = cleaned_text.split()

    if len(words) <= max_words:
        return [cleaned_text]

    chunks = []
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
