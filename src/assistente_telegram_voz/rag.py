from functools import lru_cache

import chromadb

from .config import get_settings
from .embeddings import embed

COLLECTION_NAME = "knowledge"


@lru_cache(maxsize=1)
def get_collection():
    """Coleção ChromaDB persistida em disco (criada se não existir)."""
    s = get_settings()
    client = chromadb.PersistentClient(path=s.chroma_dir)
    return client.get_or_create_collection(COLLECTION_NAME)


def _embed(text: str) -> list[float]:
    """Embedding local de um único texto."""
    return embed([text])[0]


def retrieve(query: str, k: int | None = None) -> list[str]:
    """Recupera os `k` trechos mais relevantes para a pergunta na base RAG."""
    s = get_settings()
    k = k or s.rag_top_k
    emb = _embed(query)
    res = get_collection().query(query_embeddings=[emb], n_results=k)
    docs = res.get("documents") or [[]]
    return docs[0]
