from pydantic import ValidationError

from api.storage.base_provider import StorageProvider, StorageType
from api.storage.exceptions import StorageError


_REGISTRY: dict[StorageType, type[StorageProvider]] = {}


def register[T: type[StorageProvider]](cls: T) -> T:
    _REGISTRY[cls.type] = cls
    return cls


def create_provider(t: StorageType, config: dict | None, secerts: dict | None) -> StorageProvider:
    cls = _REGISTRY.get(t)
    if cls is None:
        raise StorageError(f'unsupported storage type: {t}')
    try:
        cfg = cls.config_model.model_validate(config or {})
        sec = cls.secrets_model.model_validate(secerts or {})
    except ValidationError as e:
        fields = sorted({'.'.join(map(str, err['loc'])) for err in e.errors(include_input=False)})
        raise StorageError(f'invalid storage configuration: {", ".join(fields)}') from None
    return cls(cfg, sec)


def registered_providers() -> dict[StorageType, type[StorageProvider]]:
    return dict(_REGISTRY)
