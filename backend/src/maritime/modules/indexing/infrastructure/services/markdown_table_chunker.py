from maritime.core.exceptions import InvariantViolationError
from maritime.modules.indexing.domain.entities import DocumentChunk
from maritime.modules.indexing.domain.ports import IChunkingService, ParsedPage
from maritime.modules.indexing.domain.value_objects import ChunkId, PageNumber, TextSpan
from maritime.modules.ingestion.domain.value_objects import DocumentId


class MarkdownTableChunker(IChunkingService):
    """Chunking service that segments text while keeping Markdown tables intact."""

    def __init__(self, max_chunk_chars: int = 800, overlap_chars: int = 100) -> None:
        if max_chunk_chars <= 0:
            raise InvariantViolationError(
                f"max_chunk_chars must be positive, got {max_chunk_chars}."
            )
        if overlap_chars < 0 or overlap_chars >= max_chunk_chars:
            raise InvariantViolationError(
                f"overlap_chars ({overlap_chars}) must be >= 0 and < max_chunk_chars ({max_chunk_chars})."
            )
        self.max_chunk_chars = max_chunk_chars
        self.overlap_chars = overlap_chars

    def chunk(self, pages: list[ParsedPage], document_id: DocumentId) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        global_chunk_idx = 0

        for page in pages:
            page_blocks: list[str] = []

            # 1. Add prose text split by double newlines, and further split very long paragraphs
            if page.text and page.text.strip():
                raw_paragraphs = [p.strip() for p in page.text.split("\n\n") if p.strip()]
                for p in raw_paragraphs:
                    if len(p) > self.max_chunk_chars:
                        page_blocks.extend(self._split_long_text(p))
                    else:
                        page_blocks.append(p)

            # 2. Add structured tables as indivisible blocks
            for table_md in page.tables:
                if table_md and table_md.strip():
                    page_blocks.append(table_md.strip())

            if not page_blocks:
                continue

            # Build full page combined string to calculate accurate character spans
            full_page_content = "\n\n".join(page_blocks)

            if len(full_page_content) <= self.max_chunk_chars:
                chunks.append(
                    DocumentChunk(
                        id=ChunkId.generate(),
                        document_id=document_id,
                        chunk_index=global_chunk_idx,
                        page_number=PageNumber(page.page_number),
                        text=full_page_content,
                        span=TextSpan(0, len(full_page_content)),
                    )
                )
                global_chunk_idx += 1
                continue

            # If page content exceeds max_chunk_chars, assemble chunks preserving table blocks
            current_chunk_blocks: list[str] = []
            current_len = 0
            page_char_offset = 0

            for block in page_blocks:
                block_len = len(block)

                if current_len + block_len + 2 > self.max_chunk_chars and current_chunk_blocks:
                    # Flush current chunk
                    chunk_text = "\n\n".join(current_chunk_blocks)
                    span_start = max(0, page_char_offset)
                    span_end = span_start + len(chunk_text)

                    chunks.append(
                        DocumentChunk(
                            id=ChunkId.generate(),
                            document_id=document_id,
                            chunk_index=global_chunk_idx,
                            page_number=PageNumber(page.page_number),
                            text=chunk_text,
                            span=TextSpan(span_start, span_end),
                        )
                    )
                    global_chunk_idx += 1
                    page_char_offset += len(chunk_text) - self.overlap_chars

                    # Retain last block for overlap if short
                    last_block = current_chunk_blocks[-1]
                    if len(last_block) <= self.overlap_chars:
                        current_chunk_blocks = [last_block, block]
                        current_len = len(last_block) + block_len + 2
                    else:
                        current_chunk_blocks = [block]
                        current_len = block_len
                else:
                    current_chunk_blocks.append(block)
                    current_len += block_len + 2

            if current_chunk_blocks:
                chunk_text = "\n\n".join(current_chunk_blocks)
                span_start = max(0, page_char_offset)
                span_end = span_start + len(chunk_text)

                chunks.append(
                    DocumentChunk(
                        id=ChunkId.generate(),
                        document_id=document_id,
                        chunk_index=global_chunk_idx,
                        page_number=PageNumber(page.page_number),
                        text=chunk_text,
                        span=TextSpan(span_start, span_end),
                    )
                )
                global_chunk_idx += 1

        return chunks

    def _split_long_text(self, text: str) -> list[str]:
        """Splits text longer than max_chunk_chars by sentence boundary or window."""
        sentences = text.replace(". ", ".\n").splitlines()
        pieces: list[str] = []
        cur: list[str] = []
        cur_len = 0

        for s in sentences:
            s_clean = s.strip()
            if not s_clean:
                continue
            if cur_len + len(s_clean) + 1 > self.max_chunk_chars and cur:
                pieces.append(" ".join(cur))
                cur = [s_clean]
                cur_len = len(s_clean)
            else:
                cur.append(s_clean)
                cur_len += len(s_clean) + 1

        if cur:
            pieces.append(" ".join(cur))

        # Fallback: if any piece is still too long, force-split
        final_pieces: list[str] = []
        for piece in pieces:
            if len(piece) > self.max_chunk_chars:
                for i in range(0, len(piece), self.max_chunk_chars - self.overlap_chars):
                    sub = piece[i : i + self.max_chunk_chars].strip()
                    if sub:
                        final_pieces.append(sub)
            else:
                final_pieces.append(piece)

        return final_pieces
