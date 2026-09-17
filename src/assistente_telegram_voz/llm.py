from functools import lru_cache

from openai import OpenAI

from .config import get_settings


@lru_cache(maxsize=1)
def _client() -> OpenAI:
    s = get_settings()
    return OpenAI(api_key=s.openrouter_api_key, base_url=s.openrouter_base_url)


def generate(system: str, history: list[dict], user_msg: str) -> str:
    """Gera a resposta do assistente combinando system prompt, histórico e mensagem."""
    s = get_settings()
    messages = [
        {"role": "system", "content": system},
        *history,
        {"role": "user", "content": user_msg},
    ]
    resp = _client().chat.completions.create(model=s.llm_model, messages=messages)
    return resp.choices[0].message.content.strip()
