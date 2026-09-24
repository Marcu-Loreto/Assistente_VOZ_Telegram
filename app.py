"""Frontend de gestão da base RAG (Streamlit).

Duas áreas, atrás de um login simples (sem senha — POC):

- **Adicionar documentos:** recebe arquivos em vários formatos (.txt, .md, .docx,
  .csv, .xlsx, .pdf e imagens), converte cada um para Markdown com a
  `DocumentConverter`, salva na pasta do RAG (`RAG_DIR`) e opcionalmente reindexa.
- **Gerenciar base:** lista os documentos indexados no banco vetorial (ChromaDB),
  mostra arquivos ainda não indexados e permite excluir documentos (chunks no banco
  + arquivo em disco).

O acesso é liberado por nome de usuário presente em `RAG_ADMIN_USERS` (.env). Como
é POC, não há senha — o login serve só para separar a gestão do uso comum. NÃO use
isso exposto na internet sem uma autenticação real.

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
from assistente_telegram_voz.rag import delete_document, list_documents

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


# ------------------------------------------------------------------ login

def _login_gate() -> str | None:
    """Mostra o formulário de login e retorna o usuário autenticado (ou None).

    Sem senha (POC): basta o nome estar em RAG_ADMIN_USERS. O usuário logado fica
    na session_state até clicar em Sair.
    """
    if user := st.session_state.get("user"):
        return user

    admins = get_settings().rag_admin_users
    st.title("🔐 Gestão do RAG")
    if not admins:
        st.error(
            "Nenhum usuário de gestão configurado. Defina `RAG_ADMIN_USERS` no `.env` "
            "(ex.: `RAG_ADMIN_USERS=admin`) e recarregue."
        )
        return None

    st.caption("Acesso restrito. Informe um usuário autorizado (sem senha — POC).")
    with st.form("login"):
        nome = st.text_input("Usuário")
        entrar = st.form_submit_button("Entrar", type="primary")
    if entrar:
        if nome.strip() in admins:
            st.session_state["user"] = nome.strip()
            st.rerun()
        else:
            st.error("Usuário não autorizado.")
    return None


# ------------------------------------------------------------ página: upload

def _page_upload() -> None:
    st.header("📚 Adicionar documentos")
    st.caption(
        "Envie arquivos em .txt, .md, .docx, .csv, .xlsx, .pdf ou imagens "
        "(.png, .jpg, .jpeg, .webp, .gif, .bmp). Cada documento é convertido para "
        "Markdown e salvo na base. Imagens passam por um modelo de visão que "
        "descreve o conteúdo e extrai o texto (OCR)."
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


# ---------------------------------------------------------- página: gestão

def _page_manage() -> None:
    st.header("🗂️ Gerenciar base")
    st.caption(
        "Documentos indexados no banco vetorial (ChromaDB). Excluir remove os "
        "trechos do banco e, opcionalmente, o arquivo de origem em disco."
    )

    rag_dir = _rag_dir()
    docs = list_documents()

    total_chunks = sum(d["chunks"] for d in docs)
    st.metric("Documentos indexados", len(docs), help=f"{total_chunks} trechos no total")

    if not docs:
        st.info("Nenhum documento indexado ainda. Adicione documentos na outra página.")
    else:
        for doc in docs:
            source = doc["source"]
            file_exists = Path(source).is_file()
            with st.container(border=True):
                col_info, col_btn = st.columns([4, 1.4], vertical_alignment="center")
                with col_info:
                    nome = Path(source).name
                    st.markdown(f"**{nome}**")
                    detalhe = f"`{source}` · {doc['chunks']} trecho(s)"
                    if not file_exists:
                        detalhe += " · ⚠️ arquivo ausente em disco"
                    st.caption(detalhe)
                with col_btn:
                    _delete_control(source, file_exists, rag_dir)

    # Arquivos na pasta que ainda não foram indexados no banco.
    indexed_sources = {d["source"] for d in docs}
    orfaos = [
        p for p in sorted(rag_dir.rglob("*"))
        if p.is_file() and p.suffix.lower() != ".gitkeep" and str(p) not in indexed_sources
    ]
    if orfaos:
        st.divider()
        st.subheader("Arquivos não indexados")
        st.caption("Estão em disco mas ainda não entraram no banco. Reindexe para incluí-los.")
        for p in orfaos:
            st.write(f"• `{p}`")
        if st.button("Reindexar base agora"):
            with st.spinner("Reindexando (gerando embeddings)..."):
                ok, output = _run_ingest()
            st.success("Base reindexada.") if ok else st.error("Falha na reindexação.")
            if output:
                st.code(output)
            st.rerun()


def _delete_control(source: str, file_exists: bool, rag_dir: Path) -> None:
    """Botão de exclusão com confirmação em dois passos (evita apagar por engano).

    Os botões usam a largura do contêiner para não cortar o texto ("C..." etc.).
    """
    confirm_key = f"confirm_del::{source}"
    if not st.session_state.get(confirm_key):
        if st.button("🗑️ Excluir", key=f"del::{source}", use_container_width=True):
            st.session_state[confirm_key] = True
            st.rerun()
        return

    also_file = st.checkbox(
        "Apagar também o arquivo em disco",
        value=file_exists,
        key=f"file::{source}",
        disabled=not file_exists,
    )
    if st.button("Confirmar exclusão", key=f"ok::{source}", type="primary",
                 use_container_width=True):
        removed = delete_document(source)
        msg = f"Removidos {removed} trecho(s) do banco."
        if also_file and file_exists:
            try:
                Path(source).unlink()
                msg += " Arquivo apagado."
            except OSError as e:
                msg += f" (Falha ao apagar arquivo: {e})"
        st.session_state.pop(confirm_key, None)
        st.success(msg)
        st.rerun()
    if st.button("Cancelar", key=f"no::{source}", use_container_width=True):
        st.session_state.pop(confirm_key, None)
        st.rerun()


# -------------------------------------------------------------------- main

def main() -> None:
    st.set_page_config(page_title="RAG · Gestão", page_icon="📚")

    user = _login_gate()
    if not user:
        return

    with st.sidebar:
        st.write(f"👤 **{user}**")
        pagina = st.radio("Página", ["Adicionar documentos", "Gerenciar base"])
        if st.button("Sair"):
            st.session_state.clear()
            st.rerun()

    if pagina == "Adicionar documentos":
        _page_upload()
    else:
        _page_manage()


if __name__ == "__main__":
    main()
