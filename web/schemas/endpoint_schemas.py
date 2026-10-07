from pydantic import Field

from api.models.endpoint import Endpoint, OnLimitAction
from web.schemas.shared import CreateSchema, ReadSchema


class EndpointCreate(CreateSchema[Endpoint]):
    name: str = Field(min_length=1, max_length=100)
    storage_backend_id: int

    max_backups: int | None = None
    max_age_days: int | None = None
    max_total_bytes: int | None = None
    max_file_size_bytes: int | None = None
    on_limit_action: OnLimitAction = OnLimitAction.REJECT

    def row(self, *, created_by: int) -> Endpoint:
        return Endpoint(
            name=self.name,
            storage_backend_id=self.storage_backend_id,
            created_by=created_by,
            max_backups=self.max_backups,
            max_age_days=self.max_age_days,
            max_total_bytes=self.max_total_bytes,
            max_file_size_bytes=self.max_file_size_bytes,
            on_limit_action=self.on_limit_action
        )


class EndpointRead(ReadSchema[Endpoint]):
    id: int
    name: str
    storage_backend_id: int
    created_by: int

    max_backups: int | None
    max_age_days: int | None
    max_total_bytes: int | None
    max_file_size_bytes: int | None
    on_limit_action: OnLimitAction

    @classmethod
    def from_row(cls, row: Endpoint) -> EndpointRead:
        return cls(
            id=row.id,  # type: ignore
            name=row.name,
            storage_backend_id=row.storage_backend_id,
            created_by=row.created_by,
            max_backups=row.max_backups,
            max_age_days=row.max_age_days,
            max_total_bytes=row.max_total_bytes,
            max_file_size_bytes=row.max_file_size_bytes,
            on_limit_action=row.on_limit_action
        )
