from enum import Enum
from sqlmodel import Field

from api.db.mixins import AuditedMixIn, UpdatedMixIn
from api.db.models.audit import EntityType


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
