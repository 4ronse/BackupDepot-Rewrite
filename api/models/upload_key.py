import hashlib
import secrets

from datetime import datetime
from fastapi import HTTPException
from sqlmodel import Field, Session, UniqueConstraint, select

from api.db.audit_types import Actor, ActorRef, EntityType
from api.db.mixins import AuditedMixIn, UpdatedMixIn
from api.db.mixins.audited_mixin import ActorMixIn
from api.db.utc_datetime import UTCDateTime
from api.db.utils import utcnow


def hash_key(key: str) -> str:
    """Hash the key using SHA256 and return the hex digest."""
    return hashlib.sha256(key.encode()).hexdigest()

class UploadKey(AuditedMixIn, UpdatedMixIn, ActorMixIn, table=True):
    __tablename__: str = "upload_keys"
    __entity_type__ = EntityType.UPLOAD_KEY
    __actor_type__ = Actor.UPLOAD_KEY

    __table_args__ = (
        UniqueConstraint('endpoint_id', 'name', name='uq_upload_keys_endpoint_id_name'),
    )

    key_hash: str = Field(index=True, unique=True)
    key_prefix: str = Field(index=True)

    name: str = Field(index=True)
    endpoint_id: int = Field(foreign_key="endpoints.id", index=True)
    created_by: int = Field(foreign_key="users.id", index=True)

    last_used_at: datetime | None = UTCDateTime.Field(default=None, nullable=True)
    last_used_ip: str | None = Field(default=None, nullable=True)
    revoked_at: datetime | None = UTCDateTime.Field(default=None, nullable=True)

    def is_revoked(self) -> bool:
        return self.revoked_at is not None and self.revoked_at <= utcnow()

    @classmethod
    def create_key(cls, endpoint_id: int, created_by: int, name: str | None = None, revoke_at: datetime | None = None) -> tuple['UploadKey', str]:
        plain = 'dpt_' + secrets.token_urlsafe(32)
        key_hash = hash_key(plain)
        key_prefix = plain[:12]
        return cls(endpoint_id=endpoint_id, created_by=created_by, key_hash=key_hash, key_prefix=key_prefix, name=name or key_prefix, revoked_at=revoke_at), plain

    @classmethod
    def find_key(cls, session: Session, plain: str) -> UploadKey | None:
        key_hash = hash_key(plain)
        return session.exec(select(UploadKey).where(UploadKey.key_hash == key_hash)).one_or_none()

    @classmethod
    def find_key_or_404(cls, session: Session, plain: str) -> UploadKey:
        if (k := cls.find_key(session, plain)) is not None:
            return k
        raise HTTPException(404, 'Key not found.')
