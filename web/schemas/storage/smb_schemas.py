from typing import Literal

from api.storage.base_provider import StorageType
from api.storage.providers.smb_provider import SMBConfig, SMBSecrets
from web.schemas.shared import BackendCreate


class SMBBackendCreate(BackendCreate[SMBConfig, SMBSecrets]):
    type: Literal[StorageType.SAMBA]
