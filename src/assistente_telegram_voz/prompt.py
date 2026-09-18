from functools import lru_cache
from pathlib import Path

from .config import get_settings


@lru_cache(maxsize=1)
def load_system_prompt() -> str:
    """Lê o system prompt base do caminho configurado (cacheado)."""
    path = Path(get_settings().system_prompt_path)
    return path.read_text(encoding="utf-8").strip()


def build_system_prompt(retrieved_chunks: list[str]) -> str:
    """Combina o prompt base com os trechos recuperados pela RAG.

    Sem trechos, devolve apenas o prompt base. Com trechos, injeta um bloco de
    material de referência e instrui o modelo a responder apenas com base nele.
    """
    base = load_system_prompt()
    if not retrieved_chunks:
        contexto = "(nenhum documento recuperado para esta pergunta)"
    else:
        contexto = "\n\n".join(
            f"[Trecho {i}]\n{c}" for i, c in enumerate(retrieved_chunks, 1)
        )
    return (
        f"{base}\n\n"
        "===== CONTEXT_RAG =====\n"
        "A seguir estão os trechos recuperados da base de conhecimento para a "
        "pergunta atual. Use-os como sua fonte de evidência. Se algum trecho "
        "responder à pergunta, responda com base nele mesmo que a redação não "
        "seja idêntica à pergunta.\n\n"
        f"{contexto}\n"
        "===== FIM DO CONTEXT_RAG ====="
    )
