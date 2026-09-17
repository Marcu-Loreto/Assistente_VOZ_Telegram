from functools import lru_cache

from elevenlabs.client import ElevenLabs

from .config import get_settings

# Opus em container OGG é o formato nativo de voice message do Telegram,
# então pedimos Opus direto ao ElevenLabs e evitamos reconversão.
OUTPUT_FORMAT = "opus_48000_64"


@lru_cache(maxsize=1)
def _client() -> ElevenLabs:
    return ElevenLabs(api_key=get_settings().elevenlabs_api_key)


def synthesize(text: str) -> bytes:
    """Converte texto em áudio (bytes Opus/OGG) via ElevenLabs."""
    s = get_settings()
    audio = _client().text_to_speech.convert(
        voice_id=s.elevenlabs_voice_id,
        model_id=s.elevenlabs_model,
        text=text,
        output_format=OUTPUT_FORMAT,
    )
    return b"".join(audio)
