from pydantic import AwareDatetime

from api.models.backup import Backup, BackupStatus
from web.schemas.shared import ReadSchema


class BackupRead(ReadSchema[Backup]):
    endpoint_id: int
    upload_key_id: int
    storage_backend_id: int

    status: BackupStatus
    status_reason: str | None
    size_bytes: int | None
    sha256: str | None
    original_filename: str

    deleted_at: AwareDatetime | None

    download_link: str | None

    @classmethod
    def from_row(cls, row: Backup) -> BackupRead:
        print('REMINDER: IMPLEMENT DOWNLOAD LINK SOMETIME')
        return cls(
            id=row.id,  # type: ignore
            created_at=row.created_at,

            endpoint_id=row.endpoint_id,
            upload_key_id=row.upload_key_id,
            storage_backend_id=row.storage_backend_id,

            status=row.status,
            status_reason=row.status_reason,
            size_bytes=row.size_bytes,
            sha256=row.sha256,
            original_filename=row.original_filename,
            deleted_at=row.deleted_at,
            download_link='IMPLEMENT MEEEEEEE'
        )
