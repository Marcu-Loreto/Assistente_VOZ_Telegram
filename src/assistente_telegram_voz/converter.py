"""Conversão de documentos para Markdown.

Recebe arquivos em diferentes formatos (.txt, .md, .docx, .csv, .xlsx, .pdf e
imagens .png/.jpg/.jpeg/.webp/.gif/.bmp) e os converte para `.md`, formato limpo e
uniforme que facilita o chunking e a geração de embeddings na etapa de ingestão do
RAG. Imagens passam por um modelo de visão que descreve o conteúdo e faz OCR.

Uso básico:

    from assistente_telegram_voz.converter import DocumentConverter

    conv = DocumentConverter()
    md_path = conv.convert_file("documento.docx")          # grava .md ao lado
    md_text = conv.convert_bytes(raw, "planilha.xlsx")     # retorna só o texto
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

# Extensões de imagem: exigem interpretação + OCR por um modelo de visão.
IMAGE_EXTENSIONS: frozenset[str] = frozenset(
    {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
)

# Formatos aceitos na entrada. A saída é sempre .md.
SUPPORTED_EXTENSIONS: frozenset[str] = (
    frozenset({".txt", ".md", ".docx", ".csv", ".xlsx", ".pdf"}) | IMAGE_EXTENSIONS
)


class UnsupportedFormatError(ValueError):
    """Levantada quando a extensão do arquivo não é suportada."""


class DocumentConverter:
    """Converte documentos de vários formatos para texto Markdown.

    Cada formato tem um handler dedicado (`_from_*`) que recebe os bytes brutos
    do arquivo e devolve uma string Markdown. Isso permite converter tanto de um
    caminho em disco (`convert_file`) quanto de um upload em memória
    (`convert_bytes`), sem duplicar a lógica de parsing.
    """

    def __init__(self, csv_delimiter: str | None = None) -> None:
        # None => detecta o delimitador automaticamente (vírgula, ponto-e-vírgula...).
        self.csv_delimiter = csv_delimiter

    # ------------------------------------------------------------------ API

    def convert_bytes(self, data: bytes, filename: str) -> str:
        """Converte os bytes de um arquivo em texto Markdown.

        Usa a extensão de `filename` para escolher o parser correto. Não escreve
        nada em disco — ideal para uploads (ex.: Streamlit).
        """
        suffix = Path(filename).suffix.lower()
        handler = self._handlers().get(suffix)
        if handler is None:
            raise UnsupportedFormatError(
                f"Formato não suportado: {suffix or '(sem extensão)'}. "
                f"Suportados: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            )
        title = Path(filename).stem
        body = handler(data, suffix).strip()
        return self._with_title(title, body)

    def convert_file(self, path: str | Path, out_dir: str | Path | None = None) -> Path:
        """Converte um arquivo em disco e grava o `.md` resultante.

        Por padrão o `.md` é escrito ao lado do original; passe `out_dir` para
        gravar em outra pasta. Retorna o caminho do arquivo `.md` gerado.
        """
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(f"Arquivo não encontrado: {path}")

        md_text = self.convert_bytes(path.read_bytes(), path.name)

        out_dir = Path(out_dir) if out_dir else path.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{path.stem}.md"
        out_path.write_text(md_text, encoding="utf-8")
        return out_path

    # -------------------------------------------------------------- helpers

    def _handlers(self) -> dict[str, "callable[[bytes, str], str]"]:
        handlers: dict[str, "callable[[bytes, str], str]"] = {
            ".txt": lambda data, _suffix: self._from_text(data),
            ".md": lambda data, _suffix: self._from_text(data),
            ".docx": lambda data, _suffix: self._from_docx(data),
            ".csv": lambda data, _suffix: self._from_csv(data),
            ".xlsx": lambda data, _suffix: self._from_xlsx(data),
            ".pdf": lambda data, _suffix: self._from_pdf(data),
        }
        for ext in IMAGE_EXTENSIONS:
            handlers[ext] = self._from_image
        return handlers

    @staticmethod
    def _with_title(title: str, body: str) -> str:
        """Prefixa um cabeçalho `# título` para dar contexto ao chunk."""
        title = title.strip()
        if not title:
            return body
        return f"# {title}\n\n{body}".strip() + "\n"

    @staticmethod
    def _decode(data: bytes) -> str:
        """Decodifica bytes tentando UTF-8 e caindo para latin-1 se preciso."""
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            return data.decode("latin-1", errors="replace")

    # ------------------------------------------------------------ parsers

    def _from_text(self, data: bytes) -> str:
        """.txt / .md: usa o conteúdo como está."""
        return self._decode(data)

    def _from_docx(self, data: bytes) -> str:
        """.docx: extrai parágrafos e tabelas, preservando títulos e listas."""
        from docx import Document

        doc = Document(io.BytesIO(data))
        lines: list[str] = []

        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            style = (para.style.name or "").lower() if para.style else ""
            if style.startswith("heading"):
                # "Heading 1" -> "#", "Heading 2" -> "##", etc.
                level = "".join(ch for ch in style if ch.isdigit()) or "1"
                lines.append(f"{'#' * min(int(level) + 1, 6)} {text}")
            elif style.startswith("list") or style.startswith("bullet"):
                lines.append(f"- {text}")
            else:
                lines.append(text)

        for table in doc.tables:
            lines.append("")
            lines.extend(self._table_to_md([[c.text.strip() for c in row.cells] for row in table.rows]))

        return "\n\n".join(lines)

    def _from_csv(self, data: bytes) -> str:
        """.csv: converte em tabela Markdown, detectando o delimitador."""
        text = self._decode(data)
        if not text.strip():
            return ""
        if self.csv_delimiter:
            delimiter = self.csv_delimiter
        else:
            try:
                delimiter = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|").delimiter
            except csv.Error:
                delimiter = ","
        rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
        return "\n".join(self._table_to_md(rows))

    def _from_xlsx(self, data: bytes) -> str:
        """.xlsx: cada aba vira uma seção `## <aba>` com uma tabela Markdown."""
        from openpyxl import load_workbook

        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        sections: list[str] = []
        for ws in wb.worksheets:
            rows = [
                ["" if cell is None else str(cell) for cell in row]
                for row in ws.iter_rows(values_only=True)
            ]
            # Remove linhas totalmente vazias.
            rows = [r for r in rows if any(c.strip() for c in r)]
            if not rows:
                continue
            table = "\n".join(self._table_to_md(rows))
            sections.append(f"## {ws.title}\n\n{table}")
        wb.close()
        return "\n\n".join(sections)

    def _from_pdf(self, data: bytes) -> str:
        """.pdf: extrai o texto de cada página (mesma lib usada na ingestão)."""
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
        return "\n\n".join(p for p in pages if p)

    def _from_image(self, data: bytes, suffix: str) -> str:
        """Imagem: interpreta o conteúdo e faz OCR via modelo de visão.

        Diferente dos outros parsers, este depende de uma chamada de rede ao
        modelo multimodal (VISION_MODEL). O resultado já vem em Markdown com uma
        descrição da imagem e o texto extraído.
        """
        # Import tardio: só carrega a infra de visão quando há uma imagem.
        from .image import IMAGE_MIME_TYPES, describe_image

        mime = IMAGE_MIME_TYPES.get(suffix, "image/png")
        return describe_image(data, mime)

    # -------------------------------------------------------------- tables

    @staticmethod
    def _table_to_md(rows: list[list[str]]) -> list[str]:
        """Converte uma matriz de células em linhas de tabela Markdown.

        A primeira linha é tratada como cabeçalho. Normaliza o número de colunas
        e escapa pipes para não quebrar a formatação da tabela.
        """
        rows = [r for r in rows if r]
        if not rows:
            return []

        width = max(len(r) for r in rows)

        def fmt(cell: str) -> str:
            return cell.replace("|", "\\|").replace("\n", " ").strip()

        def pad(r: list[str]) -> list[str]:
            return [fmt(c) for c in r] + [""] * (width - len(r))

        header = pad(rows[0])
        lines = ["| " + " | ".join(header) + " |"]
        lines.append("| " + " | ".join(["---"] * width) + " |")
        for r in rows[1:]:
            lines.append("| " + " | ".join(pad(r)) + " |")
        return lines
