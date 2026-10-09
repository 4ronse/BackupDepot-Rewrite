import hashlib
import logging
from typing import Iterator, NoReturn
import anyio
from fastapi import HTTPException, Request
from sqlmodel import Session, col, select

from api.db.audit_types import ActorRef
from api.models.backup import Backup, BackupStatus
from api.models.endpoint import Endpoint
from api.storage.base_provider import StorageProvider
from api.storage.exceptions import StorageError

_LOGGER = logging.getLogger(__name__)


class Ingest:
    def __init__(self, request: Request):
        self._chunks = request.stream().__aiter__()
        self.size = 0
        self.sha = hashlib.sha256()

    async def _next(self) -> bytes:
        try:
            return await self._chunks.__anext__()
        except StopAsyncIteration:
            return b''

    def __iter__(self) -> Iterator[bytes]:
        while chunk := anyio.from_thread.run(self._next):
            self.size += len(chunk)
            self.sha.update(chunk)
            yield chunk

def stop(session: Session, actor: ActorRef, backup: Backup, status: BackupStatus, http_status: int, reason: str, public: str | None = None, commit: bool = False) -> NoReturn:
    backup.status = status
    backup.reason = reason
    backup.update(session, actor, commit=commit)
    raise HTTPException(http_status, public or reason)

def discard(provider: StorageProvider, ref: str) -> None:
    """A for effort..."""
    try:
        provider.delete(ref)
    except StorageError as e:
        _LOGGER.warning(f'Failed to delete `{ref}`', exc_info=e)

def evict_oldest(session: Session, actor: ActorRef, endpoint: Endpoint, provider: StorageProvider, commit: bool = False) -> None:
    while True:
        count, total = endpoint.usage(session)
        over = (endpoint.max_backups and count > endpoint.max_backups) \
                or (endpoint.max_total_bytes and total > endpoint.max_total_bytes)
        if not over:
            return

        oldest = session.exec(
            select(Backup)
            .where(col(Backup.endpoint_id) == endpoint.id)
            .where(col(Backup.status) == BackupStatus.VALID)
            .order_by(col(Backup.created_at), col(Backup.id))
        ).first()

        if oldest is None:
            return

        try:
            assert oldest.storage_ref is not None
            provider.delete(oldest.storage_ref)
        except StorageError as e:
            _LOGGER.warning('Failed to evict oldest backup', exc_info=e)
            raise HTTPException(500, 'Failed to evict oldest backup')

        oldest.set_deleted('Oldest evicted')
        oldest.update(session, actor, commit=commit)
