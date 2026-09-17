import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


def _req(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise ValueError(f"Variável obrigatória ausente: {name}")
    return v


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    openrouter_api_key: str
    openrouter_base_url: str
    llm_model: str
    openai_api_key: str
    transcribe_model: str
    embedding_model: str
    elevenlabs_api_key: str
    elevenlabs_voice_id: str
    elevenlabs_model: str
    rag_dir: str
    chroma_dir: str
    rag_top_k: int
    system_prompt_path: str
    history_max_messages: int
    max_audio_seconds: int


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        telegram_bot_token=_req("TELEGRAM_BOT_TOKEN"),
        openrouter_api_key=_req("OPENROUTER_API_KEY"),
        openrouter_base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        llm_model=os.getenv("LLM_MODEL", "openai/gpt-5.6-luna"),
        openai_api_key=_req("OPENAI_API_KEY"),
        transcribe_model=os.getenv("TRANSCRIBE_MODEL", "gpt-4o-transcribe"),
        embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        elevenlabs_api_key=_req("ELEVENLABS_API_KEY"),
        elevenlabs_voice_id=_req("ELEVENLABS_VOICE_ID"),
        elevenlabs_model=os.getenv("ELEVENLABS_MODEL", "eleven_multilingual_v2"),
        rag_dir=os.getenv("RAG_DIR", "rag"),
        chroma_dir=os.getenv("CHROMA_DIR", "chroma_db"),
        rag_top_k=int(os.getenv("RAG_TOP_K", "4")),
        system_prompt_path=os.getenv("SYSTEM_PROMPT_PATH", "prompt/system.md"),
        history_max_messages=int(os.getenv("HISTORY_MAX_MESSAGES", "10")),
        max_audio_seconds=int(os.getenv("MAX_AUDIO_SECONDS", "120")),
    )
