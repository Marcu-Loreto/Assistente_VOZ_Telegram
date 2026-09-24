"""Compatibilidade: `transcribe` agora vive no pacote `stt` (seleção de provedor).

Mantido para não quebrar imports antigos. Novos usos devem importar de
`assistente_telegram_voz.stt`.
"""

from .stt import transcribe

__all__ = ["transcribe"]
