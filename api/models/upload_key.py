import hashlib
import secrets

from datetime import datetime
from sqlmodel import Field, UniqueConstraint

from api.db.mixins import AuditedMixIn, UpdatedMixIn
from api.db.utc_datetime import UTCDateTime
from api.db.utils import utcnow


def hash_key(key: str) -> str:
    """Hash the key using SHA256 and return the hex digest."""
    return hashlib.sha256(key.encode()).hexdigest()

class UploadKey(AuditedMixIn, UpdatedMixIn, table=True):
    __tablename__: str = "upload_keys"

    __table_args__ = (
        UniqueConstraint('endpoint_id', 'name', name='uq_upload_keys_endpoint_id_name'),
    )

    key_hash: str = Field(index=True, unique=True)
    key_prefix: str = Field(index=True)

    name: str = Field(index=True, unique=True)
    endpoint_id: int = Field(foreign_key="endpoints.id", index=True)
    created_by: int = Field(foreign_key="users.id", index=True)

    last_used_at: datetime | None = UTCDateTime.Field(default=None, nullable=True)
    last_used_ip: str | None = Field(default=None, nullable=True)
    revoked_at: datetime | None = UTCDateTime.Field(default=None, nullable=True)

    def is_revoked(self) -> bool:
        return self.revoked_at is not None and self.revoked_at <= utcnow()

    @classmethod
    def create_key(cls, endpoint_id: int, created_by: int, name: str | None = None) -> tuple['UploadKey', str]:
        plain = 'dpt_' + secrets.token_urlsafe(32)
        key_hash = hash_key(plain)
        key_prefix = plain[:12]
        return cls(endpoint_id=endpoint_id, created_by=created_by, key_hash=key_hash, key_prefix=key_prefix, name=name or key_prefix), plain
