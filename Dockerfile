# Imagem base com uv já instalado (Python 3.12)
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Deixa logs saírem na hora (bom para logs de container) e configura o cache do HF.
# O torch CPU-only é garantido pelo pyproject.toml + uv.lock (índice CPU do PyTorch),
# então não há pacotes NVIDIA/CUDA aqui — o embedding roda em CPU.
ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    HF_HOME=/opt/hf-cache

WORKDIR /app

# 1) Instala as dependências (camada cacheável) usando só os manifestos.
#    O cache do uv é montado como cache do BuildKit: acelera rebuilds sem inchar
#    a imagem final com uma segunda cópia dos pacotes (efeito do UV_LINK_MODE=copy).
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --no-install-project

# 2) Copia o código da aplicação e instala o próprio pacote
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev

# 3) Pré-baixa o modelo de embeddings para a imagem, evitando download a cada start.
#    O nome deve casar com EMBEDDING_MODEL do .env.
ARG EMBEDDING_MODEL=paraphrase-multilingual-MiniLM-L12-v2
RUN uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${EMBEDDING_MODEL}')"

# Sobe o bot (polling — não precisa de porta exposta nem domínio)
CMD ["uv", "run", "python", "-m", "assistente_telegram_voz.bot"]
