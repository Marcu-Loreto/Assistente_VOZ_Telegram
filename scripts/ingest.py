"""Ingestão da base RAG.

Lê os documentos da pasta configurada (RAG_DIR), fatia em chunks, gera embeddings
e popula a coleção do ChromaDB. Rodar com:

    uv run python -m scripts.ingest
"""

from pathlib import Path

from pypdf import PdfReader

from assistente_telegram_voz.config import get_settings
from assistente_telegram_voz.embeddings import embed
from assistente_telegram_voz.rag import get_collection


def chunk_text(text: str, size: int = 1000, overlap: int = 150) -> list[str]:
    """Divide o texto em pedaços de até `size` caracteres, com sobreposição."""
    if not text.strip():
        return []
    chunks, start = [], 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start = end - overlap if end - overlap > start else end
    return chunks


def _read_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def read_documents(rag_dir: str) -> list[dict]:
    """Lê .txt, .md e .pdf da pasta rag_dir, retornando {source, text} por arquivo."""
    docs = []
    for p in Path(rag_dir).rglob("*"):
        suffix = p.suffix.lower()
        if suffix in {".txt", ".md"}:
            docs.append({"source": str(p), "text": p.read_text(encoding="utf-8").strip()})
        elif suffix == ".pdf":
            docs.append({"source": str(p), "text": _read_pdf(p).strip()})
    return docs


def _batched(seq: list, size: int):
    """Divide uma lista em lotes de até `size` itens."""
    for start in range(0, len(seq), size):
        yield seq[start : start + size]


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Gera embeddings locais para uma lista de textos (sem chamadas de rede)."""
    return embed(texts)


EMBED_BATCH_SIZE = 128
UPSERT_BATCH_SIZE = 512


def main() -> None:
    s = get_settings()
    collection = get_collection()
    documents = read_documents(s.rag_dir)

    # Achata todos os documentos em chunks com seus ids e metadados.
    ids, texts, metadatas = [], [], []
    for doc in documents:
        for i, chunk in enumerate(chunk_text(doc["text"])):
            ids.append(f"{doc['source']}#{i}")
            texts.append(chunk)
            metadatas.append({"source": doc["source"]})

    if not ids:
        print("Nenhum chunk para indexar. Verifique a pasta de documentos.")
        return

    # Embeddings em lote (uma chamada por lote, não por chunk).
    embeddings: list[list[float]] = []
    for batch in _batched(texts, EMBED_BATCH_SIZE):
        embeddings.extend(embed_batch(batch))
        print(f"  embeddings gerados: {len(embeddings)}/{len(texts)}")

    # Upsert em lote no ChromaDB.
    for start in range(0, len(ids), UPSERT_BATCH_SIZE):
        end = start + UPSERT_BATCH_SIZE
        collection.upsert(
            ids=ids[start:end],
            documents=texts[start:end],
            embeddings=embeddings[start:end],
            metadatas=metadatas[start:end],
        )

    print(f"Indexados {len(ids)} chunks de {len(documents)} documentos.")


if __name__ == "__main__":
    main()
