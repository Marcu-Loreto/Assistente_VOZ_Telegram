from functools import lru_cache

from .config import get_settings


@lru_cache(maxsize=1)
def _get_model():
    """Carrega o modelo de embeddings local uma única vez (custo alto no primeiro uso)."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(get_settings().embedding_model)


def embed(texts: list[str]) -> list[list[float]]:
    """Gera embeddings locais para uma lista de textos. Não faz chamadas de rede."""
    if not texts:
        return []
    vectors = _get_model().encode(texts, convert_to_numpy=True)
    return vectors.tolist()
