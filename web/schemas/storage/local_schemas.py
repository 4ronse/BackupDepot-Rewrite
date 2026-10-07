from typing import Literal

from api.storage.base_provider import EmptyModel, StorageType
from api.storage.providers.local_provider import LocalConfig
from web.schemas.shared import BackendCreate


class LocalBackendCreate(BackendCreate[LocalConfig, EmptyModel]):
    type: Literal[StorageType.LOCAL]
