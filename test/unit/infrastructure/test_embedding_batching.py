from types import SimpleNamespace

from app.infrastructure.embeddings.embedding_provider import EmbeddingProvider


def test_embed_documents_splits_requests_by_batch_size():
    provider = EmbeddingProvider.__new__(EmbeddingProvider)
    provider._batch_size = 128
    sizes: list[int] = []

    def fake_create(texts: list[str]) -> list[list[float]]:
        sizes.append(len(texts))
        return [[0.0] for _ in texts]

    provider._create_embeddings = fake_create  # type: ignore[method-assign]
    result = EmbeddingProvider.embed_documents(provider, ["x"] * 300)
    assert len(result) == 300
    assert sizes == [128, 128, 44]


def test_embed_documents_empty():
    provider = SimpleNamespace(_batch_size=10)
    assert EmbeddingProvider.embed_documents(provider, []) == []  # type: ignore[arg-type]
