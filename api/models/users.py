from datetime import datetime
from enum import Enum
from typing import NoReturn
from sqlmodel import Field

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError

from api.db.mixins import AuditedMixIn, UpdatedMixIn
from api.db.mixins.audited_mixin import ActorMixIn
from api.db.secret_box import SecretBox
from api.db.utc_datetime import UTCDateTime
from api.db.audit_types import Actor, ActorRef, EntityType


_ph = PasswordHasher()
_DUMMY_HASH = _ph.hash('timing-equalizer')


class Role(str, Enum):
    ADMIN = 'ADMIN'
    ROOT = 'ROOT'


class UserStatus(str, Enum):
    ACTIVE = 'ACTIVE'
    DISABLED = 'DISABLED'
    DELETED = 'DELETED'


class User(AuditedMixIn, UpdatedMixIn, ActorMixIn, table=True):
    __tablename__: str = 'users'
    __actor_type__ = Actor.USER
    __entity_type__ = EntityType.USER
    __audit_redacted__ = frozenset({'password_hash'})

    name: str
    email: str = Field(index=True, nullable=False, unique=True)
    password_hash: str | None = Field(default=None, nullable=True)
    role: Role = Field(default=Role.ADMIN, nullable=False)
    user_status: UserStatus = Field(default=UserStatus.ACTIVE, nullable=False)

    last_login_at: datetime | None = UTCDateTime.Field(default=None, nullable=True)
    last_login_ip: str | None = Field(default=None, nullable=True)

    @property
    def password(self) -> NoReturn:
        raise AttributeError('password is write-only; use verify_password()')

    @password.setter
    def password(self, new: str) -> None:
        self.set_password(new)

    @password.setter
    def password(self, new: str) -> None:
        self.set_password(new)

    def set_password(self, new: str) -> None:
        self.password_hash = _ph.hash(new)

    def verify_password(self, password: str) -> bool:
        try:
            _ph.verify(self.password_hash or _DUMMY_HASH, password)
        except (VerificationError | InvalidHashError):
            return False
        return self.password_hash is not None

    @staticmethod
    def hash(password: str | bytes) -> str:
        return _ph.hash(password)
