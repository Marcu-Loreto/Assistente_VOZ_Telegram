import pytest


@pytest.fixture(autouse=True)
def fake_env(monkeypatch):
    """Injeta variáveis de ambiente falsas para os testes não dependerem do .env real."""
    env = {
        "TELEGRAM_BOT_TOKEN": "tg-test",
        "OPENROUTER_API_KEY": "or-test",
        "OPENROUTER_BASE_URL": "https://openrouter.ai/api/v1",
        "LLM_MODEL": "openai/gpt-5.6-luna",
        "OPENAI_API_KEY": "oa-test",
        "TRANSCRIBE_MODEL": "gpt-4o-transcribe",
        "EMBEDDING_MODEL": "text-embedding-3-small",
        "ELEVENLABS_API_KEY": "el-test",
        "ELEVENLABS_VOICE_ID": "Qrdut83w0Cr152Yb4Xn3",
        "ELEVENLABS_MODEL": "eleven_multilingual_v2",
        "RAG_DIR": "rag",
        "CHROMA_DIR": "chroma_db",
        "RAG_TOP_K": "4",
        "SYSTEM_PROMPT_PATH": "prompt/system.md",
        "HISTORY_MAX_MESSAGES": "10",
        "MAX_AUDIO_SECONDS": "120",
    }
    for k, v in env.items():
        monkeypatch.setenv(k, v)
