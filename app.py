"""Frontend de upload de documentos para a base RAG.

Interface web (Streamlit) que recebe documentos em vários formatos
(.txt, .md, .docx, .csv, .xlsx, .pdf), converte cada um para Markdown com a
`DocumentConverter` e salva na pasta do RAG (`RAG_DIR`). Opcionalmente dispara a
reindexação da base logo após salvar.

Rodar com:

    uv run streamlit run app.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import streamlit as st

from assistente_telegram_voz.config import get_settings
from assistente_telegram_voz.converter import (
    SUPPORTED_EXTENSIONS,
    DocumentConverter,
    UnsupportedFormatError,
)

# Extensões sem o ponto, no formato que o uploader do Streamlit espera.
UPLOAD_TYPES = sorted(ext.lstrip(".") for ext in SUPPORTED_EXTENSIONS)


@st.cache_resource
def _converter() -> DocumentConverter:
    return DocumentConverter()


def _rag_dir() -> Path:
    """Pasta destino dos .md (RAG_DIR do .env), criada se não existir."""
    rag_dir = Path(get_settings().rag_dir)
    rag_dir.mkdir(parents=True, exist_ok=True)
    return rag_dir


def _unique_path(directory: Path, stem: str) -> Path:
    """Evita sobrescrever: gera nome.md, nome-1.md, nome-2.md..."""
    candidate = directory / f"{stem}.md"
    counter = 1
    while candidate.exists():
        candidate = directory / f"{stem}-{counter}.md"
        counter += 1
    return candidate


def _run_ingest() -> tuple[bool, str]:
    """Executa a ingestão como subprocesso e retorna (ok, saída)."""
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.ingest"],
        capture_output=True,
        text=True,
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode == 0, output.strip()


def main() -> None:
    st.set_page_config(page_title="RAG · Adicionar documentos", page_icon="📚")
    st.title("📚 Adicionar documentos ao RAG")
    st.caption(
        "Envie arquivos em .txt, .md, .docx, .csv, .xlsx, .pdf ou imagens "
        "(.png, .jpg, .jpeg, .webp, .gif, .bmp). Cada documento é convertido para "
        "Markdown e salvo na base de conhecimento. Imagens passam por um modelo de "
        "visão que descreve o conteúdo e extrai o texto (OCR)."
    )

    rag_dir = _rag_dir()
    st.info(f"Os arquivos convertidos serão salvos em `{rag_dir}/`.")

    uploads = st.file_uploader(
        "Documentos",
        type=UPLOAD_TYPES,
        accept_multiple_files=True,
        help="Você pode enviar vários arquivos de uma vez.",
    )

    reindex = st.checkbox(
        "Reindexar a base após salvar",
        value=True,
        help="Roda a ingestão (gera embeddings e popula o ChromaDB) ao final.",
    )

    if st.button("Converter e salvar", type="primary", disabled=not uploads):
        converter = _converter()
        saved: list[Path] = []
        errors: list[str] = []

        progress = st.progress(0.0)
        status = st.empty()
        for i, upload in enumerate(uploads, start=1):
            try:
                status.write(f"Convertendo `{upload.name}`...")
                md_text = converter.convert_bytes(upload.getvalue(), upload.name)
                out_path = _unique_path(rag_dir, Path(upload.name).stem)
                out_path.write_text(md_text, encoding="utf-8")
                saved.append(out_path)
            except UnsupportedFormatError as e:
                errors.append(f"{upload.name}: {e}")
            except Exception as e:  # parsing pode falhar em arquivos corrompidos
                errors.append(f"{upload.name}: falha ao converter ({e})")
            progress.progress(i / len(uploads))
        status.empty()

        if saved:
            st.success(f"{len(saved)} documento(s) salvo(s) em `{rag_dir}/`.")
            for path in saved:
                with st.expander(f"📄 {path.name}"):
                    st.code(path.read_text(encoding="utf-8"), language="markdown")

        for err in errors:
            st.error(err)

        if saved and reindex:
            with st.spinner("Reindexando a base (gerando embeddings)..."):
                ok, output = _run_ingest()
            if ok:
                st.success("Base reindexada com sucesso.")
            else:
                st.error("Falha na reindexação. Veja a saída abaixo.")
            if output:
                st.code(output)
        elif saved:
            st.warning(
                "Documentos salvos, mas a base **não** foi reindexada. "
                "Rode `uv run python -m scripts.ingest` quando quiser atualizar."
            )


if __name__ == "__main__":
    main()
