from unittest.mock import MagicMock, mock_open, patch

from assistente_telegram_voz.stt import openai_stt


def test_transcribe_chama_client_e_retorna_texto(monkeypatch):
    fake_client = MagicMock()
    fake_client.audio.transcriptions.create.return_value = MagicMock(text="ola mundo")
    monkeypatch.setattr(openai_stt, "_client", lambda: fake_client)
    with patch("builtins.open", mock_open(read_data=b"audio")):
        out = openai_stt.OpenAISTT().transcribe("/tmp/a.ogg")
    assert out == "ola mundo"
    fake_client.audio.transcriptions.create.assert_called_once()
