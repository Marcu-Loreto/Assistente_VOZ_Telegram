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


# ------------------------------------------------------------------ gestão

def list_documents() -> list[dict]:
    """Lista os documentos indexados, agrupados pela fonte (metadata `source`).

    Cada documento vira uma entrada {"source": str, "chunks": int}, ordenada por
    source. Usado pela tela de gestão do RAG para mostrar o que está no banco
    vetorial (não os arquivos em disco, mas o que realmente foi indexado).
    """
    collection = get_collection()
    # Busca só os metadados de todos os itens (sem embeddings/documentos, mais leve).
    got = collection.get(include=["metadatas"])
    counts: dict[str, int] = {}
    for meta in got.get("metadatas") or []:
        source = (meta or {}).get("source", "(sem fonte)")
        counts[source] = counts.get(source, 0) + 1
    return [
        {"source": source, "chunks": counts[source]}
        for source in sorted(counts)
    ]


def delete_document(source: str) -> int:
    """Remove do banco vetorial todos os chunks de um documento (por `source`).

    Retorna quantos chunks foram removidos. Não mexe em arquivos em disco — a
    remoção do arquivo (quando desejada) é responsabilidade de quem chama.
    """
    collection = get_collection()
    before = collection.count()
    collection.delete(where={"source": source})
    return before - collection.count()
