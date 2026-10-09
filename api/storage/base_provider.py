from abc import ABC, abstractmethod as abst
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import ClassVar, Iterable, Iterator

from pydantic import BaseModel

from .exceptions import *

CHUNK_SIZE = 4 * 1024 * 1024  # 4 MiB

def format_size(size: int | float) -> str:
    """Format size in bytes to a human-readable string."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"

@dataclass(frozen=True)
class StorageUsage:
    used_bytes: int | None
    total_bytes: int | None
    free_bytes: int | None

    @property
    def usage_percentage(self) -> float | None:
        if self.used_bytes is None or self.total_bytes is None or self.total_bytes == 0:
            return None
        return (self.used_bytes / self.total_bytes) * 100

    def format_size(self) -> tuple[str, str]:
        used = format_size(self.used_bytes) if self.used_bytes is not None else "Unknown"
        total = format_size(self.total_bytes) if self.total_bytes is not None else "Unknown"
        return used, total


@dataclass(frozen=True)
class StoredObject:
    ref: str  # Provider-specific reference to the stored object
    size: int

class StorageType(str, Enum):
    LOCAL = 'LOCAL'
    SAMBA = 'SAMBA'

class EmptyModel(BaseModel): ...


class StorageProvider[C: BaseModel, S: BaseModel](ABC):
    type: ClassVar[StorageType]
    config_model: ClassVar[type[BaseModel]]
    secrets_model: ClassVar[type[BaseModel]]
    location_fields: ClassVar[frozenset[str]] = frozenset()

    def __init__(self, config: C, secrets: S) -> None:
        self.config: C = config
        self.secrets: S = secrets

    @abst
    def check(self) -> None:
        """Raise StorageError if the backend is unusable or unreachable"""

    @abst
    def put(self, key: str, source: Path) -> StoredObject:
        """Store `source` under `key`. On success the provider may move or copy it,
        so the caller deletes the staging file afterwards (missing_ok). On failure
        the source is left untouched, so the move can be retried."""

    @abst
    def stream(self, ref: str) -> Iterator[bytes]:
        """Yield the object in chunks. Raises ObjectNotFound."""

    @abst
    def stream_put(self, key: str, chunks: Iterable[bytes]) -> StoredObject:
        """Store `source` under `key`. On success the provider may move or copy it,
        so the caller deletes the staging file afterwards (missing_ok). On failure
        the source is left untouched, so the move can be retried."""

    @abst
    def delete(self, ref: str) -> None:
        """Idempotent. If file is missing, deletion is still successful."""

    @abst
    def usage(self) -> StorageUsage: ...

def write_stream(provider: StorageProvider, key: str, chunks: Iterable[bytes], *, tmp_dir: Path | None = None) -> StoredObject:
    with NamedTemporaryFile(dir=tmp_dir, delete=True, delete_on_close=False) as tmp:
        for chunk in chunks:
            tmp.write(chunk)
        tmp.close()
        return provider.put(key, Path(tmp.name))
