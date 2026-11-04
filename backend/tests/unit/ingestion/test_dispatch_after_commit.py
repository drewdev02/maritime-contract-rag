from collections.abc import Generator
from typing import Annotated, Any

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from maritime.infrastructure.di import deps
from maritime.modules.ingestion.domain.events import DocumentUploadedEvent


class FakeSession:
    def __init__(self, log: list[str]) -> None:
        self._log = log

    async def commit(self) -> None:
        self._log.append("commit")

    async def rollback(self) -> None:
        self._log.append("rollback")

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, *_: Any) -> None:
        return None


@pytest.fixture
def log(monkeypatch: pytest.MonkeyPatch) -> Generator[list[str], None, None]:
    events: list[str] = []
    monkeypatch.setattr(deps, "async_session_factory", lambda: FakeSession(events))
    monkeypatch.setattr(
        deps, "_enqueue_indexing", lambda doc_id: events.append(f"enqueue:{doc_id}")
    )
    yield events


def _client() -> TestClient:
    app = FastAPI()

    @app.post("/upload/{doc_id}")
    async def upload(
        doc_id: str, _: Annotated[Any, Depends(deps.get_db_session)]
    ) -> dict[str, str]:
        await deps._global_event_bus.publish_all(
            [DocumentUploadedEvent(document_id=doc_id, content_hash="h", filename="a.pdf")]
        )
        if doc_id == "boom":
            raise HTTPException(status_code=500, detail="db error")
        return {"ok": doc_id}

    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.unit
def test_indexing_task_is_queued_only_after_the_transaction_commits(log: list[str]) -> None:
    response = _client().post("/upload/doc-1")

    assert response.status_code == 200
    assert log == ["commit", "enqueue:doc-1"]


@pytest.mark.unit
def test_indexing_task_is_not_queued_when_the_request_fails(log: list[str]) -> None:
    response = _client().post("/upload/boom")

    assert response.status_code == 500
    assert "enqueue:boom" not in log
