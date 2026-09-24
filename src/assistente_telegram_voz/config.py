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


def _int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        return int(raw)
    except ValueError as e:
        raise ValueError(f"Variável {name} deve ser um inteiro, recebido: {raw!r}") from e


def _csv_list(name: str, default: str = "") -> tuple[str, ...]:
    """Lê uma variável com itens separados por vírgula (ex.: 'a, b, c')."""
    raw = os.getenv(name, default)
    return tuple(item.strip() for item in raw.split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    openrouter_api_key: str
    openrouter_base_url: str
    llm_model: str
    openai_api_key: str
    transcribe_model: str
    vision_model: str
    vision_max_image_px: int
    vision_image_quality: int
    embedding_model: str
    stt_provider: str
    tts_provider: str
    elevenlabs_api_key: str
    elevenlabs_voice_id: str
    elevenlabs_model: str
    rag_dir: str
    chroma_dir: str
    rag_top_k: int
    system_prompt_path: str
    history_max_messages: int
    max_audio_seconds: int
    rag_admin_users: tuple[str, ...]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        telegram_bot_token=_req("TELEGRAM_BOT_TOKEN"),
        openrouter_api_key=_req("OPENROUTER_API_KEY"),
        openrouter_base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        llm_model=os.getenv("LLM_MODEL", "openai/gpt-5.6-luna"),
        openai_api_key=_req("OPENAI_API_KEY"),
        transcribe_model=os.getenv("TRANSCRIBE_MODEL", "gpt-4o-transcribe"),
        vision_model=os.getenv("VISION_MODEL", "openai/gpt-4o-mini"),
        vision_max_image_px=_int("VISION_MAX_IMAGE_PX", 1536),
        vision_image_quality=_int("VISION_IMAGE_QUALITY", 85),
        embedding_model=os.getenv("EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2"),
        # Seletores de provedor (cada um valida suas credenciais quando é usado).
        stt_provider=os.getenv("STT_PROVIDER", "openai").strip().lower(),
        tts_provider=os.getenv("TTS_PROVIDER", "elevenlabs").strip().lower(),
        # ElevenLabs deixou de ser obrigatório: só é exigido se TTS_PROVIDER=elevenlabs.
        elevenlabs_api_key=os.getenv("ELEVENLABS_API_KEY", ""),
        elevenlabs_voice_id=os.getenv("ELEVENLABS_VOICE_ID", ""),
        elevenlabs_model=os.getenv("ELEVENLABS_MODEL", "eleven_multilingual_v2"),
        rag_dir=os.getenv("RAG_DIR", "rag"),
        chroma_dir=os.getenv("CHROMA_DIR", "chroma_db"),
        rag_top_k=_int("RAG_TOP_K", 4),
        system_prompt_path=os.getenv("SYSTEM_PROMPT_PATH", "prompt/system.md"),
        history_max_messages=_int("HISTORY_MAX_MESSAGES", 10),
        max_audio_seconds=_int("MAX_AUDIO_SECONDS", 120),
        rag_admin_users=_csv_list("RAG_ADMIN_USERS"),
    )
