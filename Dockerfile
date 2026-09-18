# Imagem base com uv já instalado (Python 3.12)
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Evita prompts e deixa logs saírem na hora (bom para logs de container).
# UV_TORCH_BACKEND=cpu faz o uv resolver a variante CPU-only do PyTorch,
# evitando ~4-5 GB de pacotes NVIDIA/CUDA (o embedding roda em CPU).
ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_TORCH_BACKEND=cpu \
    HF_HOME=/opt/hf-cache

WORKDIR /app

# 1) Instala as dependências (camada cacheável) usando só os manifestos.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --no-dev --no-install-project

# 2) Copia o código da aplicação e instala o próprio pacote
COPY src ./src
RUN uv sync --no-dev

# 3) Pré-baixa o modelo de embeddings para a imagem, evitando download a cada start.
#    O nome deve casar com EMBEDDING_MODEL do .env.
ARG EMBEDDING_MODEL=paraphrase-multilingual-MiniLM-L12-v2
RUN uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${EMBEDDING_MODEL}')"

# Sobe o bot (polling — não precisa de porta exposta nem domínio)
CMD ["uv", "run", "python", "-m", "assistente_telegram_voz.bot"]
