import pytest
from assistente_telegram_voz.config import get_settings


def test_get_settings_carrega_valores(fake_env):
    s = get_settings()
    assert s.telegram_bot_token == "tg-test"
    assert s.llm_model == "openai/gpt-5.6-luna"
    assert s.openrouter_base_url.endswith("/v1")
    assert s.rag_top_k == 4
    assert s.history_max_messages == 10


def test_get_settings_falta_chave_obrigatoria(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN"):
        get_settings()


def test_get_settings_usa_default_quando_var_ausente(monkeypatch):
    monkeypatch.delenv("LLM_MODEL", raising=False)
    s = get_settings()
    assert s.llm_model == "openai/gpt-5.6-luna"


def test_get_settings_numero_malformado(monkeypatch):
    monkeypatch.setenv("RAG_TOP_K", "abc")
    with pytest.raises(ValueError, match="RAG_TOP_K"):
        get_settings()
