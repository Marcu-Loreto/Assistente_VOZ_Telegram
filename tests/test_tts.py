from unittest.mock import MagicMock

from assistente_telegram_voz.tts import elevenlabs_tts


def test_synthesize_retorna_bytes(monkeypatch):
    fake_client = MagicMock()
    fake_client.text_to_speech.convert.return_value = iter([b"aa", b"bb"])
    monkeypatch.setattr(elevenlabs_tts, "_client", lambda: fake_client)
    # ELEVENLABS_VOICE_ID vem do fake_env (conftest), então o provider não aborta.
    out = elevenlabs_tts.ElevenLabsTTS().synthesize("ola")
    assert out == b"aabb"
    fake_client.text_to_speech.convert.assert_called_once()
