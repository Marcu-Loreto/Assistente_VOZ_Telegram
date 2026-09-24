"""Testes do seletor de provedores de voz (STT_PROVIDER / TTS_PROVIDER)."""

import importlib

import pytest

from assistente_telegram_voz import config


def _reload_dispatchers():
    """Recarrega os dispatchers para limpar o lru_cache de get_stt/get_tts."""
    from assistente_telegram_voz import stt, tts

    importlib.reload(stt)
    importlib.reload(tts)
    return stt, tts


def test_stt_seleciona_openai(monkeypatch):
    monkeypatch.setenv("STT_PROVIDER", "openai")
    config.get_settings.cache_clear()
    stt, _ = _reload_dispatchers()
    from assistente_telegram_voz.stt.openai_stt import OpenAISTT

    assert isinstance(stt.get_stt(), OpenAISTT)


def test_stt_seleciona_cpqd(monkeypatch):
    monkeypatch.setenv("STT_PROVIDER", "cpqd")
    config.get_settings.cache_clear()
    stt, _ = _reload_dispatchers()
    from assistente_telegram_voz.stt.cpqd_stt import CpqdSTT

    assert isinstance(stt.get_stt(), CpqdSTT)


def test_tts_seleciona_elevenlabs(monkeypatch):
    monkeypatch.setenv("TTS_PROVIDER", "elevenlabs")
    config.get_settings.cache_clear()
    _, tts = _reload_dispatchers()
    from assistente_telegram_voz.tts.elevenlabs_tts import ElevenLabsTTS

    assert isinstance(tts.get_tts(), ElevenLabsTTS)


def test_tts_seleciona_cpqd(monkeypatch):
    monkeypatch.setenv("TTS_PROVIDER", "cpqd")
    config.get_settings.cache_clear()
    _, tts = _reload_dispatchers()
    from assistente_telegram_voz.tts.cpqd_tts import CpqdTTS

    assert isinstance(tts.get_tts(), CpqdTTS)


def test_provider_invalido_erro_claro(monkeypatch):
    monkeypatch.setenv("STT_PROVIDER", "inexistente")
    config.get_settings.cache_clear()
    stt, _ = _reload_dispatchers()
    with pytest.raises(ValueError, match="STT_PROVIDER inválido"):
        stt.get_stt()


def test_cpqd_stt_extrai_texto_de_varios_formatos():
    """O parser tolera os formatos de resposta do ASR do CPQD (sem chamar a rede)."""
    from assistente_telegram_voz.stt.cpqd_stt import _extract_text

    assert _extract_text({"text": "ola mundo"}) == "ola mundo"
    assert _extract_text([{"text": "  na lista "}]) == "na lista"
    assert _extract_text({"alternatives": [{"text": "melhor"}]}) == "melhor"
    assert _extract_text({"result": {"text": "aninhado"}}) == "aninhado"
    assert _extract_text({}) == ""  # sem texto = silêncio
    assert _extract_text("resposta nao-json") == ""


def test_cpqd_stt_credenciais_ausentes_erro_claro(monkeypatch):
    """Sem I2_ASR_USER/PASSWORD, falha com mensagem clara ao pedir o token."""
    from assistente_telegram_voz.cpqd_common import CpqdError
    from assistente_telegram_voz.stt.cpqd_stt import CpqdSTT

    monkeypatch.delenv("I2_ASR_USER", raising=False)
    monkeypatch.delenv("I2_ASR_PASSWORD", raising=False)
    stt = CpqdSTT()
    with pytest.raises(CpqdError, match="I2_ASR_USER"):
        stt._auth.token()


def test_cpqd_tts_repair_wav_header():
    """Cabeçalho WAV com tamanhos 0xFFFFFFFF é corrigido para os tamanhos reais."""
    from assistente_telegram_voz.tts.cpqd_tts import repair_wav_header

    payload = b"\x01\x02\x03\x04\x05\x06" * 8  # 48 bytes de áudio
    # WAV realista: RIFF + WAVE + chunk 'fmt ' (16 bytes) + chunk 'data', com os
    # sizes de RIFF e data inválidos (0xFFFFFFFF), como o CPQD devolve.
    fmt_chunk = b"fmt " + (16).to_bytes(4, "little") + b"\x00" * 16
    broken = (
        b"RIFF" + b"\xff\xff\xff\xff" + b"WAVE"
        + fmt_chunk
        + b"data" + b"\xff\xff\xff\xff" + payload
    )
    fixed = repair_wav_header(broken)
    # data size = len(payload); RIFF size = len(arquivo) - 8.
    data_start = fixed.find(b"data") + 8
    assert fixed[data_start - 4 : data_start] == len(payload).to_bytes(4, "little")
    assert fixed[4:8] == (len(fixed) - 8).to_bytes(4, "little")
    # Um não-WAV é devolvido intacto.
    assert repair_wav_header(b"nao eh wav") == b"nao eh wav"


def test_cpqd_tts_credenciais_ausentes_erro_claro(monkeypatch):
    from assistente_telegram_voz.cpqd_common import CpqdError
    from assistente_telegram_voz.tts.cpqd_tts import CpqdTTS

    monkeypatch.delenv("I2_TTS_USER", raising=False)
    monkeypatch.delenv("I2_TTS_PASSWORD", raising=False)
    tts = CpqdTTS()
    with pytest.raises(CpqdError, match="I2_TTS_USER"):
        tts._auth.token()
