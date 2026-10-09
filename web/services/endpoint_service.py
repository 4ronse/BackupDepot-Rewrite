import hashlib

from fastapi import HTTPException
from sqlmodel import Session, col, delete, func, or_, select

from api.db.audit_types import ActorRef
from api.db.utils import utcnow
from api.models.backup import Backup, BackupStatus
from api.models.endpoint import Endpoint
from api.models.upload_key import UploadKey
from web.schemas.endpoint_schemas import EndpointImpact


_NOT_STORED = {BackupStatus.DELETED, BackupStatus.REJECTED, BackupStatus.FAILED}

def compute_impact(session: Session, endpoint_id: int) -> EndpointImpact:
    rows = session.exec(
        select(Backup.status, func.count(), func.sum(Backup.size_bytes))
        .where(Backup.endpoint_id == endpoint_id)
        .group_by(Backup.status)
    ).all()

    by_status = {status: n for status, n, _ in rows}
    n_backups = sum(n for _, n, _ in rows)
    total_bytes = sum(size or 0 for status, _, size in rows if status not in _NOT_STORED)
    in_flight = any(status in Backup.IN_FLIGHT_STATUSES for status, _, _ in rows)

    max_backup_id = session.exec(
        select(func.max(Backup.id)).where(Backup.endpoint_id == endpoint_id)
    ).one()

    active_keys = session.exec(
        select(func.count()).select_from(UploadKey)
        .where(UploadKey.endpoint_id == endpoint_id)
        .where(or_(col(UploadKey.revoked_at).is_(None), col(UploadKey.revoked_at) > utcnow()))
    ).one()

    token = None
    if n_backups or active_keys:
        raw = f'{endpoint_id}|{sorted(by_status.items())}|{max_backup_id}|{active_keys}|{total_bytes}'
        token = hashlib.sha256(raw.encode()).hexdigest()[:16]

    return EndpointImpact(
        upload_keys=active_keys,
        backups=n_backups,
        backups_by_status=by_status,
        total_bytes=total_bytes,
        in_flight=in_flight,
        confirm_token=token,
    )


def delete_endpoint(session: Session, row: Endpoint, actor: ActorRef, confirm: str | None = None):
    impact = compute_impact(session, row.id)  # type: ignore

    if impact.in_flight:
        raise HTTPException(409, detail={
            'message': 'Uploads are in progress on this endpoint. Wait for them to finish.',
            'data': impact.model_dump(),
        })
    if impact.confirm_token is not None and confirm != impact.confirm_token:
        raise HTTPException(409, detail={
            'message': 'This endpoint is in use. Review the impact and resend with ?confirm=<token>.',
            'data': impact.model_dump(),
        })

    session.exec(delete(Backup).where(col(Backup.endpoint_id) == row.id))
    session.exec(delete(UploadKey).where(col(UploadKey.endpoint_id) == row.id))

    row.delete(
        session, actor,
        extra={'impact': impact.model_dump(exclude={'confirm_token'})},
        commit=True,
    )
