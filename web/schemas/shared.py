from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, ClassVar, Generic, Self, TypeVar, Generic, final

from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

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
    id: int
    created_at: datetime

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

def merge(model: type[BaseModel], current: dict[str, Any] | None, patch: dict[str, Any], field: str) -> dict[str, Any]:
    try:
        return model.model_validate({**(current or {}), **patch}).model_dump(mode='json')
    except ValidationError as e:
        raise RequestValidationError([
            {**err, 'loc': ('body', field, *err['loc'])}
            for err in e.errors(include_url=False, include_context=False, include_input=False)
        ]) from None


class UpdateSchema(Strict, ABC, Generic[RowT]):
    nullable: ClassVar[frozenset[str]] = frozenset()  # i.e. clearable - like Endpoint.revoked_at

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        super().__pydantic_init_subclass__(**kwargs)
        fields = set(cls.model_fields)

        hooks = {
            name.removeprefix('merge_')
            for name in dir(cls)
            if name.startswith('merge_') and callable(getattr(cls, name))
        }

        if orphans := hooks - fields:
            raise TypeError(
                f'{cls.__name__}: merge_ hooks without a matching field: {sorted(orphans)} '
                f'(fields: {sorted(fields)})'
            )

        if unknown := cls.nullable - fields:
            raise TypeError(f'{cls.__name__}: nullable names unknown fields: {sorted(unknown)}')


    @model_validator(mode='after')
    def check_body(self) -> Self:
        if not self.model_fields_set:
            raise ValueError('Nothing to update')

        for name in self.model_fields_set - self.nullable:
            if getattr(self, name) is None:
                raise ValueError(f'{name}: cannot be null; omit the field to leave it unchanged')

        return self

    @staticmethod
    def diff(path: str, old: Any, new: Any) -> set[str]:
        if isinstance(old, dict) and isinstance(new, dict):
            out: set[str] = set()
            for k in old.keys() | new.keys():
                out |= UpdateSchema.diff(f'{path}.{k}', old.get(k), new.get(k))
            return out
        return set() if old == new else {path}

    @final
    def apply(self, row: RowT) -> set[str]:
        changed: set[str] = set()
        for name, value in self.model_dump(exclude_unset=True).items():
            if (hook := getattr(self, f'merge_{name}', None)) is not None:
                value = hook(row, value)
            old = getattr(row, name)
            if value != old:
                setattr(row, name, value)
                changed |= UpdateSchema.diff(name, old, value)
        return changed

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


