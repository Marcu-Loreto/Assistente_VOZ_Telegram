# Assistente Conversacional por Voz (Telegram + ElevenLabs) — Design

**Data:** 2026-09-17
**Status:** Aprovado (brainstorming concluído via skill superpowers)

## Objetivo

Um assistente conversacional no Telegram, especializado em um tema via RAG, que
responde em texto quando recebe texto e em voz quando recebe voz. O cérebro é o
modelo `gpt-5.6-luna` (via OpenRouter). Idioma: português.

## Decisões (brainstorming)

- **LLM (cérebro):** `gpt-5.6-luna` via **OpenRouter** (SDK `openai` apontando
  `base_url` do OpenRouter). Identificador do modelo configurável no `.env`
  (ex.: `openai/gpt-5.6-luna`).
- **Transcrição (voz → texto):** `gpt-4o-transcribe` via **OpenAI direto**.
- **Embeddings (RAG):** `text-embedding-3-small` via **OpenAI direto**.
- **TTS (texto → voz):** **ElevenLabs**, `voice_id=Qrdut83w0Cr152Yb4Xn3`,
  modelo `eleven_multilingual_v2`.
- **Formato de resposta:** espelha a entrada (texto→texto, áudio→áudio).
- **Memória:** em RAM por `chat_id`, janela limitada (`HISTORY_MAX_MESSAGES`);
  reinício zera.
- **RAG:** ChromaDB local persistido em disco (Opção A). Documentos na pasta
  `rag/` (.md/.txt/.pdf). Script de ingestão separado do runtime.
- **Prompt:** system prompt em `prompt/system.md`, carregado/montado por
  `prompt.py` (injeta trechos recuperados da RAG).
- **Tema e origem dos documentos:** a definir pelo usuário (pasta `rag/` genérica;
  system prompt refinável depois).

## Arquitetura / estrutura de arquivos

```
Assistente_Telegram_Voz/
├─ .env                      # segredos e config (nunca commitado)
├─ .env.example              # modelo com as chaves esperadas
├─ prompt/
│  └─ system.md              # system prompt do assistente (editável)
├─ rag/                      # documentos-fonte do tema (.md/.txt/.pdf)
├─ chroma_db/                # índice vetorial persistido (gitignored)
├─ scripts/
│  └─ ingest.py              # lê rag/, chunk+embed, popula ChromaDB
├─ src/assistente_telegram_voz/
│  ├─ __init__.py
│  ├─ config.py              # carrega .env, valida, expõe Settings
│  ├─ bot.py                 # entrada: handlers do Telegram + polling
│  ├─ llm.py                 # chamada ao gpt-5.6-luna (OpenRouter)
│  ├─ prompt.py              # carrega/monta o system prompt
│  ├─ rag.py                 # consulta ao ChromaDB (retrieve)
│  ├─ transcribe.py          # áudio -> texto (gpt-4o-transcribe)
│  ├─ tts.py                 # texto -> áudio (ElevenLabs)
│  └─ memory.py              # histórico por chat em RAM
└─ tests/                    # testes por módulo (TDD)
```

## Fluxo de uma mensagem

1. Recebe update (texto ou voz) + `chat_id`.
2. É voz? SIM → baixa `.ogg` → `transcribe.py` → texto; modo="audio".
   NÃO → texto = `message.text`; modo="texto".
3. `rag.py`: embedding da pergunta → top-k trechos no ChromaDB.
4. `memory.py`: histórico recente do `chat_id` (janela limitada).
5. `prompt.py`: monta system prompt (base + trechos recuperados).
6. `llm.py`: chama `gpt-5.6-luna` com [system, ...histórico, pergunta] → resposta.
7. `memory.py`: adiciona pergunta + resposta ao histórico.
8. modo=="audio"? SIM → `tts.py` (ElevenLabs) → envia voice message.
   NÃO → envia texto.

**Erros/detalhes:** feedback de chat action (typing/record_voice); qualquer falha
→ mensagem de erro amigável em texto + log do erro real, sem travar o processo;
RAG sem resultado → modelo instruído a dizer que não sabe; limites configuráveis
de áudio/histórico; possível reconversão de áudio com ffmpeg (confirmar na impl.).

## Configuração (.env)

```bash
# Telegram
TELEGRAM_BOT_TOKEN=

# LLM via OpenRouter
OPENROUTER_API_KEY=
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=openai/gpt-5.6-luna

# OpenAI direto (transcrição + embeddings)
OPENAI_API_KEY=
TRANSCRIBE_MODEL=gpt-4o-transcribe
EMBEDDING_MODEL=text-embedding-3-small

# ElevenLabs
ELEVENLABS_API_KEY=
ELEVENLABS_VOICE_ID=Qrdut83w0Cr152Yb4Xn3
ELEVENLABS_MODEL=eleven_multilingual_v2

# RAG
RAG_DIR=rag
CHROMA_DIR=chroma_db
RAG_TOP_K=4

# Comportamento
SYSTEM_PROMPT_PATH=prompt/system.md
HISTORY_MAX_MESSAGES=10
MAX_AUDIO_SECONDS=120
```

## Contrato dos módulos

| Módulo | Função | Entrada → Saída |
|---|---|---|
| `config.py` | `get_settings()` | `.env` → `Settings` validado |
| `prompt.py` | `build_system_prompt(chunks)` | trechos → system prompt |
| `rag.py` | `retrieve(query, k)` / `get_collection()` | pergunta → trechos |
| `transcribe.py` | `transcribe(audio_path)` | `.ogg` → texto |
| `tts.py` | `synthesize(text)` | texto → bytes de áudio |
| `llm.py` | `generate(system, history, user_msg)` | prompt → resposta |
| `memory.py` | `get_history(chat_id)` / `append(...)` | histórico em RAM |
| `bot.py` | `main()` | inicia bot + polling |
| `scripts/ingest.py` | CLI | `rag/` → `chroma_db/` |

## Dependências

`python-telegram-bot`, `openai`, `elevenlabs`, `chromadb`, `pypdf`,
`python-dotenv`; dev: `pytest`.

## Estratégia de testes (TDD)

Mockar todas as chamadas externas (Telegram/OpenAI/OpenRouter/ElevenLabs); testar
a lógica própria. Cobertura: validação de config; injeção de contexto no prompt;
janela e isolamento da memória; retrieve com Chroma em memória; clients chamados
com parâmetros corretos; lógica de decisão do fluxo no bot. Sem testes que gastem
crédito de API real.

## Ordem de implementação

1. `config.py` → 2. `memory.py` → 3. `prompt.py` → 4. `rag.py` + `scripts/ingest.py`
→ 5. `transcribe.py` → 6. `tts.py` → 7. `llm.py` → 8. `bot.py`
→ 9. `.env.example`, `prompt/system.md` placeholder, README de execução.
