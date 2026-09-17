from unittest.mock import MagicMock

from assistente_telegram_voz import tts as tmod


def test_synthesize_retorna_bytes(monkeypatch):
    fake_client = MagicMock()
    fake_client.text_to_speech.convert.return_value = iter([b"aa", b"bb"])
    monkeypatch.setattr(tmod, "_client", lambda: fake_client)
    out = tmod.synthesize("ola")
    assert out == b"aabb"
    fake_client.text_to_speech.convert.assert_called_once()
