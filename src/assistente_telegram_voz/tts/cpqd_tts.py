"""Provedor TTS via CPQD.

Adaptado da solução original do CPQD (tts.py) ao cenário deste projeto. O serviço
devolve WAV; o Telegram usa OGG/Opus para voice message. Então: autentica (token
bearer cacheado), pede a síntese em JSON, conserta o cabeçalho WAV que o serviço
manda com tamanhos inválidos (0xFFFFFFFF) e converte o WAV para OGG/Opus via ffmpeg.

Copyright da solução original: CPQD.
"""

from __future__ import annotations

import os
from typing import Any

import requests

from ..cpqd_common import TIMEOUT_SECONDS, AuthConfig, CpqdAuth, CpqdError, run_ffmpeg

TTS_URL = os.environ.get("CPQD_TTS_URL", "https://tts.cpqd.com.br/rest/v2/synthesize")
TTS_VOICE = os.environ.get("CPQD_TTS_VOICE", "CPQD-ADRIANA-PT-NAT-NEU-BAI-PRF")

# OGG/Opus é o formato nativo de voice message do Telegram.
_OGG_OPUS = ["-vn", "-ac", "1", "-c:a", "libopus", "-f", "ogg"]


def repair_wav_header(audio: bytes) -> bytes:
    """Escreve os tamanhos reais num WAV cujo cabeçalho diz não conhecê-los.

    O serviço do CPQD responde com os campos de tamanho `RIFF` e `data` em
    0xFFFFFFFF (marcador de stream de tamanho desconhecido), mesmo sem streaming.
    O áudio está correto; só o cabeçalho não. Sem corrigir, um decodificador pode
    rejeitar o arquivo. Um cabeçalho já correto é devolvido intacto.
    """
    header_size = 44
    if len(audio) < header_size or audio[:4] != b"RIFF" or audio[8:12] != b"WAVE":
        return audio
    marker = audio.find(b"data", 12)
    if marker < 0:
        return audio

    payload_start = marker + 8
    payload_size = len(audio) - payload_start
    declared = int.from_bytes(audio[payload_start - 4 : payload_start], "little")
    if declared == payload_size:
        return audio

    fixed = bytearray(audio)
    fixed[4:8] = (len(audio) - 8).to_bytes(4, "little")
    fixed[payload_start - 4 : payload_start] = payload_size.to_bytes(4, "little")
    return bytes(fixed)


class CpqdTTS:
    """Sintetiza voz com o CPQD e devolve OGG/Opus pronto para o Telegram."""

    def __init__(self) -> None:
        self._auth = CpqdAuth(AuthConfig("I2_TTS_USER", "I2_TTS_PASSWORD"))

    def synthesize(self, text: str) -> bytes:
        response = self._request(self._auth.token(), text)
        if response.status_code == 401:
            response = self._request(self._auth.token(force_refresh=True), text)
        if response.status_code >= 400:
            raise CpqdError(f"TTS do CPQD respondeu {response.status_code}.")
        if not response.content:
            raise CpqdError("TTS do CPQD devolveu áudio vazio.")

        wav = repair_wav_header(response.content)
        # Converte o WAV do CPQD para OGG/Opus (voice message do Telegram).
        return run_ffmpeg(wav, _OGG_OPUS, "voz.ogg")

    def _request(self, bearer: str, text: str) -> requests.Response:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {bearer}",
            "Accept": "application/octet-stream",
        }
        payload: dict[str, Any] = {
            "text": text,
            "voice": TTS_VOICE,
            "use_streaming": False,
        }
        try:
            return self._auth.session().post(
                TTS_URL, json=payload, headers=headers, timeout=TIMEOUT_SECONDS
            )
        except requests.RequestException as exc:
            raise CpqdError(f"Falha na chamada de TTS do CPQD: {exc}") from exc
