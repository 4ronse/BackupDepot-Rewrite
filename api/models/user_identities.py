from datetime import datetime

from sqlmodel import Field, UniqueConstraint

from api.db.mixins import AuditedMixIn
from api.db.utc_datetime import UTCDateTime


class UserIdentity(AuditedMixIn, table=True):
    __tablename__: str = 'user_identities'

    __table_args__ =(
        UniqueConstraint('provider_id', 'subject', name='uq_user_identity_provider_subject'),
        UniqueConstraint('user_id', 'provider_id', name='uq_user_identity_user_provider'),
    )

    user_id: int = Field(foreign_key='users.id', nullable=False)
    provider_id: int = Field(foreign_key='auth_providers.id', nullable=False)
    subject: str = Field(nullable=False)

    last_login_at: datetime | None = UTCDateTime.Field(default=None, nullable=True)
    last_login_ip: str | None = Field(default=None, nullable=True)
