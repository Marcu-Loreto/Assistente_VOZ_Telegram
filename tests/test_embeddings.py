from unittest.mock import MagicMock

from assistente_telegram_voz import embeddings as emod


def test_embed_usa_modelo_e_retorna_listas(monkeypatch):
    fake_model = MagicMock()
    # encode devolve algo tipo numpy; simulamos com objeto que tem tolist()
    fake_model.encode.return_value = _FakeArray([[0.1, 0.2], [0.3, 0.4]])
    monkeypatch.setattr(emod, "_get_model", lambda: fake_model)
    out = emod.embed(["a", "b"])
    assert out == [[0.1, 0.2], [0.3, 0.4]]
    fake_model.encode.assert_called_once()


def test_embed_lista_vazia_nao_chama_modelo(monkeypatch):
    fake_model = MagicMock()
    monkeypatch.setattr(emod, "_get_model", lambda: fake_model)
    assert emod.embed([]) == []
    fake_model.encode.assert_not_called()


class _FakeArray:
    """Simula um array numpy com .tolist()."""

    def __init__(self, data):
        self._data = data

    def tolist(self):
        return self._data
