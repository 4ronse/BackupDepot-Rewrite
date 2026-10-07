from abc import ABC, abstractmethod
from typing import Any, ClassVar, Generic, Self, TypeVar, Generic

from pydantic import BaseModel, ConfigDict, Field

from api.db.mixins.db_model_mixin import DBModelMixIn
from api.models.storage_backend import StorageBackend
from api.storage.base_provider import EmptyModel, StorageType

RowT = TypeVar('RowT', bound=DBModelMixIn)
ConfT = TypeVar('ConfT', bound=BaseModel)
SecT = TypeVar('SecT', bound=BaseModel)


class Strict(BaseModel):
    """Unknown fields are rejected instead of ignored."""
    model_config = ConfigDict(extra='forbid')


class CreateSchema(Strict, ABC, Generic[RowT]):
    @abstractmethod
    def row(self, *, created_by: int) -> RowT: ...


class ReadSchema(Strict, ABC, Generic[RowT]):
    @classmethod
    @abstractmethod
    def from_row(cls, row: RowT) -> Self: ...


def secret_keys(value: dict[str, Any] | None, prefix: str='') -> list[str]:
    if value is None:
        return []

    out: list[str] = []
    for k, v in value.items():
        path = f'{prefix}{k}'
        if isinstance(v, dict) and v is not None:
            out += secret_keys(v, f'{path}.')
        else:
            out += [path]
    return out


class BackendCreate(CreateSchema[StorageBackend], Generic[ConfT, SecT]):
    type: ClassVar[StorageType]
    name: str = Field(min_length=1, max_length=100)
    config: ConfT
    secrets: SecT

    def row(self, *, created_by: int) -> StorageBackend:
        return StorageBackend(
            name=self.name,
            type=self.type,
            config=self.config.model_dump(mode='json'),
            secrets=None if isinstance(self.secrets, EmptyModel) else self.secrets.model_dump(mode='json'),
            created_by=created_by
        )


