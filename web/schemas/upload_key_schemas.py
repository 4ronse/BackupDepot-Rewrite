from datetime import UTC, datetime
from typing import Self

from pydantic import AwareDatetime, Field, field_validator

from api.models.upload_key import UploadKey
from web.schemas.shared import ReadSchema, Strict


__all__ = ['UploadKeyCreate', 'UploadKeyRead']


class UploadKeyCreate(Strict):
    name: str = Field(min_length=1, max_length=100)
    endpoint_id: int
    revoke_at: AwareDatetime | None = None  # None = never expires

    @field_validator('revoke_at')
    @classmethod
    def _in_future(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return None
        v = v.astimezone(UTC)
        if v <= datetime.now(UTC):
            raise ValueError('revoke_at must be in the future')
        return v

    def create(self, *, created_by: int) -> tuple[UploadKey, str]:
        return UploadKey.create_key(
            name=self.name,
            endpoint_id=self.endpoint_id,
            revoke_at=self.revoke_at,
            created_by=created_by,
        )


class UploadKeyRead(ReadSchema[UploadKey]):
    id: int
    endpoint_id: int
    name: str
    revoked_at: datetime | None

    @classmethod
    def from_row(cls, row: UploadKey) -> Self:
        assert row.id is not None
        return cls(
            id=row.id,
            endpoint_id=row.endpoint_id,
            name=row.name,
            revoked_at=row.revoked_at,
        )
