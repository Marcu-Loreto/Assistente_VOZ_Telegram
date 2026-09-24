"""Text-to-speech (texto -> voz) com seleção de provedor.

A escolha do provedor é feita por `TTS_PROVIDER` no `.env` (ex.: `elevenlabs`,
`cpqd`). O resto do código só chama `synthesize(text)`, que roteia para a
implementação selecionada.

Adicionar um provedor novo:
1. Crie um módulo em `tts/` com uma classe que implemente `TextToSpeech`.
2. Registre-o em `_PROVIDERS` no dispatcher abaixo.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Protocol

from ..config import get_settings


class TextToSpeech(Protocol):
    """Contrato de um provedor de TTS."""

    def synthesize(self, text: str) -> bytes:
        """Converte `text` em áudio e retorna os bytes (formato pronto p/ Telegram)."""
        ...


# provider -> factory. Import tardio para não carregar o SDK de um provedor que
# não está em uso (ex.: não importar o ElevenLabs se TTS=cpqd).
def _elevenlabs() -> TextToSpeech:
    from .elevenlabs_tts import ElevenLabsTTS

    return ElevenLabsTTS()


def _cpqd() -> TextToSpeech:
    from .cpqd_tts import CpqdTTS

    return CpqdTTS()


_PROVIDERS = {
    "elevenlabs": _elevenlabs,
    "cpqd": _cpqd,
}


@lru_cache(maxsize=1)
def get_tts() -> TextToSpeech:
    """Devolve o provedor de TTS configurado em `TTS_PROVIDER`."""
    name = get_settings().tts_provider
    factory = _PROVIDERS.get(name)
    if factory is None:
        raise ValueError(
            f"TTS_PROVIDER inválido: {name!r}. "
            f"Opções: {', '.join(sorted(_PROVIDERS))}."
        )
    return factory()


def synthesize(text: str) -> bytes:
    """Sintetiza voz a partir de texto usando o provedor de TTS selecionado."""
    return get_tts().synthesize(text)
