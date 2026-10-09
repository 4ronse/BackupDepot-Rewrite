from datetime import datetime
from typing import Any

from fastapi.exceptions import RequestValidationError
from pydantic import Field

from api.models.storage_backend import StorageBackend
from api.storage import registry
from api.storage.base_provider import EmptyModel, StorageProvider, StorageType
from web.schemas.shared import ReadSchema, Strict, UpdateSchema, merge, secret_keys

from .local_schemas import LocalBackendCreate
from .smb_schemas import SMBBackendCreate


__all__ = [
    'LocalBackendCreate', 'SMBBackendCreate',
    'StorageBackendRead', 'EndpointRef', 'StorageBackendImpact'
]


class StorageTypeInfo(Strict):
    type: StorageType
    config_schema: dict[str, Any]
    secrets_schema: dict[str, Any] | None
    location_fields: list[str]

    @classmethod
    def from_provider(cls, provider: type[StorageProvider]):
        return cls(
            type=provider.type,
            config_schema=provider.config_model.model_json_schema(),
            secrets_schema=None if provider.secrets_model is EmptyModel else provider.secrets_model.model_json_schema(),
            location_fields=sorted(provider.location_fields)
        )


class StorageBackendRead(ReadSchema[StorageBackend]):
    id: int
    name: str
    type: StorageType
    config: Any
    secret_keys: list[str]
    created_by: int

    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, row: StorageBackend) -> 'StorageBackendRead':
        return cls(
            id=row.id,  # type: ignore
            name=row.name,
            type=row.type,
            config=row.config,
            secret_keys=secret_keys(row.secrets),
            created_by=row.created_by,
            created_at=row.created_at,
            updated_at=row.updated_at
        )


class EndpointRef(Strict):
    id: int
    name: str

class StorageBackendImpact(Strict):
    endpoints: list[EndpointRef]
    upload_keys: int
    backups: int
    backups_by_status: dict[str, int]
    total_bytes: int
    in_flight: bool  # Backups in progress - block deletion no matter what
    confirm_token: str | None


class StorageBackendUpdate(UpdateSchema[StorageBackend]):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    config: dict[str, Any] | None = None
    secrets: dict[str, Any] | None = None

    def merge_config(self, row: StorageBackend, patch: dict[str, Any]) -> dict[str, Any]:
        model = registry.registered_providers()[row.type].config_model
        return merge(model, row.config, patch, 'config')

    def merge_secrets(self, row: StorageBackend, patch: dict[str, Any]) -> dict[str, Any]:
        model = registry.registered_providers()[row.type].secrets_model
        if model is EmptyModel:
            raise RequestValidationError([{
                'loc': ('body', 'secrets'),
                'msg': f'{row.type.value} backends have no secrets',
                'type': 'value_error',
            }])
        return merge(model, row.secrets, patch, 'secrets')

