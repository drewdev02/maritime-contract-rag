import re

from maritime.modules.rag.domain.value_objects import Citation, RetrievedChunk


class StrictCitationValidator:
    """Domain service enforcing strict anti-hallucination rules on citations.

    Every citation returned by an LLM must correlate with an actual chunk
    present in the retrieved context. If a snippet is fabricated or the document
    does not match the retrieved context, the citation is rejected.
    """

    def validate(
        self,
        citations: list[Citation],
        context_chunks: list[RetrievedChunk],
    ) -> list[Citation]:
        if not citations or not context_chunks:
            return []

        validated: list[Citation] = []
        chunks_by_doc = {chunk.document_id: chunk for chunk in context_chunks}

        for citation in citations:
            matched_chunk = chunks_by_doc.get(citation.document_id)
            if not matched_chunk:
                # Document was not in retrieved context
                continue

            # Check if snippet text exists within any retrieved chunk for this document
            snippet_cleaned = self._normalize_text(citation.snippet_text)
            if not snippet_cleaned:
                continue

            found_in_chunk = False
            for chunk in context_chunks:
                if chunk.document_id == citation.document_id:
                    normalized_chunk_text = self._normalize_text(chunk.text)
                    if snippet_cleaned in normalized_chunk_text:
                        found_in_chunk = True
                        # Preserve accurate chunk metadata
                        validated.append(
                            Citation(
                                chunk_id=chunk.chunk_id,
                                document_id=chunk.document_id,
                                document_name=chunk.document_name,
                                page_number=chunk.page_number,
                                snippet_text=citation.snippet_text,
                            )
                        )
                        break

            if not found_in_chunk:
                # Text snippet is hallucinated/absent in retrieved context
                continue

        return validated

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Normalizes spaces and casing for substring matching."""
        lowered = text.lower()
        return re.sub(r"\s+", " ", lowered).strip()
