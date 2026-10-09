from urllib.parse import quote

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from api.db.audit_types import Operation
from api.db.models.audit import Audit
from api.models.backup import Backup, BackupStatus
from api.models.storage_backend import StorageBackend
from web.deps import ActorDep, SessionDep
from web.responses import ResponseModel as RM, ok
from web.schemas.backup_schemas import BackupRead


router = APIRouter(prefix='/backups', tags=['storage'])

@router.get('/{id}', response_model=RM[BackupRead])
def get_single_backup(id: int, session: SessionDep):
    return ok(data=BackupRead.from_row(Backup.get_or_404(session, id)))

@router.get('/{id}/download')
def download_backup(id: int, session: SessionDep, acotr: ActorDep):
    row = Backup.get_or_404(session, id)
    sb = StorageBackend.get_or_404(session, row.storage_backend_id)

    if not row.status == BackupStatus.VALID:
        raise HTTPException(404, 'Backup not found')

    Audit.record(
        session,
        actor_ref=acotr,
        entity_ref=row.entity_ref,
        operation=Operation.DOWNLOAD,
    )
    session.commit()

    return StreamingResponse(
        sb.provider().stream(f'{row.endpoint_id}/{row.storage_ref}'),
        media_type='application/octet-stream',
        headers={
            'Content-Disposition': f"attachment; filename*=UTF-8''{quote(row.original_filename, safe='')}",
            'X-Checksum-SHA256': row.sha256  # type: ignore
        },
    )
