import hashlib

from fastapi import HTTPException
from sqlmodel import Session, and_, col, delete, func, select

from api.db.audit_types import ActorRef
from api.models.backup import Backup, BackupStatus
from api.models.endpoint import Endpoint
from api.models.storage_backend import StorageBackend
from api.models.upload_key import UploadKey
from web.schemas import EndpointRef, StorageBackendImpact


__all__ = ['compute_impact', 'delete_backend', 'has_backups']


def compute_impact(session: Session, backend_id: int) -> StorageBackendImpact:
    endpoints = session.exec(
        select(Endpoint.id, Endpoint.name)
        .where(Endpoint.storage_backend_id == backend_id)
        .order_by(col(Endpoint.id))
    ).all()

    backups = session.exec(
        select(Backup.status, func.count(), func.sum(Backup.size_bytes))
        .where(Backup.storage_backend_id == backend_id)
        .group_by(Backup.status)
    ).all()

    by_status = {status: n for status, n, _ in backups}
    n_backups = sum(n for _, n, _ in backups)
    total_bytes = sum(size or 0 for _, _, size in backups)
    in_flight = any(status in Backup.IN_FLIGHT_STATUSES for status, _, _ in backups)

    max_backup_id = session.exec(
        select(func.max(Backup.id)).where(Backup.storage_backend_id == backend_id)
    ).one()

    """
    SELECT COUNT(*)
    FROM upload_keys
    JOIN endpoints
        ON upload_keys.endpoint_id = endpoints.id
    WHERE endpoints.storage_backend_id = :backend_id;
    """

    # upload keys belong to endpoints, so count them through the join
    n_upload_keys = session.exec(
        select(func.count()).select_from(UploadKey)
        .join(Endpoint, col(UploadKey.endpoint_id) == col(Endpoint.id))
        .where(Endpoint.storage_backend_id == backend_id)
    ).one()

    token = None
    if endpoints or n_backups:
        ids = [id_ for id_, _ in endpoints]
        raw = f'{backend_id}|{ids}|{n_backups}|{max_backup_id}|{n_upload_keys}'
        token = hashlib.sha256(raw.encode()).hexdigest()[:16]

    return StorageBackendImpact(
        endpoints=[EndpointRef(id=id_, name=name) for id_, name in endpoints],  # type: ignore
        upload_keys=n_upload_keys,
        backups=n_backups,
        backups_by_status=by_status,
        total_bytes=total_bytes,
        in_flight=in_flight,
        confirm_token=token,
    )


def has_backups(session, id_or_row: int | StorageBackend) -> bool:
    row: StorageBackend
    if isinstance(id_or_row, StorageBackend):
        row = id_or_row
    else:
        row = StorageBackend.get_or_404(session, id_or_row)
    return Backup.find_one(
        session,
        and_(Backup.storage_backend_id == row.id, col(Backup.status).not_in([
            BackupStatus.DELETED, BackupStatus.REJECTED, BackupStatus.FAILED
        ]))
    ) is not None


def delete_backend(session: Session, row: StorageBackend, actor: ActorRef, confirm: str | None = None):
    impact = compute_impact(session, row.id)  # type: ignore

    if impact.in_flight:
        raise HTTPException(409, detail={
            'message': 'Uploads are in progress on this endpoint. Wait for them to finish.',
            'impact': impact.model_dump(),
        })
    if impact.confirm_token is not None and confirm != impact.confirm_token:
        raise HTTPException(409, detail={
            'message': 'This endpoint is in use. Review the impact and resend with ?confirm=<token>.',
            'impact': impact.model_dump(),
        })

    session.exec(delete(Backup).where(col(Backup.storage_backend_id) == row.id))
    session.exec(delete(UploadKey).where(
        col(UploadKey.endpoint_id).in_(
            select(Endpoint.id).where(Endpoint.storage_backend_id == row.id)
        )
    ))
    session.exec(delete(Endpoint).where(col(Endpoint.storage_backend_id) == row.id))

    row.delete(session, actor, extra={'impact': impact.model_dump(exclude={'confirm_keys'})}, commit=True)
