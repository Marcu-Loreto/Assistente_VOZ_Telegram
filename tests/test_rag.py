from unittest.mock import MagicMock

from assistente_telegram_voz import rag as ragmod


def test_retrieve_retorna_documentos(monkeypatch):
    fake_collection = MagicMock()
    fake_collection.query.return_value = {"documents": [["trecho1", "trecho2"]]}
    monkeypatch.setattr(ragmod, "get_collection", lambda: fake_collection)
    monkeypatch.setattr(ragmod, "_embed", lambda text: [0.1, 0.2, 0.3])
    out = ragmod.retrieve("pergunta", k=2)
    assert out == ["trecho1", "trecho2"]
    fake_collection.query.assert_called_once()


def test_retrieve_sem_resultado_lista_vazia(monkeypatch):
    fake_collection = MagicMock()
    fake_collection.query.return_value = {"documents": [[]]}
    monkeypatch.setattr(ragmod, "get_collection", lambda: fake_collection)
    monkeypatch.setattr(ragmod, "_embed", lambda text: [0.1])
    assert ragmod.retrieve("x", k=4) == []
