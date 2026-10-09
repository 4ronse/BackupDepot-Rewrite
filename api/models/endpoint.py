from enum import Enum
from sqlmodel import Field, Session, col, func, select

from api.db.mixins import AuditedMixIn, UpdatedMixIn
from api.db.models.audit import EntityType
from api.models.backup import Backup


class OnLimitAction(str, Enum):
    REJECT = 'REJECT'
    DELETE_OLDEST = 'DELETE_OLDEST'

class Endpoint(AuditedMixIn, UpdatedMixIn, table=True):
    __tablename__: str = "endpoints"
    __entity_type__ = EntityType.ENDPOINT

    name: str = Field(unique=True)
    storage_backend_id: int = Field(foreign_key="storage_backends.id")
    created_by: int = Field(foreign_key="users.id")

    max_backups: int | None = Field(default=None, nullable=True)
    max_age_days: int | None = Field(default=None, nullable=True)
    max_total_bytes: int | None = Field(default=None, nullable=True)
    max_file_size_bytes: int | None = Field(default=None, nullable=True)
    on_limit_action: OnLimitAction = Field(default=OnLimitAction.REJECT, nullable=False)

    def usage(self, session: Session) -> tuple[int, int]:
        count, bytes_total = session.exec(
            select(func.count(), func.coalesce(func.sum(Backup.size_bytes), 0))
            .where(col(Backup.endpoint_id) == self.id)
            .where(col(Backup.status).not_in(Backup.NOT_STORED_STATUSES))
        ).one()

        return count, 0 if bytes_total is None else bytes_total
