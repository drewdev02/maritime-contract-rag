import asyncio
from pathlib import Path

from maritime.modules.ingestion.domain.ports import IFileStorage


class LocalFileStorageAdapter(IFileStorage):
    """Local filesystem adapter for contract document PDF storage."""

    def __init__(self, base_path: str = "storage/contracts") -> None:
        self._base_path = Path(base_path)

    def _resolve_path(self, file_path: str) -> Path:
        path = Path(file_path)
        if path.is_absolute():
            return path
        candidate = self._base_path / path
        if candidate.exists():
            return candidate
        return path

    async def save(self, doc_id: str, filename: str, content: bytes) -> str:
        doc_dir = self._base_path / doc_id
        target_path = doc_dir / filename

        def _write() -> None:
            doc_dir.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(content)

        await asyncio.to_thread(_write)
        return str(target_path)

    async def read(self, file_path: str) -> bytes:
        resolved = self._resolve_path(file_path)
        return await asyncio.to_thread(resolved.read_bytes)

    async def exists(self, file_path: str) -> bool:
        resolved = self._resolve_path(file_path)
        return await asyncio.to_thread(resolved.is_file)
