"""Provedor TTS via ElevenLabs."""

from __future__ import annotations

from functools import lru_cache

from elevenlabs.client import ElevenLabs

from ..config import get_settings

# Opus em container OGG é o formato nativo de voice message do Telegram,
# então pedimos Opus direto ao ElevenLabs e evitamos reconversão.
OUTPUT_FORMAT = "opus_48000_64"


@lru_cache(maxsize=1)
def _client() -> ElevenLabs:
    key = get_settings().elevenlabs_api_key
    if not key:
        raise ValueError(
            "ELEVENLABS_API_KEY ausente: necessário para TTS_PROVIDER=elevenlabs."
        )
    return ElevenLabs(api_key=key)


class ElevenLabsTTS:
    """Converte texto em áudio (bytes Opus/OGG) via ElevenLabs."""

    def synthesize(self, text: str) -> bytes:
        s = get_settings()
        if not s.elevenlabs_voice_id:
            raise ValueError(
                "ELEVENLABS_VOICE_ID ausente: necessário para TTS_PROVIDER=elevenlabs."
            )
        audio = _client().text_to_speech.convert(
            voice_id=s.elevenlabs_voice_id,
            model_id=s.elevenlabs_model,
            text=text,
            output_format=OUTPUT_FORMAT,
        )
        return b"".join(audio)
