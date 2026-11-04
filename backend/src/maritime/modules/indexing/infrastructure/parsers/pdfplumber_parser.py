import io
import re

import pdfplumber
from pypdf.errors import FileNotDecryptedError, PdfReadError

from maritime.core.exceptions import CorruptedPdfError, PasswordProtectedPdfError
from maritime.modules.indexing.domain.ports import IPdfParser, ParsedPage


class PdfplumberParser(IPdfParser):
    """PDF parser implementation using pdfplumber with tabular Markdown extraction."""

    def parse(self, pdf_bytes: bytes) -> list[ParsedPage]:
        if not pdf_bytes or len(pdf_bytes.strip()) == 0:
            raise CorruptedPdfError("Archivo corrupto o sin páginas legibles")

        try:
            stream = io.BytesIO(pdf_bytes)
            with pdfplumber.open(stream) as pdf:
                if not pdf.pages or len(pdf.pages) == 0:
                    raise CorruptedPdfError("Archivo corrupto o sin páginas legibles")

                parsed_pages: list[ParsedPage] = []

                for idx, page in enumerate(pdf.pages, start=1):
                    raw_text = page.extract_text() or ""
                    clean_text = self._sanitize_text(raw_text)

                    # Extract structured tables
                    markdown_tables: list[str] = []
                    try:
                        raw_tables = page.extract_tables()
                        if raw_tables:
                            for table_data in raw_tables:
                                md = self._convert_table_to_markdown(table_data)
                                if md:
                                    markdown_tables.append(md)
                    except Exception:
                        # Fallback gracefully to text extraction if table parsing encounters errors
                        pass

                    parsed_pages.append(
                        ParsedPage(
                            page_number=idx,
                            text=clean_text,
                            tables=markdown_tables,
                        )
                    )

                return parsed_pages

        except FileNotDecryptedError:
            raise PasswordProtectedPdfError("El documento está protegido por contraseña") from None
        except (PdfReadError, ValueError, IndexError, Exception) as e:
            if isinstance(e, (PasswordProtectedPdfError, CorruptedPdfError)):
                raise
            raise CorruptedPdfError(f"Archivo corrupto o sin páginas legibles: {e}") from e

    @staticmethod
    def _sanitize_text(text: str) -> str:
        """Removes null bytes and normalizes whitespace."""
        text = text.replace("\x00", "")
        text = re.sub(r"[ \t]+", " ", text)
        return text.strip()

    @staticmethod
    def _convert_table_to_markdown(table: list[list[str | None]]) -> str | None:
        """Converts a 2D matrix of table cells into a clean Markdown table."""
        if not table or len(table) < 2:
            return None

        # Clean cell values
        cleaned_rows: list[list[str]] = []
        for raw_row in table:
            cleaned_row = [
                str(cell).strip().replace("\n", " ").replace("|", "\\|") if cell is not None else ""
                for cell in raw_row
            ]
            if any(cleaned_row):  # Row not entirely empty
                cleaned_rows.append(cleaned_row)

        if len(cleaned_rows) < 2:
            return None

        # Determine column count from the widest row
        max_cols = max(len(r) for r in cleaned_rows)
        if max_cols == 0:
            return None

        # Pad rows to max_cols
        padded_rows = [r + [""] * (max_cols - len(r)) for r in cleaned_rows]

        header = padded_rows[0]
        separator = ["---"] * max_cols
        body = padded_rows[1:]

        lines: list[str] = []
        lines.append("| " + " | ".join(header) + " |")
        lines.append("| " + " | ".join(separator) + " |")
        for b_row in body:
            lines.append("| " + " | ".join(b_row) + " |")

        return "\n".join(lines)
