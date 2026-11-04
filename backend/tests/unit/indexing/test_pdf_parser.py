import io

import pytest
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from maritime.core.exceptions import CorruptedPdfError
from maritime.modules.indexing.infrastructure.parsers.pdfplumber_parser import PdfplumberParser


def create_sample_pdf_with_table() -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("Contrato de Transporte Maritimo Naviera Portecho", styles["Heading1"]))
    story.append(Spacer(1, 10))
    story.append(
        Paragraph("Clausula 4: Tarifas aplicables por contenedor y dias libres.", styles["Normal"])
    )
    story.append(Spacer(1, 10))

    data = [
        ["Tipo Contenedor", "Tarifa USD", "Dias Libres Demurrage"],
        ["20ft Standard", "1250", "7"],
        ["40ft High Cube", "2100", "10"],
        ["40ft Reefer", "3400", "5"],
    ]
    t = Table(data)
    t.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ]
        )
    )
    story.append(t)

    doc.build(story)
    return buffer.getvalue()


@pytest.mark.unit
def test_parser_rejects_empty_bytes() -> None:
    parser = PdfplumberParser()
    with pytest.raises(CorruptedPdfError, match="Archivo corrupto o sin páginas legibles"):
        parser.parse(b"")


@pytest.mark.unit
def test_parser_rejects_corrupted_garbage_bytes() -> None:
    parser = PdfplumberParser()
    with pytest.raises(CorruptedPdfError, match="Archivo corrupto o sin páginas legibles"):
        parser.parse(b"Not a valid PDF header garbage content 1234567890")


@pytest.mark.unit
def test_parser_extracts_text_and_markdown_tables() -> None:
    pdf_bytes = create_sample_pdf_with_table()
    parser = PdfplumberParser()
    pages = parser.parse(pdf_bytes)

    assert len(pages) == 1
    page = pages[0]
    assert page.page_number == 1
    assert "Contrato de Transporte Maritimo Naviera Portecho" in page.text
    assert "Clausula 4" in page.text

    # Verify table extracted into Markdown
    assert len(page.tables) >= 1
    markdown_table = page.tables[0]
    assert "| Tipo Contenedor | Tarifa USD | Dias Libres Demurrage |" in markdown_table
    assert "| 20ft Standard | 1250 | 7 |" in markdown_table
    assert "| 40ft Reefer | 3400 | 5 |" in markdown_table
