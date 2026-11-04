# Backend

API FastAPI y worker Celery del asistente RAG de contratos. La documentación general (cómo
levantarlo, pruebas, evaluación) está en el [README principal](../README.md) y el diseño en
[`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md).

```bash
uv sync --dev
uv run ruff check . && uv run mypy src tests
uv run pytest -m unit
uv run pytest -m integration            # requiere Docker
uv run python eval/run_eval.py          # evaluación de recuperación
uv run alembic upgrade head             # migraciones
```
