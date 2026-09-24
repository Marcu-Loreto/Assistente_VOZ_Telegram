"""Provedor STT via OpenAI (modelo de transcrição)."""

from __future__ import annotations

from functools import lru_cache

from openai import OpenAI

from ..config import get_settings


@lru_cache(maxsize=1)
def _client() -> OpenAI:
    key = get_settings().openai_api_key
    if not key:
        raise ValueError("OPENAI_API_KEY ausente: necessário para STT_PROVIDER=openai.")
    return OpenAI(api_key=key)


class OpenAISTT:
    """Transcreve áudio com o modelo de transcrição da OpenAI (forçado para pt)."""

    def transcribe(self, audio_path: str) -> str:
        s = get_settings()
        with open(audio_path, "rb") as f:
            resp = _client().audio.transcriptions.create(
                model=s.transcribe_model,
                file=f,
                language="pt",
            )
        return resp.text.strip()
