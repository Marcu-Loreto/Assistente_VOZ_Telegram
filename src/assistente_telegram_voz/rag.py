from functools import lru_cache

import chromadb
from openai import OpenAI

from .config import get_settings

COLLECTION_NAME = "knowledge"


@lru_cache(maxsize=1)
def _openai_client() -> OpenAI:
    return OpenAI(api_key=get_settings().openai_api_key)


@lru_cache(maxsize=1)
def get_collection():
    """Coleção ChromaDB persistida em disco (criada se não existir)."""
    s = get_settings()
    client = chromadb.PersistentClient(path=s.chroma_dir)
    return client.get_or_create_collection(COLLECTION_NAME)


def _embed(text: str) -> list[float]:
    s = get_settings()
    resp = _openai_client().embeddings.create(model=s.embedding_model, input=text)
    return resp.data[0].embedding


def retrieve(query: str, k: int | None = None) -> list[str]:
    """Recupera os `k` trechos mais relevantes para a pergunta na base RAG."""
    s = get_settings()
    k = k or s.rag_top_k
    emb = _embed(query)
    res = get_collection().query(query_embeddings=[emb], n_results=k)
    docs = res.get("documents") or [[]]
    return docs[0]
