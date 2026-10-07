import os
from pathlib import Path
import shutil
from typing import Iterator

from pydantic import BaseModel, field_validator

from api.storage.base_provider import StorageUsage
from api.storage.exceptions import ObjectNotFound, StorageError
from api.storage.registry import register

from ..base_provider import CHUNK_SIZE, StorageProvider, EmptyModel, StorageType, StoredObject


__all__ = ['LocalConfig', 'LocalProvider']


class LocalConfig(BaseModel):
    base_path: Path

    @field_validator('base_path')
    @classmethod
    def _absolute(cls, v: Path) -> Path:
        if not v.is_absolute():
            raise ValueError('base_path must be an absolute path')
        return v


@register
class LocalProvider(StorageProvider[LocalConfig, EmptyModel]):
    type = StorageType.LOCAL
    config_model = LocalConfig
    secrets_model = EmptyModel
    location_fields = frozenset({'base_path'})

    def _path(self, ref: str) -> Path:
        if ref.startswith('/'):
            ref = '.' + ref
        root = self.config.base_path.resolve()
        path = (root / ref).resolve()
        if not path.is_relative_to(root):   # block ../ and absolute-path tricks
            raise StorageError('invalid object reference')
        return path

    def check(self) -> None:
        root = self.config.base_path
        root.mkdir(parents=True, exist_ok=True)
        if not os.access(root, os.W_OK):
            raise StorageError('storage directory is not writable')

    def put(self, key: str, source: Path) -> StoredObject:
        dest = self._path(key)
        if not source.is_file():
            raise StorageError('staging file is missing')
        size = source.stat().st_size

        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            raise StorageError('object already exists')

        try:
            os.replace(source, dest)
        except OSError:
            self._copy_in(source, dest)

        return StoredObject(ref=key, size=size)

    @staticmethod
    def _copy_in(source: Path, dest: Path) -> None:
        tmp = dest.with_name(dest.name + '.part')
        try:
            shutil.copyfile(source, tmp)
            with open(tmp, 'rb+') as f:
                os.fsync(f.fileno())
            os.replace(tmp, dest)
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise

    def stream(self, ref: str) -> Iterator[bytes]:
        # Try to open file BEFORE yielding data
        try:
            f = open(self._path(ref), 'rb')
        except FileNotFoundError:
            raise ObjectNotFound(ref) from None

        def chunks() -> Iterator[bytes]:
            with f:
                while chunk := f.read(CHUNK_SIZE):
                    yield chunk
        return chunks()

    def delete(self, ref: str) -> None:
        self._path(ref).unlink(missing_ok=True)

    def exists(self, ref: str) -> bool:
        return self._path(ref).is_file()

    def usage(self) -> StorageUsage:
        res = shutil.disk_usage(self._path('/'))
        return StorageUsage(res.used, res.total, res.free)
