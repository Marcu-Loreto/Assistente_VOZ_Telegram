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
        return base
    contexto = "\n\n".join(f"- {c}" for c in retrieved_chunks)
    return (
        f"{base}\n\n"
        "## Material de referência (use para responder)\n"
        f"{contexto}\n\n"
        "Responda usando apenas o material acima. "
        "Se a resposta não estiver nele, diga que não tem essa informação."
    )
