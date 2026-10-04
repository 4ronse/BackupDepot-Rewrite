from sqlmodel import Field

from api.db.mixins import AuditedMixIn, UpdatedMixIn


class AuthProvider(AuditedMixIn, UpdatedMixIn, table=True):
    __tablename__: str = "auth_providers"

    slug: str = Field(index=True, nullable=False, unique=True)
    display_name: str = Field(nullable=False)
    type: str = Field(nullable=False, default="oauth")
    discovery_url: str = Field(nullable=False)
    client_id: str = Field(nullable=False)
    client_secret: bytes = Field(nullable=False)
    scopes: str = Field(nullable=False, default="openid email profile")
    enabled: bool = Field(nullable=False, default=True)
    auto_create_users: bool = Field(nullable=False, default=True)


