import errno
import posixpath
import smbclient

from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Iterable, Iterator

from pydantic import BaseModel, Field, field_validator
from smbprotocol.exceptions import (
    AccessDenied, BadNetworkName, LogonFailure,
    SMBAuthenticationError, SMBConnectionClosed, SMBOSError,
)
from api.storage.base_provider import CHUNK_SIZE, StorageProvider, StorageType, StorageUsage, StoredObject
from api.storage.exceptions import ObjectNotFound, StorageAuthError, StorageError, StorageUnavailable
from api.storage.registry import register


__all__ = ['SMBConfig', 'SMBSecrets', 'SMBProvider']


class SMBConfig(BaseModel):
    host: str = Field(min_length=1)
    username: str = Field(min_length=1)
    share: str = Field(min_length=1)
    port: int = Field(default=445, ge=1, le=65535)
    base_path: str = ''
    domain: str | None = None
    encrypt: bool = False
    connection_timeout: int = Field(default=30, ge=1, le=300)

    @field_validator('host', 'share')
    @classmethod
    def _no_slashes(cls, v: str) -> str:
        if '/' in v or '\\' in v:
            raise StorageError('must not contain slashes')
        return v

    @field_validator('base_path')
    @classmethod
    def _clean_path(cls, v: str) -> str:
        parts = [p for p in v.replace('\\', '/').split('/') if p]
        if '..' in parts:
            raise StorageError("'..' is not allowed")
        return '/'.join(parts)  # normalised, never leading or trailing slash

class SMBSecrets(BaseModel):
    password: str = Field(
        min_length=1,
        json_schema_extra={'format': 'password'}
    )


@register
class SMBProvider(StorageProvider[SMBConfig, SMBSecrets]):
    type = StorageType.SAMBA
    config_model = SMBConfig
    secrets_model = SMBSecrets
    location_fields = frozenset({'share', 'base_path'})

    @contextmanager
    def _conn(self):
        c = self.config
        cache: dict = {}
        user = f'{c.domain}\\{c.username}' if c.domain else c.username
        try:
            smbclient.register_session(
                c.host,
                username=user,
                password=self.secrets.password,
                port=c.port,
                encrypt=c.encrypt,
                connection_timeout=c.connection_timeout,
                connection_cache=cache,
            )
            yield {'connection_cache': cache, 'port': c.port}
        finally:
            smbclient.reset_connection_cache(connection_cache=cache)

    @contextmanager
    def _errors(self):
        """Translate smbprotocol/OS errors into the StorageError family. Wrap every operation."""
        c = self.config
        try:
            yield
        except StorageError:
            raise
        except (SMBAuthenticationError, LogonFailure, AccessDenied) as e:
            raise StorageAuthError('Login or permission denied.') from e
        except BadNetworkName as e:
            raise StorageUnavailable(f"Share '{c.share}' does not exist on {c.host}.") from e
        except SMBOSError as e:
            if e.errno in (errno.EACCES, errno.EPERM):
                raise StorageAuthError('Permission denied on the share or folder.') from e
            if e.errno == errno.ENOENT:
                raise ObjectNotFound(str(e)) from e
            raise StorageError(f'SMB error: {e}') from e
        except (SMBConnectionClosed, TimeoutError, ConnectionError, OSError) as e:
            raise StorageUnavailable(f'Cannot reach {c.host}:{c.port}.') from e

    def _unc(self, ref: str = '') -> str:
        # Universal Naming Convention
        def split(p: str) -> list[str]:
            return [s for s in p.replace('\\', '/').split('/') if s]

        parts = split(ref)
        if '..' in parts:
            raise StorageError('invalid storage ref')
        tail = '\\'.join([*split(self.config.base_path), *parts])
        root = f'\\\\{self.config.host}\\{self.config.share}'
        return f'{root}\\{tail}' if tail else root

    def check(self) -> None:
        with self._errors(), self._conn() as kw:
            if self.config.base_path:
                smbclient.makedirs(self._unc(), exist_ok=True, **kw)
            smbclient.listdir(self._unc(), **kw)

    def delete(self, ref: str) -> None:
        with self._errors(), self._conn() as kw:
            try:
                smbclient.unlink(self._unc(ref), **kw)
            except SMBOSError as e:
                if e.errno != errno.ENOENT:  # already gone is success
                    raise

    def put(self, key: str, source: Path) -> StoredObject:
        with source.open('rb') as f:
            return self.stream_put(key, iter(lambda: f.read(CHUNK_SIZE), b''))

    def stream_put(self, key: str, chunks: Iterable[bytes]) -> StoredObject:
        c = self.config
        dst = self._unc(key)
        tmp = dst + '.part'
        size = 0

        with self._errors(), self._conn() as kw:
            parent = self._unc(posixpath.dirname(key.replace('\\', '/')))
            if parent != f'\\\\{c.host}\\{c.share}':
                smbclient.makedirs(parent, exist_ok=True, **kw)
            try:
                with smbclient.open_file(tmp, 'wb', **kw) as out:
                    for chunk in chunks:
                        out.write(chunk)
                        size += len(chunk)
                smbclient.replace(tmp, dst, **kw)
            except BaseException:
                try:
                    smbclient.unlink(tmp, **kw)
                except Exception:
                    pass
                raise
        return StoredObject(key, size)

    def stream(self, ref: str) -> Iterator[bytes]:
        with self._errors():
            stack = ExitStack()

            try:
                kw = stack.enter_context(self._conn())
                file = stack.enter_context(smbclient.open_file(self._unc(ref), 'rb', **kw))
                first = file.read(CHUNK_SIZE)
            except BaseException:
                stack.close()
                raise

            def chunks() -> Iterator[bytes]:
                try:
                    chunk = first

                    while chunk:
                        yield chunk
                        chunk = file.read(CHUNK_SIZE)
                finally:
                    stack.close()

            return chunks()

    def usage(self) -> StorageUsage:
        with self._errors(), self._conn() as kw:
            total, caller_available, _actual = smbclient.stat_volume(self._unc(), **kw)
        return StorageUsage(
            used_bytes=total - caller_available,
            total_bytes=total,
            free_bytes=caller_available,
        )

