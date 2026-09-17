# Assistente Conversacional por Voz (Telegram)

Bot do Telegram especializado por RAG que conversa por texto e por voz:
responde em **texto** quando recebe texto e em **voz** quando recebe áudio.

- **Cérebro:** `gpt-5.6-luna` via OpenRouter
- **Transcrição (voz → texto):** `gpt-4o-transcribe` (OpenAI)
- **Voz (texto → áudio):** ElevenLabs
- **Conhecimento:** RAG local com ChromaDB, alimentado pelos documentos em `rag/`

## Como rodar

### 1. Instalar dependências

```bash
uv sync
```

### 2. Configurar credenciais

Copie o modelo e preencha suas chaves:

```bash
cp .env.example .env
```

Edite o `.env` com o token do Telegram (via @BotFather) e as chaves do OpenRouter,
OpenAI e ElevenLabs. O `.env` não é versionado.

### 3. Alimentar a base de conhecimento

Coloque os documentos do tema (`.md`, `.txt`, `.pdf`) na pasta `rag/` e rode a
ingestão (indexa os documentos no ChromaDB):

```bash
uv run python -m scripts.ingest
```

Rode esse comando sempre que adicionar ou alterar documentos em `rag/`.

### 4. Personalizar o assistente (opcional)

Edite `prompt/system.md` para ajustar a personalidade, o tom e as regras do
assistente. Não precisa mexer no código.

### 5. Iniciar o bot

```bash
uv run python -m assistente_telegram_voz.bot
```

O bot fica em polling. Mande uma mensagem de texto ou de voz no Telegram.

## Testes

```bash
uv run pytest
```

## Estrutura

```
prompt/system.md   # system prompt (editável)
rag/               # documentos-fonte da base de conhecimento
chroma_db/         # índice vetorial gerado (não versionado)
scripts/ingest.py  # ingestão da RAG
src/assistente_telegram_voz/
  config.py        # carrega e valida o .env
  memory.py        # histórico de conversa por chat (em RAM)
  prompt.py        # monta o system prompt + contexto da RAG
  rag.py           # busca trechos relevantes no ChromaDB
  transcribe.py    # áudio -> texto
  tts.py           # texto -> áudio
  llm.py           # geração de resposta (OpenRouter)
  bot.py           # orquestração e handlers do Telegram
```
