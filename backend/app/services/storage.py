"""Where prescription images live.

Behind a protocol so the local directory can be replaced with S3 without
touching callers. Keys are random and carry no user data.
"""

from __future__ import annotations

import secrets
from pathlib import Path
from typing import Protocol

from app.core.config import get_settings


class Storage(Protocol):
    def put(self, data: bytes, suffix: str = ".jpg") -> str: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...


class LocalStorage:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        # Keys are generated here, but never trust one that comes back in.
        if not key or "/" in key or "\\" in key or key.startswith("."):
            raise ValueError("invalid storage key")
        return self.root / key

    def put(self, data: bytes, suffix: str = ".jpg") -> str:
        key = f"{secrets.token_hex(16)}{suffix}"
        self._path(key).write_bytes(data)
        return key

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


_storage: Storage | None = None


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        _storage = LocalStorage(get_settings().storage_dir)
    return _storage


def set_storage(storage: Storage) -> None:
    global _storage
    _storage = storage
