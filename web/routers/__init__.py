from pathlib import Path
import secrets
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Header, Request, UploadFile
from starlette.requests import ClientDisconnect

from api.models.backup import Backup, BackupStatus
from api.models.endpoint import Endpoint, OnLimitAction
from api.models.storage_backend import StorageBackend
from api.models.upload_key import UploadKey
from api.storage.exceptions import StorageError
from web import services
from web.deps import ActorDep, SessionDep, UploadKeyDep, UserDep
from web.responses import ResponseModel, ok
from web.schemas.backup_schemas import BackupRead

from .storage_router import router as storage_router
from .endpoint_router import router as endpoint_router
from .audit_router import router as audit_router
from .upload_key_router import router as key_router
from .backup_router import router as backup_router

router = APIRouter(prefix='/api', tags=['api'])
router.include_router(storage_router)
router.include_router(endpoint_router)
router.include_router(audit_router)
router.include_router(key_router)
router.include_router(backup_router)


@router.put('/ingest', response_model=ResponseModel[BackupRead])
def ingest(
    request: Request,
    session: SessionDep,
    key: UploadKeyDep,
    actor: ActorDep,
    x_content_sha256: Annotated[str, Header(pattern=r'^[0-9a-fA-F]{64}$')],
    content_length: Annotated[int | None, Header()] = None,
    x_filename: Annotated[str, Header(min_length=1, max_length=255)] = 'backup'
):
    if content_length is None:
        raise HTTPException(411, 'Content-Length is required')
    if content_length <= 0:
        raise HTTPException(400, 'empty upload')

    endpoint = Endpoint.get_or_404(session, key.endpoint_id)  # type: ignore
    backend = StorageBackend.get_or_404(session, endpoint.storage_backend_id)  # type: ignore
    provider = backend.provider()

    count, total = endpoint.usage(session)
    backup = Backup(
        endpoint_id=endpoint.id,  # type: ignore
        storage_backend_id=backend.id,  # type: ignore
        upload_key_id=key.id,  # type: ignore
        status=BackupStatus.UPLOADING_TO_SERVER,
        original_filename=Path(x_filename).name or 'backup',
        storage_ref=secrets.token_hex(8)
    )
    backup.insert(session, key.actor_ref, commit=True)
    ref = f'{endpoint.id}/{backup.storage_ref}'

    if endpoint.max_file_size_bytes and content_length > endpoint.max_file_size_bytes:
        services.ingest.stop(session, actor, backup, BackupStatus.REJECTED, 413, "file exceeds endpoint's max file size")

    if endpoint.on_limit_action == OnLimitAction.REJECT:
        if endpoint.max_backups and count + 1 > endpoint.max_backups:
            services.ingest.stop(session, actor, backup, BackupStatus.REJECTED, 409, 'endpoint backup count limit reached')
        if endpoint.max_total_bytes and total + content_length > endpoint.max_total_bytes:
            services.ingest.stop(session, actor, backup, BackupStatus.REJECTED, 507, 'endpoint storage limit reached')

    body = services.ingest.Ingest(request)
    try:
        stored = provider.stream_put(ref, body)
    except ClientDisconnect:
        services.ingest.stop(session, actor, backup, BackupStatus.FAILED, 400, 'client disconnected mid-upload')
    except StorageError as e:
        services.ingest.stop(session, actor, backup, BackupStatus.FAILED, 502, f'storage error: {e}', public='storage backend error')
    except Exception:
        backup.status = BackupStatus.FAILED
        backup.status_reason = 'internal error'
        raise

    digest = body.sha.hexdigest()
    if body.size != content_length:
        services.ingest.discard(provider, ref)
        services.ingest.stop(session, actor, backup, BackupStatus.FAILED, 400, f'received {body.size} of {content_length} bytes')
    if digest != x_content_sha256.lower():
        services.ingest.discard(provider, ref)
        services.ingest.stop(session, actor, backup, BackupStatus.REJECTED, 422, f'SHA-256 mismatch: the file was corrupted or altered in transit')

    backup.status = BackupStatus.VALID
    backup.size_bytes = stored.size
    backup.sha256 = digest
    backup.update(session, actor, commit=True)

    return ok(data=BackupRead.from_row(backup))



