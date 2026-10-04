from dataclasses import dataclass
from enum import Enum

class Operation(str, Enum):
    CREATE = 'CREATE'
    UPDATE = 'UPDATE'
    DELETE = 'DELETE'
    DOWNLOAD = 'DOWNLOAD'
    REVOKE = 'REVOKE'
    REJECT = 'REJECT'
    RETENTION = 'RETENTION'
    LOGIN = 'LOGIN'
    LOGIN_FAILED = 'LOGIN_FAILED'

class Actor(str, Enum):
    USER = 'USER'
    SYSTEM = 'SYSTEM'
    UPLOAD_KEY = 'UPLOAD_KEY'
    UNKNOWN = 'UNKNOWN'

class EntityType(str, Enum):
    STORAGE_BACKEND = 'STORAGE_BACKEND'
    ENDPOINT = 'ENDPOINT'
    UPLOAD_KEY = 'UPLOAD_KEY'
    BACKUP = 'BACKUP'
    USER = 'USER'

@dataclass(frozen=True)
class ActorRef:
    actor: Actor
    actor_id: int | None = None
    remote_addr: str | None = None

@dataclass(frozen=True)
class EntityRef:
    entity_type: EntityType
    entity_id: int | None = None
    entity_name: str | None = None
