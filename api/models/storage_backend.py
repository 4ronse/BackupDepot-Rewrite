from typing import Any

from sqlmodel import JSON, Column, Field

from api.db.mixins import AuditedMixIn, UpdatedMixIn
from api.db.models.audit import EntityType
from api.db.secret_box import SecretBox
from api.db.utils import decrypt_secrets, encrypt_secrets
from api.storage.base_provider import StorageProvider, StorageType
from api.storage.registry import create_provider

class StorageBackend(AuditedMixIn, UpdatedMixIn, table=True):
    __tablename__: str= "storage_backends"
    __entity_type__ = EntityType.STORAGE_BACKEND
    __audit_exclude__ = frozenset({'secrets_enc'})
    __audit_secret_fields__ = frozenset({'secrets_enc'})

    name: str = Field(index=True, unique=True)
    type: StorageType = Field(index=True)
    config: dict = Field(sa_column=Column(JSON))
    secrets: dict | None = Field(sa_column=SecretBox(dict).column(nullable=True, default=None))
    created_by: int = Field(foreign_key="users.id", index=True)

    def provider(self) -> StorageProvider:
        return create_provider(self.type, self.config, self.secrets)

    # @property
    # def secrets(self) -> dict[str, Any]:
    #     return decrypt_secrets(self.secrets_enc)

    # @secrets.setter
    # def secrets(self, value: dict[str, Any]) -> None:
    #     if value == self.secrets:
    #         return
    #     self.secrets_enc = encrypt_secrets(value) if value else None
