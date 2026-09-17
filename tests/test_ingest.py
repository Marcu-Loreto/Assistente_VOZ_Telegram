from unittest.mock import MagicMock

from scripts import ingest


def test_embed_batch_uma_chamada_para_varios_textos():
    fake_client = MagicMock()
    fake_client.embeddings.create.return_value = MagicMock(
        data=[MagicMock(embedding=[0.1]), MagicMock(embedding=[0.2])]
    )
    out = ingest.embed_batch(["a", "b"], model="m", client=fake_client)
    assert out == [[0.1], [0.2]]
    # um único request para os dois textos, não um por texto
    fake_client.embeddings.create.assert_called_once_with(model="m", input=["a", "b"])


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
