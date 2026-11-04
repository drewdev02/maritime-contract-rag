import pytest

from maritime.modules.indexing.domain.ports import ParsedPage
from maritime.modules.indexing.infrastructure.services.markdown_table_chunker import (
    MarkdownTableChunker,
)
from maritime.modules.ingestion.domain.value_objects import DocumentId


@pytest.mark.unit
def test_chunker_creates_single_chunk_for_short_page() -> None:
    chunker = MarkdownTableChunker(max_chunk_chars=1000, overlap_chars=100)
    pages = [
        ParsedPage(
            page_number=1,
            text="Clausula 1: Definiciones y Condiciones Generales de Transporte.",
            tables=["| Contenedor | Tarifa |\n| --- | --- |\n| 20ft | 1000 |"],
        )
    ]

    document_id = DocumentId.generate()
    chunks = chunker.chunk(pages=pages, document_id=document_id)

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.document_id == document_id
    assert chunk.chunk_index == 0
    assert chunk.page_number.value == 1
    assert "Clausula 1" in chunk.text
    assert "| Contenedor | Tarifa |" in chunk.text
    assert chunk.span.start_char == 0
    assert chunk.span.end_char == len(chunk.text)


@pytest.mark.unit
def test_chunker_splits_long_page_into_multiple_chunks_with_overlap() -> None:
    chunker = MarkdownTableChunker(max_chunk_chars=300, overlap_chars=50)

    long_text = (
        "Sección A: Derechos y obligaciones del fletador y armador en puerto de escala. " * 8
    )
    pages = [
        ParsedPage(
            page_number=2,
            text=long_text,
            tables=[],
        )
    ]

    chunks = chunker.chunk(pages=pages, document_id=DocumentId.generate())

    assert len(chunks) > 1
    # Verify sequential chunk_index
    for idx, c in enumerate(chunks):
        assert c.chunk_index == idx
        assert c.page_number.value == 2
        assert len(c.text) <= 350
        assert c.span.start_char >= 0
        assert c.span.end_char > c.span.start_char


@pytest.mark.unit
def test_chunker_preserves_table_in_its_own_chunk() -> None:
    chunker = MarkdownTableChunker(max_chunk_chars=400, overlap_chars=50)
    table_md = (
        "| Puerto Origen | Puerto Destino | Tarifa Base USD | Días Libres |\n"
        "| --- | --- | --- | --- |\n"
        "| Valencia | Nueva York | 2400 | 10 |\n"
        "| Barcelona | Miami | 2600 | 7 |\n"
        "| Algeciras | Santos | 1900 | 14 |"
    )

    pages = [
        ParsedPage(
            page_number=1,
            text="Tarifario general de transporte marítimo transatlántico.",
            tables=[table_md],
        )
    ]

    chunks = chunker.chunk(pages=pages, document_id=DocumentId.generate())

    # Table is intact in at least one chunk
    table_chunk = next((c for c in chunks if "| Valencia | Nueva York |" in c.text), None)
    assert table_chunk is not None
    assert "| Algeciras | Santos |" in table_chunk.text
