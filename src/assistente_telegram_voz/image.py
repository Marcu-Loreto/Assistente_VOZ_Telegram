"""Interpretação de imagens + OCR via modelo de visão (OpenRouter).

Quando um documento é uma imagem (foto, print, diagrama, slide escaneado), não há
texto que o `pypdf` ou os parsers de texto consigam extrair. Aqui usamos um modelo
multimodal (o mesmo provedor OpenRouter já usado pelo LLM) para:

1. **Descrever/interpretar** o conteúdo visual (o que a imagem mostra); e
2. Fazer o **OCR**, transcrevendo todo o texto legível embutido na imagem.

O resultado é um Markdown com duas seções, pronto para virar chunk no RAG.

Antes do envio, a imagem passa por um pré-processamento (redimensionamento e
recompressão via Pillow) que reduz o payload e, com isso, o custo e a latência da
chamada, sem comprometer a legibilidade do texto para o OCR.
"""

from __future__ import annotations

import base64
from functools import lru_cache

from openai import OpenAI

from .config import get_settings

# Extensões de imagem suportadas -> mime type enviado ao modelo de visão.
IMAGE_MIME_TYPES: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
}

# Instrução pedindo interpretação + OCR, com saída já em Markdown estruturado.
_PROMPT = (
    "Você recebeu uma imagem para ser indexada em uma base de conhecimento. "
    "Responda em português, em Markdown, com exatamente estas duas seções:\n\n"
    "## Descrição\n"
    "Descreva de forma objetiva o que a imagem mostra (tipo de conteúdo, "
    "elementos visuais, gráficos, diagramas, contexto).\n\n"
    "## Texto extraído (OCR)\n"
    "Transcreva fielmente TODO o texto legível presente na imagem, preservando a "
    "ordem de leitura. Se não houver texto, escreva '(sem texto detectado)'.\n\n"
    "Não invente informações que não estejam na imagem."
)


@lru_cache(maxsize=1)
def _client() -> OpenAI:
    """Cliente OpenRouter (mesma infra do LLM), compatível com a API OpenAI."""
    s = get_settings()
    return OpenAI(api_key=s.openrouter_api_key, base_url=s.openrouter_base_url)


def _data_url(data: bytes, mime: str) -> str:
    """Codifica a imagem como data URL base64 para envio inline ao modelo."""
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{b64}"


def preprocess_image(
    data: bytes,
    max_side: int,
    quality: int,
) -> tuple[bytes, str]:
    """Reduz e recomprime a imagem antes de enviar ao modelo de visão.

    Objetivo: cortar custo e latência sem perder legibilidade do texto (OCR).

    - Redimensiona mantendo a proporção se o maior lado passar de `max_side`.
      Reduzir a resolução importa mesmo quando não reduz bytes: modelos de visão
      costumam cobrar por resolução (tiles), não por tamanho de arquivo.
    - Recomprime em JPEG (mais leve); usa PNG quando a imagem tem transparência,
      para não pintar o fundo de preto.
    - Quando a imagem NÃO foi redimensionada, só troca pelo recomprimido se ele
      ficar menor — assim não inflamos uma imagem já pequena/otimizada.

    Retorna `(bytes, mime)`. Em caso de qualquer falha ao decodificar, devolve os
    bytes originais com um mime genérico — a conversão nunca deve quebrar por isso.
    """
    import io

    from PIL import Image, ImageOps

    try:
        with Image.open(io.BytesIO(data)) as img:
            # Respeita a orientação EXIF (fotos de celular) antes de medir/redimensionar.
            img = ImageOps.exif_transpose(img)

            has_alpha = img.mode in ("RGBA", "LA") or (
                img.mode == "P" and "transparency" in img.info
            )

            # Redimensiona só para baixo, preservando a proporção.
            resized = max_side > 0 and max(img.size) > max_side
            if resized:
                img.thumbnail((max_side, max_side), Image.LANCZOS)

            buf = io.BytesIO()
            if has_alpha:
                img.convert("RGBA").save(buf, format="PNG", optimize=True)
                out_mime = "image/png"
            else:
                img.convert("RGB").save(
                    buf, format="JPEG", quality=quality, optimize=True
                )
                out_mime = "image/jpeg"

            processed = buf.getvalue()
    except Exception:
        # Formato exótico/corrompido para o Pillow: segue com o original.
        return data, "image/png"

    # Se a imagem foi reduzida em pixels, vale a pena enviar a versão menor mesmo
    # que os bytes não tenham caído (o ganho está na resolução). Sem redução de
    # dimensão, só trocamos se o recomprimido realmente ficou menor.
    if resized or len(processed) < len(data):
        return processed, out_mime
    return data, "image/png"


def describe_image(data: bytes, mime: str) -> str:
    """Interpreta a imagem e extrai o texto (OCR), retornando Markdown.

    Antes de enviar, a imagem passa por `preprocess_image` (redimensiona e
    recomprime) para reduzir custo e latência. Faz uma única chamada ao modelo de
    visão configurado (VISION_MODEL). Requer OPENROUTER_API_KEY válido e um modelo
    multimodal.
    """
    s = get_settings()
    data, mime = preprocess_image(data, s.vision_max_image_px, s.vision_image_quality)
    resp = _client().chat.completions.create(
        model=s.vision_model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _PROMPT},
                    {"type": "image_url", "image_url": {"url": _data_url(data, mime)}},
                ],
            }
        ],
    )
    return (resp.choices[0].message.content or "").strip()
