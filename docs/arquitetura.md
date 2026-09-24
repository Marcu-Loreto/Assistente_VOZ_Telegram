# Arquitetura — Assistente Conversacional por Voz (Telegram)

Diagrama baseado no código da branch `v2.0`. Dois processos independentes
compartilham a mesma base de conhecimento (ChromaDB) e o mesmo system prompt:

- **Bot do Telegram** (`assistente_telegram_voz.bot`): runtime em polling que
  atende texto, voz e imagem.
- **Frontend Streamlit** (`app.py`): gestão do RAG (upload/conversão + listar/excluir),
  atrás de login simples.
- **Ingestão** (`scripts/ingest.py`): CLI que popula o ChromaDB a partir de `rag/`.

## Fluxo geral

```mermaid
flowchart TB
    user([Usuário no Telegram])

    subgraph bot["Processo: Bot (polling)"]
        direction TB
        handlers["bot.py<br/>handlers: texto / voz / foto"]
        memory["memory.py<br/>histórico por chat (RAM)"]
        promptb["prompt.py<br/>build_system_prompt + CONTEXT_RAG"]
        ragr["rag.py<br/>retrieve(query, k)"]
    end

    subgraph ext["Serviços externos"]
        direction TB
        transcribe["OpenAI<br/>gpt-4o-transcribe<br/>(voz → texto)"]
        vision["OpenRouter<br/>VISION_MODEL<br/>(imagem → descrição + OCR)"]
        llm["OpenRouter<br/>LLM_MODEL<br/>(geração da resposta)"]
        tts["ElevenLabs<br/>TTS (texto → áudio Opus)"]
    end

    subgraph knowledge["Base de conhecimento (local)"]
        direction TB
        embed["embeddings.py<br/>sentence-transformers (CPU, offline)"]
        chroma[("ChromaDB<br/>chroma_dir/ (coleção 'knowledge')")]
        promptfile["prompt/agente.md<br/>(system prompt base)"]
    end

    subgraph admin["Processo: Frontend Streamlit (app.py)"]
        direction TB
        login["Login (RAG_ADMIN_USERS)"]
        upload["Adicionar documentos<br/>converter.py → Markdown"]
        manage["Gerenciar base<br/>list_documents / delete_document"]
    end

    ragfiles[/"rag/ (documentos-fonte)"/]
    ingest["scripts/ingest.py<br/>chunk + embed + index"]

    %% Entrada do usuário
    user -->|texto| handlers
    user -->|voz .ogg| handlers
    user -->|foto| handlers

    %% Pré-processamento por tipo
    handlers -->|áudio| transcribe
    transcribe -->|texto| handlers
    handlers -->|imagem| vision
    vision -->|conteúdo visual + OCR| handlers

    %% Núcleo RAG + LLM
    handlers --> ragr
    ragr --> embed
    embed --> chroma
    chroma -->|top-k trechos| ragr
    ragr --> promptb
    promptfile --> promptb
    memory <--> handlers
    promptb -->|system + histórico + msg| llm
    llm -->|resposta em texto| handlers

    %% Saída
    handlers -->|resposta texto| user
    handlers -->|se entrada foi voz| tts
    tts -->|áudio| user

    %% Gestão / ingestão da base
    login --> upload
    login --> manage
    upload --> ragfiles
    upload -.reindexa.-> ingest
    manage --> chroma
    ragfiles --> ingest
    ingest --> embed
    ingest --> chroma
```

## Comportamento-chave (do código)

- **Espelha o formato da entrada:** texto → responde em texto; voz → responde em
  texto **e** áudio (o texto é enviado primeiro; o áudio chega em seguida).
- **Imagem:** a legenda guia a saída; sem legenda, usa "Explique a imagem".
- **RAG:** `retrieve()` gera o embedding da pergunta (local, CPU, modo offline) e
  consulta o ChromaDB; os trechos entram no bloco `CONTEXT_RAG` do system prompt.
- **Memória:** histórico por chat mantido em RAM (`HISTORY_MAX_MESSAGES`); reiniciar
  o processo zera.
- **Resiliência:** falha de TTS não derruba a resposta — o texto já foi enviado antes.

```

```
