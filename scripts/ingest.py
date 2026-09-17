"""Ingestão da base RAG.

Lê os documentos da pasta configurada (RAG_DIR), fatia em chunks, gera embeddings
e popula a coleção do ChromaDB. Rodar com:

    uv run python -m scripts.ingest
"""

from pathlib import Path

from pypdf import PdfReader

from assistente_telegram_voz.config import get_settings
from assistente_telegram_voz.rag import _openai_client, get_collection


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


def main() -> None:
    s = get_settings()
    collection = get_collection()
    client = _openai_client()
    documents = read_documents(s.rag_dir)
    ids, texts, embeddings, metadatas = [], [], [], []
    for doc in documents:
        for i, chunk in enumerate(chunk_text(doc["text"])):
            emb = client.embeddings.create(model=s.embedding_model, input=chunk).data[0].embedding
            ids.append(f"{doc['source']}#{i}")
            texts.append(chunk)
            embeddings.append(emb)
            metadatas.append({"source": doc["source"]})
    if ids:
        collection.upsert(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas)
    print(f"Indexados {len(ids)} chunks de {len(documents)} documentos.")


if __name__ == "__main__":
    main()
