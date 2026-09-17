# Assistente Conversacional por Voz — Plano de Implementação

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (ou superpowers:subagent-driven-development) para implementar este plano task-by-task.

**Goal:** Bot do Telegram especializado por RAG que responde em texto quando recebe texto e em voz (ElevenLabs) quando recebe voz, usando `gpt-5.6-luna` via OpenRouter.

**Architecture:** Processo Python de longa duração (polling do Telegram). Módulos de responsabilidade única em `src/assistente_telegram_voz/`. RAG local com ChromaDB persistido; ingestão separada do runtime. Memória de conversa em RAM por chat. Toda chamada externa é mockada nos testes (TDD).

**Tech Stack:** Python 3.12, uv, python-telegram-bot, openai (client apontando OpenRouter p/ LLM e OpenAI p/ transcrição+embeddings), elevenlabs, chromadb, pypdf, python-dotenv, pytest.

---

## Task 0: Setup do projeto e dependências

**Files:**
- Modify: `pyproject.toml`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

**Step 1:** Adicionar dependências de runtime:
```bash
uv add python-telegram-bot openai elevenlabs chromadb pypdf python-dotenv
```

**Step 2:** Adicionar dependências de dev:
```bash
uv add --dev pytest
```

**Step 3:** Criar `tests/conftest.py` com fixtures base (env vars falsas p/ testes):
```python
import os
import pytest

@pytest.fixture(autouse=True)
def fake_env(monkeypatch):
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
```

**Step 4:** Verificar instalação:
```bash
uv run pytest --collect-only
```
Expected: coleta 0 testes sem erro de import.

**Step 5:** Commit:
```bash
git add pyproject.toml uv.lock tests/
git commit -m "chore: dependências e setup de testes"
```

---

## Task 1: config.py — carregar e validar .env

**Files:**
- Create: `src/assistente_telegram_voz/config.py`
- Test: `tests/test_config.py`

**Step 1: Teste que falha**
```python
# tests/test_config.py
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
        get_settings.cache_clear()
        get_settings()
```

**Step 2: Rodar e ver falhar**
Run: `uv run pytest tests/test_config.py -v` → FAIL (módulo não existe).

**Step 3: Implementar**
```python
# src/assistente_telegram_voz/config.py
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
```

**Step 4: Rodar e ver passar**
Run: `uv run pytest tests/test_config.py -v` → PASS.

**Step 5: Commit**
```bash
git add src/assistente_telegram_voz/config.py tests/test_config.py
git commit -m "feat: config.py com carga e validação de .env"
```

---

## Task 2: memory.py — histórico por chat em RAM

**Files:**
- Create: `src/assistente_telegram_voz/memory.py`
- Test: `tests/test_memory.py`

**Step 1: Teste que falha**
```python
# tests/test_memory.py
from assistente_telegram_voz.memory import ConversationMemory

def test_append_e_get_isolado_por_chat():
    m = ConversationMemory(max_messages=4)
    m.append(1, "user", "oi")
    m.append(1, "assistant", "ola")
    m.append(2, "user", "outro chat")
    assert m.get_history(1) == [
        {"role": "user", "content": "oi"},
        {"role": "assistant", "content": "ola"},
    ]
    assert m.get_history(2) == [{"role": "user", "content": "outro chat"}]

def test_janela_limita_tamanho():
    m = ConversationMemory(max_messages=2)
    for i in range(5):
        m.append(1, "user", f"msg{i}")
    hist = m.get_history(1)
    assert len(hist) == 2
    assert hist[0]["content"] == "msg3"
    assert hist[1]["content"] == "msg4"

def test_get_history_chat_desconhecido_vazio():
    m = ConversationMemory(max_messages=4)
    assert m.get_history(999) == []
```

**Step 2:** Run: `uv run pytest tests/test_memory.py -v` → FAIL.

**Step 3: Implementar**
```python
# src/assistente_telegram_voz/memory.py
from collections import defaultdict, deque

class ConversationMemory:
    def __init__(self, max_messages: int):
        self._max = max_messages
        self._store: dict[int, deque] = defaultdict(lambda: deque(maxlen=self._max))

    def append(self, chat_id: int, role: str, content: str) -> None:
        self._store[chat_id].append({"role": role, "content": content})

    def get_history(self, chat_id: int) -> list[dict]:
        return list(self._store.get(chat_id, []))
```

**Step 4:** Run: `uv run pytest tests/test_memory.py -v` → PASS.

**Step 5: Commit**
```bash
git add src/assistente_telegram_voz/memory.py tests/test_memory.py
git commit -m "feat: memory.py com janela por chat em RAM"
```

---

## Task 3: prompt.py — carregar e montar system prompt

**Files:**
- Create: `src/assistente_telegram_voz/prompt.py`
- Test: `tests/test_prompt.py`

**Step 1: Teste que falha**
```python
# tests/test_prompt.py
from assistente_telegram_voz import prompt as pmod

def test_build_sem_chunks_retorna_base(tmp_path, monkeypatch):
    p = tmp_path / "system.md"
    p.write_text("Voce e um assistente.", encoding="utf-8")
    monkeypatch.setattr(pmod, "PROMPT_PATH", p)
    pmod.load_system_prompt.cache_clear()
    assert pmod.build_system_prompt([]) == "Voce e um assistente."

def test_build_com_chunks_injeta_contexto(tmp_path, monkeypatch):
    p = tmp_path / "system.md"
    p.write_text("BASE", encoding="utf-8")
    monkeypatch.setattr(pmod, "PROMPT_PATH", p)
    pmod.load_system_prompt.cache_clear()
    out = pmod.build_system_prompt(["fato A", "fato B"])
    assert "BASE" in out
    assert "fato A" in out and "fato B" in out
    assert "apenas o material" in out.lower()
```

**Step 2:** Run: `uv run pytest tests/test_prompt.py -v` → FAIL.

**Step 3: Implementar**
```python
# src/assistente_telegram_voz/prompt.py
from pathlib import Path
from functools import lru_cache
from .config import get_settings

PROMPT_PATH = Path(get_settings().system_prompt_path)

@lru_cache(maxsize=1)
def load_system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8").strip()

def build_system_prompt(retrieved_chunks: list[str]) -> str:
    base = load_system_prompt()
    if not retrieved_chunks:
        return base
    contexto = "\n\n".join(f"- {c}" for c in retrieved_chunks)
    return (
        f"{base}\n\n"
        "## Material de referência (use para responder)\n"
        f"{contexto}\n\n"
        "Responda usando apenas o material acima. "
        "Se a resposta não estiver nele, diga que não tem essa informação."
    )
```
Nota: `PROMPT_PATH` derivado de config; nos testes é sobrescrito via monkeypatch.

**Step 4:** Run: `uv run pytest tests/test_prompt.py -v` → PASS.

**Step 5: Commit**
```bash
git add src/assistente_telegram_voz/prompt.py tests/test_prompt.py
git commit -m "feat: prompt.py carrega base e injeta contexto da RAG"
```

---

## Task 4: rag.py — retrieve no ChromaDB

**Files:**
- Create: `src/assistente_telegram_voz/rag.py`
- Test: `tests/test_rag.py`

**Step 1: Teste que falha** (embeddings e client Chroma mockados)
```python
# tests/test_rag.py
from unittest.mock import MagicMock
from assistente_telegram_voz import rag as ragmod

def test_retrieve_retorna_documentos(monkeypatch):
    fake_collection = MagicMock()
    fake_collection.query.return_value = {"documents": [["trecho1", "trecho2"]]}
    monkeypatch.setattr(ragmod, "get_collection", lambda: fake_collection)
    monkeypatch.setattr(ragmod, "_embed", lambda text: [0.1, 0.2, 0.3])
    out = ragmod.retrieve("pergunta", k=2)
    assert out == ["trecho1", "trecho2"]
    fake_collection.query.assert_called_once()

def test_retrieve_sem_resultado_lista_vazia(monkeypatch):
    fake_collection = MagicMock()
    fake_collection.query.return_value = {"documents": [[]]}
    monkeypatch.setattr(ragmod, "get_collection", lambda: fake_collection)
    monkeypatch.setattr(ragmod, "_embed", lambda text: [0.1])
    assert ragmod.retrieve("x", k=4) == []
```

**Step 2:** Run: `uv run pytest tests/test_rag.py -v` → FAIL.

**Step 3: Implementar**
```python
# src/assistente_telegram_voz/rag.py
from functools import lru_cache
import chromadb
from openai import OpenAI
from .config import get_settings

COLLECTION_NAME = "knowledge"

@lru_cache(maxsize=1)
def _openai_client() -> OpenAI:
    s = get_settings()
    return OpenAI(api_key=s.openai_api_key)

@lru_cache(maxsize=1)
def get_collection():
    s = get_settings()
    client = chromadb.PersistentClient(path=s.chroma_dir)
    return client.get_or_create_collection(COLLECTION_NAME)

def _embed(text: str) -> list[float]:
    s = get_settings()
    resp = _openai_client().embeddings.create(model=s.embedding_model, input=text)
    return resp.data[0].embedding

def retrieve(query: str, k: int | None = None) -> list[str]:
    s = get_settings()
    k = k or s.rag_top_k
    emb = _embed(query)
    res = get_collection().query(query_embeddings=[emb], n_results=k)
    docs = res.get("documents") or [[]]
    return docs[0]
```

**Step 4:** Run: `uv run pytest tests/test_rag.py -v` → PASS.

**Step 5: Commit**
```bash
git add src/assistente_telegram_voz/rag.py tests/test_rag.py
git commit -m "feat: rag.py com retrieve no ChromaDB"
```

---

## Task 5: scripts/ingest.py — ingestão da pasta rag/

**Files:**
- Create: `scripts/ingest.py`
- Test: `tests/test_ingest.py`

**Step 1: Teste que falha** (testa chunking e leitura; embeddings/Chroma mockados)
```python
# tests/test_ingest.py
from scripts import ingest

def test_chunk_text_divide_por_tamanho():
    texto = "a" * 2500
    chunks = ingest.chunk_text(texto, size=1000, overlap=0)
    assert len(chunks) == 3
    assert all(len(c) <= 1000 for c in chunks)

def test_read_documents_le_txt_e_md(tmp_path):
    (tmp_path / "a.txt").write_text("conteudo txt", encoding="utf-8")
    (tmp_path / "b.md").write_text("conteudo md", encoding="utf-8")
    (tmp_path / "ignora.png").write_bytes(b"\x89PNG")
    docs = ingest.read_documents(str(tmp_path))
    textos = sorted(d["text"] for d in docs)
    assert textos == ["conteudo md", "conteudo txt"]
```

**Step 2:** Run: `uv run pytest tests/test_ingest.py -v` → FAIL.

**Step 3: Implementar**
```python
# scripts/ingest.py
"""Ingestão: lê rag/, faz chunk + embed e popula ChromaDB. Rodar: uv run python -m scripts.ingest"""
from pathlib import Path
from pypdf import PdfReader
from assistente_telegram_voz.config import get_settings
from assistente_telegram_voz.rag import get_collection, _openai_client

def chunk_text(text: str, size: int = 1000, overlap: int = 150) -> list[str]:
    if not text.strip():
        return []
    chunks, start = [], 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start = end - overlap if end - overlap > start else end
    return chunks

def _read_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n".join((page.extract_text() or "") for page in reader.pages)

def read_documents(rag_dir: str) -> list[dict]:
    docs = []
    for p in Path(rag_dir).rglob("*"):
        if p.suffix.lower() in {".txt", ".md"}:
            docs.append({"source": str(p), "text": p.read_text(encoding="utf-8").strip()})
        elif p.suffix.lower() == ".pdf":
            docs.append({"source": str(p), "text": _read_pdf(p).strip()})
    return docs

def main() -> None:
    s = get_settings()
    collection = get_collection()
    client = _openai_client()
    documents = read_documents(s.rag_dir)
    ids, texts, embeddings, metadatas = [], [], [], []
    for doc in documents:
        for i, chunk in enumerate(chunk_text(doc["text"])):
            emb = client.embeddings.create(model=s.embedding_model, input=chunk).data[0].embedding
            ids.append(f"{doc['source']}#{i}")
            texts.append(chunk)
            embeddings.append(emb)
            metadatas.append({"source": doc["source"]})
    if ids:
        collection.upsert(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas)
    print(f"Indexados {len(ids)} chunks de {len(documents)} documentos.")

if __name__ == "__main__":
    main()
```
Nota: criar `scripts/__init__.py` vazio para permitir `from scripts import ingest`.

**Step 4:** Run: `uv run pytest tests/test_ingest.py -v` → PASS.

**Step 5: Commit**
```bash
git add scripts/ tests/test_ingest.py
git commit -m "feat: scripts/ingest.py para popular a RAG"
```

---

## Task 6: transcribe.py — áudio para texto

**Files:**
- Create: `src/assistente_telegram_voz/transcribe.py`
- Test: `tests/test_transcribe.py`

**Step 1: Teste que falha**
```python
# tests/test_transcribe.py
from unittest.mock import MagicMock, mock_open, patch
from assistente_telegram_voz import transcribe as tmod

def test_transcribe_chama_client_e_retorna_texto(monkeypatch):
    fake_client = MagicMock()
    fake_client.audio.transcriptions.create.return_value = MagicMock(text="ola mundo")
    monkeypatch.setattr(tmod, "_client", lambda: fake_client)
    with patch("builtins.open", mock_open(read_data=b"audio")):
        out = tmod.transcribe("/tmp/a.ogg")
    assert out == "ola mundo"
    fake_client.audio.transcriptions.create.assert_called_once()
```

**Step 2:** Run: `uv run pytest tests/test_transcribe.py -v` → FAIL.

**Step 3: Implementar**
```python
# src/assistente_telegram_voz/transcribe.py
from functools import lru_cache
from openai import OpenAI
from .config import get_settings

@lru_cache(maxsize=1)
def _client() -> OpenAI:
    return OpenAI(api_key=get_settings().openai_api_key)

def transcribe(audio_path: str) -> str:
    s = get_settings()
    with open(audio_path, "rb") as f:
        resp = _client().audio.transcriptions.create(model=s.transcribe_model, file=f)
    return resp.text.strip()
```

**Step 4:** Run: `uv run pytest tests/test_transcribe.py -v` → PASS.

**Step 5: Commit**
```bash
git add src/assistente_telegram_voz/transcribe.py tests/test_transcribe.py
git commit -m "feat: transcribe.py (gpt-4o-transcribe)"
```

---

## Task 7: tts.py — texto para áudio (ElevenLabs)

**Files:**
- Create: `src/assistente_telegram_voz/tts.py`
- Test: `tests/test_tts.py`

**Step 1: Teste que falha**
```python
# tests/test_tts.py
from unittest.mock import MagicMock
from assistente_telegram_voz import tts as tmod

def test_synthesize_retorna_bytes(monkeypatch):
    fake_client = MagicMock()
    fake_client.text_to_speech.convert.return_value = iter([b"aa", b"bb"])
    monkeypatch.setattr(tmod, "_client", lambda: fake_client)
    out = tmod.synthesize("ola")
    assert out == b"aabb"
    fake_client.text_to_speech.convert.assert_called_once()
```

**Step 2:** Run: `uv run pytest tests/test_tts.py -v` → FAIL.

**Step 3: Implementar**
```python
# src/assistente_telegram_voz/tts.py
from functools import lru_cache
from elevenlabs.client import ElevenLabs
from .config import get_settings

@lru_cache(maxsize=1)
def _client() -> ElevenLabs:
    return ElevenLabs(api_key=get_settings().elevenlabs_api_key)

def synthesize(text: str) -> bytes:
    s = get_settings()
    audio = _client().text_to_speech.convert(
        voice_id=s.elevenlabs_voice_id,
        model_id=s.elevenlabs_model,
        text=text,
        output_format="mp3_44100_128",
    )
    return b"".join(audio)
```
Nota: confirmar na execução a API exata do SDK elevenlabs instalado (assinatura de `convert`). Ajustar se a versão diferir.

**Step 4:** Run: `uv run pytest tests/test_tts.py -v` → PASS.

**Step 5: Commit**
```bash
git add src/assistente_telegram_voz/tts.py tests/test_tts.py
git commit -m "feat: tts.py (ElevenLabs)"
```

---

## Task 8: llm.py — geração via OpenRouter

**Files:**
- Create: `src/assistente_telegram_voz/llm.py`
- Test: `tests/test_llm.py`

**Step 1: Teste que falha**
```python
# tests/test_llm.py
from unittest.mock import MagicMock
from assistente_telegram_voz import llm as lmod

def test_generate_monta_mensagens_e_retorna_texto(monkeypatch):
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="resposta"))]
    )
    monkeypatch.setattr(lmod, "_client", lambda: fake_client)
    out = lmod.generate(
        system="SYS",
        history=[{"role": "user", "content": "oi"}],
        user_msg="tudo bem?",
    )
    assert out == "resposta"
    _, kwargs = fake_client.chat.completions.create.call_args
    msgs = kwargs["messages"]
    assert msgs[0] == {"role": "system", "content": "SYS"}
    assert msgs[-1] == {"role": "user", "content": "tudo bem?"}
```

**Step 2:** Run: `uv run pytest tests/test_llm.py -v` → FAIL.

**Step 3: Implementar**
```python
# src/assistente_telegram_voz/llm.py
from functools import lru_cache
from openai import OpenAI
from .config import get_settings

@lru_cache(maxsize=1)
def _client() -> OpenAI:
    s = get_settings()
    return OpenAI(api_key=s.openrouter_api_key, base_url=s.openrouter_base_url)

def generate(system: str, history: list[dict], user_msg: str) -> str:
    s = get_settings()
    messages = [{"role": "system", "content": system}, *history, {"role": "user", "content": user_msg}]
    resp = _client().chat.completions.create(model=s.llm_model, messages=messages)
    return resp.choices[0].message.content.strip()
```

**Step 4:** Run: `uv run pytest tests/test_llm.py -v` → PASS.

**Step 5: Commit**
```bash
git add src/assistente_telegram_voz/llm.py tests/test_llm.py
git commit -m "feat: llm.py via OpenRouter (gpt-5.6-luna)"
```

---

## Task 9: bot.py — orquestração e handlers do Telegram

**Files:**
- Create: `src/assistente_telegram_voz/bot.py`
- Modify: `src/assistente_telegram_voz/__init__.py` (expor `main`)
- Test: `tests/test_bot.py`

**Step 1: Teste que falha** (foco na função pura de orquestração `process_message`)
```python
# tests/test_bot.py
from unittest.mock import MagicMock
from assistente_telegram_voz import bot as bmod

def test_process_message_texto(monkeypatch):
    monkeypatch.setattr(bmod, "retrieve", lambda q, k=None: ["ctx"])
    monkeypatch.setattr(bmod, "build_system_prompt", lambda chunks: "SYS+ctx")
    monkeypatch.setattr(bmod, "generate", lambda system, history, user_msg: "resposta")
    mem = MagicMock()
    mem.get_history.return_value = []
    reply = bmod.process_message(chat_id=1, user_text="pergunta", memory=mem)
    assert reply == "resposta"
    assert mem.append.call_count == 2  # user + assistant

def test_process_message_erro_retorna_fallback(monkeypatch):
    def boom(*a, **k): raise RuntimeError("api down")
    monkeypatch.setattr(bmod, "retrieve", lambda q, k=None: [])
    monkeypatch.setattr(bmod, "build_system_prompt", lambda chunks: "SYS")
    monkeypatch.setattr(bmod, "generate", boom)
    mem = MagicMock(); mem.get_history.return_value = []
    reply = bmod.process_message(chat_id=1, user_text="x", memory=mem)
    assert "problema" in reply.lower()
```

**Step 2:** Run: `uv run pytest tests/test_bot.py -v` → FAIL.

**Step 3: Implementar** (lógica pura + wiring do Telegram)
```python
# src/assistente_telegram_voz/bot.py
import logging, tempfile
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from .config import get_settings
from .memory import ConversationMemory
from .rag import retrieve
from .prompt import build_system_prompt
from .llm import generate
from .transcribe import transcribe
from .tts import synthesize

logger = logging.getLogger(__name__)
ERRO_FALLBACK = "Tive um problema ao processar sua mensagem. Pode tentar de novo?"

def process_message(chat_id: int, user_text: str, memory: ConversationMemory) -> str:
    try:
        chunks = retrieve(user_text)
        system = build_system_prompt(chunks)
        history = memory.get_history(chat_id)
        reply = generate(system=system, history=history, user_msg=user_text)
        memory.append(chat_id, "user", user_text)
        memory.append(chat_id, "assistant", reply)
        return reply
    except Exception:
        logger.exception("Falha ao processar mensagem")
        return ERRO_FALLBACK

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    memory: ConversationMemory = ctx.application.bot_data["memory"]
    await ctx.bot.send_chat_action(update.effective_chat.id, "typing")
    reply = process_message(update.effective_chat.id, update.message.text, memory)
    await update.message.reply_text(reply)

async def handle_voice(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    memory: ConversationMemory = ctx.application.bot_data["memory"]
    await ctx.bot.send_chat_action(update.effective_chat.id, "record_voice")
    tg_file = await update.message.voice.get_file()
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=True) as tmp:
        await tg_file.download_to_drive(tmp.name)
        try:
            user_text = transcribe(tmp.name)
        except Exception:
            logger.exception("Falha na transcrição")
            await update.message.reply_text(ERRO_FALLBACK)
            return
    reply = process_message(update.effective_chat.id, user_text, memory)
    try:
        audio = synthesize(reply)
        await update.message.reply_voice(voice=audio)
    except Exception:
        logger.exception("Falha no TTS; caindo para texto")
        await update.message.reply_text(reply)

def main() -> None:
    logging.basicConfig(level=logging.INFO)
    s = get_settings()
    app = Application.builder().token(s.telegram_bot_token).build()
    app.bot_data["memory"] = ConversationMemory(max_messages=s.history_max_messages)
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    logger.info("Bot iniciado. Polling...")
    app.run_polling()
```

**Step 4:** Run: `uv run pytest tests/test_bot.py -v` → PASS.
Depois rodar a suíte inteira: `uv run pytest -v` → todos PASS.

**Step 5: Commit**
```bash
git add src/assistente_telegram_voz/bot.py src/assistente_telegram_voz/__init__.py tests/test_bot.py
git commit -m "feat: bot.py com orquestração e handlers Telegram"
```

---

## Task 10: Arquivos de apoio (.env.example, system.md, README, .gitignore)

**Files:**
- Create: `.env.example`
- Create: `prompt/system.md`
- Create: `rag/.gitkeep`
- Modify: `.gitignore` (adicionar `chroma_db/` e `.env`)
- Modify: `README.md`

**Step 1:** `.env.example` com todas as chaves do design (valores vazios).

**Step 2:** `prompt/system.md` placeholder:
```markdown
Você é um assistente especializado. Responda em português, de forma clara e concisa.
Use apenas o material de referência fornecido. Se não souber, diga que não tem a informação.
```

**Step 3:** `.gitignore` — garantir linhas `.env` e `chroma_db/`.

**Step 4:** `README.md` com: instalação (`uv sync`), configurar `.env`, colocar docs em `rag/`, rodar ingestão (`uv run python -m scripts.ingest`), rodar bot (`uv run python -m assistente_telegram_voz.bot`).

**Step 5:** Verificar suíte e commit:
```bash
uv run pytest -v
git add .env.example prompt/ rag/.gitkeep .gitignore README.md
git commit -m "docs: arquivos de apoio e instruções de execução"
```

---

## Verificação final

- `uv run pytest -v` → toda a suíte passa.
- Revisão de código final da implementação inteira.
- Teste manual (com credenciais reais): ingestão + enviar texto e áudio ao bot.

## Notas de risco a validar durante a execução

1. **Áudio de saída no Telegram:** `reply_voice` espera OGG/Opus; ElevenLabs gera MP3. Pode ser necessário converter com `ffmpeg` (ou usar `output_format` compatível). Validar e, se preciso, adicionar etapa de conversão.
2. **SDK ElevenLabs:** confirmar a assinatura de `text_to_speech.convert` na versão instalada.
3. **Identificador do modelo no OpenRouter:** confirmar se `openai/gpt-5.6-luna` é o slug correto.
4. **`gpt-4o-transcribe`:** confirmar disponibilidade na conta OpenAI; alternativa `whisper-1`.
