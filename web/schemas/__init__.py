# from .storage_schemas import *
from typing import Annotated

from pydantic import Field

from .storage import *
from .upload_key_schemas import *

StorageBackendCreate = Annotated[
    LocalBackendCreate | SMBBackendCreate,
    Field(discriminator='type')
]
