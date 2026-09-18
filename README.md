# Assistente Conversacional por Voz (Telegram)

Bot do Telegram que conversa por texto e por voz e **espelha o formato da entrada**:
responde em **texto** quando recebe texto e em **voz** quando recebe áudio.

É um assistente **generalista fundamentado em RAG**: ele não é preso a um único
tema. O conhecimento dele é definido pelos documentos que você coloca na pasta
`rag/`, seja qual for o assunto. Ele responde com base nesse material e, quando a
base não cobre a pergunta, avisa que não encontrou a informação em vez de inventar.
O comportamento, o tom e os guardrails ficam no arquivo de prompt e podem ser
editados sem mexer no código.

## Componentes

- **Cérebro (LLM):** `gpt-5.6-luna` via OpenRouter
- **Transcrição (voz → texto):** `gpt-4o-transcribe` (OpenAI), forçada para português
- **Voz (texto → áudio):** ElevenLabs (saída em Opus, formato nativo de voice message)
- **Conhecimento (RAG):** ChromaDB local + **embeddings locais** via
  `sentence-transformers` (sem custo de API para embeddings)
- **Memória:** histórico de conversa por chat, em RAM (reiniciar o processo zera)

## Como rodar (local)

### 1. Instalar dependências

```bash
uv sync
```

### 2. Configurar credenciais

```bash
cp .env.example .env
```

Edite o `.env` com o token do Telegram (via @BotFather) e as chaves do OpenRouter,
OpenAI (usada só para transcrição de voz) e ElevenLabs. O `.env` não é versionado.

### 3. Alimentar a base de conhecimento

Coloque seus documentos (`.md`, `.txt`, `.pdf`) na pasta `rag/` e rode a ingestão,
que fatia os textos, gera os embeddings localmente e popula o ChromaDB:

```bash
uv run python -m scripts.ingest
```

Rode novamente sempre que adicionar ou alterar documentos em `rag/`. O primeiro uso
baixa o modelo de embeddings (uma vez).

### 4. Personalizar o assistente (opcional)

Edite `prompt/agente.md` para ajustar identidade, escopo, tom e guardrails. O
caminho do prompt é configurável pela variável `SYSTEM_PROMPT_PATH` no `.env`.

### 5. Iniciar o bot

```bash
uv run python -m assistente_telegram_voz.bot
```

O bot fica em **polling** (puxa as mensagens do Telegram), então **não precisa de
domínio, IP público nem porta aberta** — só acesso de saída à internet. Mande uma
mensagem de texto ou de voz para o bot.

> Só uma instância do bot pode rodar por token ao mesmo tempo. Rodar duas (por
> exemplo, local e container) causa o erro `Conflict` do Telegram.

## Como rodar (Docker)

A imagem usa PyTorch CPU-only para ficar enxuta. Os dados (`.env`, `rag/`,
`chroma_db/`, `prompt/`) ficam fora da imagem e entram via volumes/env.

```bash
docker compose up --build -d      # sobe o bot em background
docker compose logs -f            # acompanha os logs
docker compose down               # para o bot
```

O `docker-compose.yml` monta `./chroma_db`, `./prompt` e `./rag` como volumes e lê
o `.env`. Se a base (`chroma_db/`) já existir na máquina, o container a reutiliza.
Em um servidor limpo, gere a base primeiro — rodando a ingestão localmente e
copiando `chroma_db/`, ou executando a ingestão dentro do container:

```bash
docker compose run --rm bot uv run python -m scripts.ingest
```

## Testes

```bash
uv run pytest
```

## Estrutura

```
prompt/agente.md   # system prompt do assistente (editável; escopo, tom, guardrails)
rag/               # documentos-fonte da base de conhecimento (não versionados)
chroma_db/         # índice vetorial gerado (não versionado)
scripts/ingest.py  # ingestão: lê rag/, gera embeddings e popula o ChromaDB
src/assistente_telegram_voz/
  config.py        # carrega e valida o .env
  memory.py        # histórico de conversa por chat (em RAM)
  prompt.py        # monta o system prompt + contexto recuperado (CONTEXT_RAG)
  rag.py           # busca trechos relevantes no ChromaDB
  embeddings.py    # embeddings locais (sentence-transformers)
  transcribe.py    # áudio -> texto (OpenAI)
  tts.py           # texto -> áudio (ElevenLabs)
  llm.py           # geração de resposta (OpenRouter)
  bot.py           # orquestração e handlers do Telegram
Dockerfile / docker-compose.yml   # execução em container
```
