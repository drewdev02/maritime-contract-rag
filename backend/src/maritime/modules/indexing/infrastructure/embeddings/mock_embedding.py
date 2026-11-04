import hashlib
import math
import random
import re
import unicodedata
from collections.abc import Sequence

from maritime.modules.indexing.domain.ports import IEmbeddingService

_STOPWORDS = frozenset(
    [
        "a",
        "al",
        "con",
        "cual",
        "cuales",
        "cuanto",
        "cuantos",
        "cuanta",
        "cuantas",
        "de",
        "del",
        "el",
        "en",
        "es",
        "la",
        "las",
        "lo",
        "los",
        "o",
        "para",
        "por",
        "que",
        "se",
        "si",
        "su",
        "sus",
        "un",
        "una",
        "y",
        "e",
        "como",
        "donde",
        "qué",
    ]
)


def _tokenize(text: str) -> list[str]:
    """Lowercases, strips accents and drops Spanish stopwords so that content words dominate."""
    folded = "".join(
        c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn"
    )
    return [w for w in re.findall(r"\w+", folded) if w not in _STOPWORDS]


class MockDeterministicEmbeddingAdapter(IEmbeddingService):
    """Deterministic, normalized 768-dimensional embedding adapter for testing and offline RAG.

    Uses word-level hash projection to ensure that texts sharing domain keywords
    (e.g., 'demoras', 'días', 'tarifa', 'TEU') have positive, measurable semantic similarity,
    while orthogonal texts yield near-zero similarity.
    """

    DIMENSION = 768

    def embed_text(self, text: str) -> list[float]:
        words = _tokenize(text)
        if not words:
            words = ["empty"]

        vector = [0.0] * self.DIMENSION
        for word in words:
            hash_bytes = hashlib.sha256(word.encode("utf-8")).digest()
            seed = int.from_bytes(hash_bytes[:8], byteorder="big")
            rng = random.Random(seed)
            for i in range(self.DIMENSION):
                vector[i] += rng.gauss(0.0, 1.0)

        # L2-normalize vector to unit length
        norm = math.sqrt(sum(x * x for x in vector))
        if norm == 0.0:
            norm = 1.0

        return [x / norm for x in vector]

    def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        return [self.embed_text(t) for t in texts]
