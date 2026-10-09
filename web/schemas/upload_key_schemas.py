from datetime import UTC, datetime, timedelta
from typing import Self

from pydantic import AwareDatetime, Field, field_validator

from api.db.utils import utcnow
from api.models.upload_key import UploadKey
from web.schemas.shared import ReadSchema, Strict


__all__ = ['UploadKeyCreate', 'UploadKeyRead']


class UploadKeyCreate(Strict):
    name: str = Field(min_length=1, max_length=100)
    endpoint_id: int
    expires_in: timedelta | None = Field(
        default=None,
        gt=timedelta(0),
        le=timedelta(days=3650),
        description='ISO 8601 (PT1H, P7D). Omit for a key that never expires.',
    )

    def create(self, *, created_by: int) -> tuple[UploadKey, str]:
        revoke_at = utcnow() + self.expires_in if self.expires_in is not None else None
        return UploadKey.create_key(
            name=self.name,
            endpoint_id=self.endpoint_id,
            revoke_at=revoke_at,
            created_by=created_by,
        )


class UploadKeyRead(ReadSchema[UploadKey]):
    id: int
    endpoint_id: int
    created_by: int
    name: str
    key_prefix: str
    revoked_at: datetime | None
    is_revoked: bool

    last_used_at: datetime | None
    last_used_ip: str | None

    plain: str | None

    @classmethod
    def from_row(cls, row: UploadKey, *, plain: str | None = None) -> Self:
        assert row.id is not None
        return cls(
            id=row.id,
            endpoint_id=row.endpoint_id,
            created_by=row.created_by,
            key_prefix=row.key_prefix,
            name=row.name,
            revoked_at=row.revoked_at,
            is_revoked=row.is_revoked(),

            last_used_at=row.last_used_at,
            last_used_ip=row.last_used_ip,

            created_at=row.created_at,

            plain=plain
        )

