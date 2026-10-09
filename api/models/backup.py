from datetime import datetime
from enum import Enum
from typing import ClassVar

from sqlmodel import Field, Index

from api.db.mixins import AuditedMixIn, UpdatedMixIn
from api.db.utc_datetime import UTCDateTime
from api.db.models.audit import EntityType
from api.db.utils import utcnow


class BackupStatus(str, Enum):
    VALID = 'VALID'  # Backup is done and valid
    UPLOADING_TO_SERVER = 'UPLOADING_TO_SERVER'
    MOVING_TO_STORAGE_BACKEND = 'MOVING_TO_STORAGE_BACKEND'
    DELETING_FROM_STORAGE_BACKEND = 'DELETING_FROM_STORAGE_BACKEND'
    REJECTED = 'REJECTED'
    FAILED = 'FAILED'
    DELETED = 'DELETED'

class Backup(AuditedMixIn, UpdatedMixIn, table=True):
    IN_FLIGHT_STATUSES: ClassVar[set[BackupStatus]] = {
        BackupStatus.UPLOADING_TO_SERVER,
        BackupStatus.MOVING_TO_STORAGE_BACKEND,
        BackupStatus.DELETING_FROM_STORAGE_BACKEND
    }

    NOT_STORED_STATUSES: ClassVar[set[BackupStatus]] = {
        BackupStatus.REJECTED,
        BackupStatus.FAILED,
        BackupStatus.DELETED
    }


    __tablename__: str = "backups"
    __entity_type__ = EntityType.BACKUP
    __audit_name_field__ = 'original_filename'

    __table_args__ = (
        Index('ix_backups_endpoint_status_created', 'endpoint_id', 'status', 'created_at'),
    )

    endpoint_id: int = Field(foreign_key="endpoints.id")
    upload_key_id: int = Field(foreign_key="upload_keys.id", index=True)
    storage_backend_id: int = Field(foreign_key="storage_backends.id")

    status: BackupStatus = Field(default=BackupStatus.UPLOADING_TO_SERVER, nullable=False)
    status_reason: str | None = Field(default=None, nullable=True)

    size_bytes: int | None = Field(default=None, nullable=True)  # Null until done
    sha256: str | None = Field(default=None, nullable=True)  # Null until done

    original_filename: str = Field(nullable=False)
    storage_ref: str = Field(nullable=False)

    deleted_at: datetime | None = UTCDateTime.Field(default=None, nullable=True)

    def set_deleted(self, reason: str = 'Deleted by user'):
        self.status = BackupStatus.DELETED
        self.deleted_at = utcnow()
