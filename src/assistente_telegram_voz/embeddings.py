import os
from functools import lru_cache

# Usa apenas o cache local do modelo, sem consultar o HuggingFace Hub a cada uso.
# Corta dezenas de requisições de rede por operação, reduzindo a latência do RAG.
# Pré-requisito: o modelo já deve estar baixado (feito no primeiro uso local e
# pré-baixado na imagem Docker). Definido antes de importar sentence-transformers.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

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
