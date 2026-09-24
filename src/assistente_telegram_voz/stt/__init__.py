"""Speech-to-text (voz -> texto) com seleção de provedor.

A escolha do provedor é feita por `STT_PROVIDER` no `.env` (ex.: `openai`, `cpqd`).
O resto do código não precisa saber qual provedor está ativo: basta chamar
`transcribe(audio_path)`, que roteia para a implementação selecionada.

Adicionar um provedor novo:
1. Crie um módulo em `stt/` com uma classe que implemente `SpeechToText`.
2. Registre-o em `_PROVIDERS` no dispatcher abaixo.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Protocol

from ..config import get_settings


class SpeechToText(Protocol):
    """Contrato de um provedor de STT."""

    def transcribe(self, audio_path: str) -> str:
        """Transcreve o arquivo de áudio em `audio_path` e retorna o texto."""
        ...


# provider -> factory. Import tardio dentro das factories para não carregar o SDK
# de um provedor que não está em uso (ex.: não importar o CPQD se STT=openai).
def _openai() -> SpeechToText:
    from .openai_stt import OpenAISTT

    return OpenAISTT()


def _cpqd() -> SpeechToText:
    from .cpqd_stt import CpqdSTT

    return CpqdSTT()


_PROVIDERS = {
    "openai": _openai,
    "cpqd": _cpqd,
}


@lru_cache(maxsize=1)
def get_stt() -> SpeechToText:
    """Devolve o provedor de STT configurado em `STT_PROVIDER`."""
    name = get_settings().stt_provider
    factory = _PROVIDERS.get(name)
    if factory is None:
        raise ValueError(
            f"STT_PROVIDER inválido: {name!r}. "
            f"Opções: {', '.join(sorted(_PROVIDERS))}."
        )
    return factory()


def transcribe(audio_path: str) -> str:
    """Transcreve um áudio usando o provedor de STT selecionado."""
    return get_stt().transcribe(audio_path)
