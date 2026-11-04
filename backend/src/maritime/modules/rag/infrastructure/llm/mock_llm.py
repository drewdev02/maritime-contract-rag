import asyncio
import re
from collections.abc import AsyncIterator

from maritime.modules.rag.domain.ports import ILlmService
from maritime.modules.rag.domain.value_objects import (
    Citation,
    RagResponse,
    RetrievedChunk,
    StreamChunk,
    StreamDeltaChunk,
    StreamMetaChunk,
)


class MockDeterministicLlmAdapter(ILlmService):
    """Deterministic LLM adapter for offline testing and zero-config evaluation.

    Synthesizes rule-based answers quoting real snippet text from retrieved chunks
    or returns an explicit abstention response when evidence is insufficient.
    """

    async def generate_answer(
        self,
        query: str,
        context_chunks: list[RetrievedChunk],
    ) -> RagResponse:
        query_lower = query.lower()

        # Case 0: Greetings and conversational inquiries
        if any(
            g in query_lower
            for g in [
                "hola",
                "buenos dias",
                "buenos días",
                "buenas tardes",
                "buenas noches",
                "saludos",
                "ayuda",
                "quien eres",
                "quién eres",
                "que puedes hacer",
                "qué puedes hacer",
            ]
        ):
            return RagResponse(
                answer=(
                    "¡Hola! Soy el asistente inteligente de Naviera Portecho especializado en contratos marítimos. "
                    "Puedo responder consultas sobre tarifas TEU, cláusulas de demoras, fletes y condiciones operativas "
                    "basándome en los contratos indexados. ¿En qué puedo asistirte hoy?"
                ),
                citations=[],
                has_sufficient_evidence=True,
                confidence_score=None,
            )

        if not context_chunks:
            return self._insufficient_evidence()

        # Case 1: Demurrage / Demoras queries
        if any(
            term in query_lower
            for term in ["demora", "demurrage", "dias", "días", "libre", "plazo"]
        ):
            for chunk in context_chunks:
                text_lower = chunk.text.lower()
                if (
                    "demora" in text_lower
                    or "días libres" in text_lower
                    or "dias libres" in text_lower
                ):
                    snippet = self._extract_snippet(
                        chunk.text, ["demora", "días libres", "dias libres"]
                    )
                    answer = (
                        f"De acuerdo con lo estipulado en el contrato {chunk.document_name} "
                        f"(página {chunk.page_number}), se especifica: '{snippet}'."
                    )
                    citation = Citation(
                        chunk_id=chunk.chunk_id,
                        document_id=chunk.document_id,
                        document_name=chunk.document_name,
                        page_number=chunk.page_number,
                        snippet_text=snippet,
                    )
                    return RagResponse(
                        answer=answer,
                        citations=[citation],
                        has_sufficient_evidence=True,
                        confidence_score=chunk.similarity_score,
                    )

        # Case 2: TEU / Tarifa / Rate queries
        if any(
            term in query_lower for term in ["tarifa", "teu", "precio", "costo", "rate", "valor"]
        ):
            for chunk in context_chunks:
                text_lower = chunk.text.lower()
                if "teu" in text_lower or "tarifa" in text_lower or "$" in text_lower:
                    snippet = self._extract_snippet(chunk.text, ["teu", "tarifa", "$"])
                    answer = (
                        f"Conforme a los términos contractuales de {chunk.document_name} "
                        f"(página {chunk.page_number}), se establece la condición tarifaria: '{snippet}'."
                    )
                    citation = Citation(
                        chunk_id=chunk.chunk_id,
                        document_id=chunk.document_id,
                        document_name=chunk.document_name,
                        page_number=chunk.page_number,
                        snippet_text=snippet,
                    )
                    return RagResponse(
                        answer=answer,
                        citations=[citation],
                        has_sufficient_evidence=True,
                        confidence_score=chunk.similarity_score,
                    )

        # Case 3: General maritime match
        # If top chunk has high similarity and matches any substantive words from query
        query_words = [w for w in re.findall(r"\w+", query_lower) if len(w) > 4]
        for chunk in context_chunks:
            chunk_lower = chunk.text.lower()
            matching_words = [w for w in query_words if w in chunk_lower]
            if len(matching_words) >= 2:
                snippet = chunk.text[:120].strip()
                answer = (
                    f"Según el documento {chunk.document_name} (página {chunk.page_number}), "
                    f"se registra la siguiente disposición relevante: '{snippet}'."
                )
                citation = Citation(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    document_name=chunk.document_name,
                    page_number=chunk.page_number,
                    snippet_text=snippet,
                )
                return RagResponse(
                    answer=answer,
                    citations=[citation],
                    has_sufficient_evidence=True,
                    confidence_score=chunk.similarity_score,
                )

        # Default: Abstention
        return self._insufficient_evidence()

    @staticmethod
    def _extract_snippet(text: str, keywords: list[str]) -> str:
        for line in text.splitlines():
            line_clean = line.strip()
            line_lower = line_clean.lower()
            if any(k in line_lower for k in keywords) and len(line_clean) > 10:
                return line_clean
        # Fallback to first line or 100 characters
        return text.strip()[:100]

    @staticmethod
    def _insufficient_evidence() -> RagResponse:
        return RagResponse(
            answer="No hay evidencia suficiente en los contratos disponibles para responder a esta pregunta.",
            citations=[],
            has_sufficient_evidence=False,
            confidence_score=0.0,
        )

    async def generate_answer_stream(
        self,
        query: str,
        context_chunks: list[RetrievedChunk],
    ) -> AsyncIterator[StreamChunk]:
        """Streams deterministic answer word-by-word followed by metadata chunk."""
        full_response = await self.generate_answer(query, context_chunks)
        words = full_response.answer.split(" ")
        for i, word in enumerate(words):
            delta = word if i == 0 else " " + word
            yield StreamDeltaChunk(delta=delta)
            await asyncio.sleep(0.005)

        yield StreamMetaChunk(
            citations=full_response.citations,
            has_sufficient_evidence=full_response.has_sufficient_evidence,
            confidence_score=full_response.confidence_score,
        )
