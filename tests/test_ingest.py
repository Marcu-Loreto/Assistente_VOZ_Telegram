from scripts import ingest


def test_embed_batch_usa_embeddings_locais(monkeypatch):
    chamadas = {}

    def fake_embed(texts):
        chamadas["texts"] = texts
        return [[0.1], [0.2]]

    monkeypatch.setattr(ingest, "embed", fake_embed)
    out = ingest.embed_batch(["a", "b"])
    assert out == [[0.1], [0.2]]
    assert chamadas["texts"] == ["a", "b"]


def test_batched_divide_em_lotes():
    assert list(ingest._batched([1, 2, 3, 4, 5], 2)) == [[1, 2], [3, 4], [5]]


def test_chunk_text_divide_por_tamanho():
    texto = "a" * 2500
    chunks = ingest.chunk_text(texto, size=1000, overlap=0)
    assert len(chunks) == 3
    assert all(len(c) <= 1000 for c in chunks)


def test_read_documents_le_txt_e_md(tmp_path):
    (tmp_path / "a.txt").write_text("conteudo txt", encoding="utf-8")
    (tmp_path / "b.md").write_text("conteudo md", encoding="utf-8")
    (tmp_path / "ignora.png").write_bytes(b"\x89PNG")
    docs = ingest.read_documents(str(tmp_path))
    textos = sorted(d["text"] for d in docs)
    assert textos == ["conteudo md", "conteudo txt"]
