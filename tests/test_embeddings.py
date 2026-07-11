from app.rag.embeddings import EMBEDDING_DIMENSIONS, embed_text


def test_real_embedding_dimension():
    embedding = embed_text("payments failing after deployment")

    assert len(embedding) == EMBEDDING_DIMENSIONS
    assert EMBEDDING_DIMENSIONS == 384
    assert any(value != 0 for value in embedding)
