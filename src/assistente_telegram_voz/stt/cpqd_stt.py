"""Provedor STT via CPQD (ASR).

Adaptado da solução original do CPQD (asr.py) ao cenário deste projeto: o áudio
chega como arquivo OGG/Opus do Telegram, então é convertido para WAV PCM 16 kHz
mono (o formato que o serviço lê) antes de ser enviado como corpo cru da requisição.

Fluxo: autentica (token bearer cacheado), envia o WAV para o endpoint de ASR com
o modelo de linguagem como query param, e extrai o texto da resposta. Um 401
dispara um único retry com token renovado. Silêncio (sem fala) volta como "".

Copyright da solução original: CPQD.
"""

from __future__ import annotations

import os

import requests

from ..cpqd_common import TIMEOUT_SECONDS, AuthConfig, CpqdAuth, CpqdError, run_ffmpeg

ASR_URL = os.environ.get("CPQD_ASR_URL", "https://asr.cpqd.com.br/asr-general")
ASR_LM = os.environ.get("CPQD_ASR_LM", "builtin:slm/general")

# WAV PCM 16 kHz mono little-endian: o formato aceito pelo asr-general.
_WAV_16K_MONO = [
    "-vn",
    "-ac", "1",
    "-ar", "16000",
    "-acodec", "pcm_s16le",
    "-f", "wav",
]


def _extract_text(payload: object) -> str:
    """Encontra o transcript numa resposta decodificada do ASR.

    O serviço responde em mais de um formato: lista de resultados, objeto único,
    alternativas ranqueadas, ou resultado aninhado em `result`. Sem texto = silêncio
    (string vazia), não erro.
    """
    if isinstance(payload, list):
        return _extract_text(payload[0]) if payload else ""
    if not isinstance(payload, dict):
        return ""
    alternatives = payload.get("alternatives")
    if isinstance(alternatives, list) and alternatives:
        first = alternatives[0]
        if isinstance(first, dict):
            return str(first.get("text") or "").strip()
    spoken = payload.get("text")
    if isinstance(spoken, str):
        return spoken.strip()
    result = payload.get("result")
    if result:
        return _extract_text(result)
    return ""


def _read_transcript(response: requests.Response) -> str:
    """Extrai o texto da resposta do ASR; corpo não-JSON é tratado como silêncio."""
    try:
        payload = response.json()
    except ValueError:
        return ""
    return _extract_text(payload)


class CpqdSTT:
    """Transcreve áudio (arquivo do Telegram) usando o ASR do CPQD."""

    def __init__(self) -> None:
        self._auth = CpqdAuth(AuthConfig("I2_ASR_USER", "I2_ASR_PASSWORD"))

    def transcribe(self, audio_path: str) -> str:
        with open(audio_path, "rb") as f:
            audio = f.read()
        if not audio:
            return ""
        wav = run_ffmpeg(audio, _WAV_16K_MONO, "audio.wav")

        response = self._request(self._auth.token(), wav)
        if response.status_code == 401:
            response = self._request(self._auth.token(force_refresh=True), wav)
        if response.status_code >= 400:
            raise CpqdError(f"ASR do CPQD respondeu {response.status_code}.")
        return _read_transcript(response)

    def _request(self, bearer: str, wav: bytes) -> requests.Response:
        """Envia o WAV como corpo cru; o modelo de linguagem vai como query param."""
        headers = {
            "Content-Type": "audio/wav",
            "Authorization": f"Bearer {bearer}",
            "Accept": "application/json",
        }
        try:
            return self._auth.session().post(
                ASR_URL, params={"lm": ASR_LM}, data=wav, headers=headers,
                timeout=TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            raise CpqdError(f"Falha na chamada de ASR do CPQD: {exc}") from exc
