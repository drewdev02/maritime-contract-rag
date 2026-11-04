import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

EVAL_DIR = Path(__file__).resolve().parents[3] / "eval"


def _load_run_eval() -> Any:
    spec = importlib.util.spec_from_file_location("run_eval", EVAL_DIR / "run_eval.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["run_eval"] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.unit
def test_retrieval_quality_does_not_regress_with_mock_embeddings() -> None:
    run_eval = _load_run_eval()
    from maritime.modules.indexing.infrastructure.embeddings.mock_embedding import (
        MockDeterministicEmbeddingAdapter,
    )

    embedder = MockDeterministicEmbeddingAdapter()
    index, _ = run_eval.build_index(embedder, chunk_chars=500, overlap=80)
    result = run_eval.evaluate(embedder, index, threshold=0.25)

    assert result["hit_rate"]["@5"] >= 0.9
    assert result["hit_rate"]["@3"] >= 0.8
    assert result["abstention_rate"] == 1.0
