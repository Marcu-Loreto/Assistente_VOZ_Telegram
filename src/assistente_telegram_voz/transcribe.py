from functools import lru_cache

from openai import OpenAI

from .config import get_settings


@lru_cache(maxsize=1)
def _client() -> OpenAI:
    return OpenAI(api_key=get_settings().openai_api_key)


def transcribe(audio_path: str) -> str:
    """Transcreve um arquivo de áudio para texto usando o modelo de transcrição."""
    s = get_settings()
    with open(audio_path, "rb") as f:
        resp = _client().audio.transcriptions.create(
            model=s.transcribe_model,
            file=f,
            language="pt",
        )
    return resp.text.strip()
