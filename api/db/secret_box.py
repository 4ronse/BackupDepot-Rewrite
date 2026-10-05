import base64
import os

from typing import TypeVar
from functools import lru_cache
from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import LargeBinary, TypeDecorator, Dialect, Column

from api.db.utils import same_signature

class SecretError(Exception): ...

def _fernet(secret: str) -> Fernet:
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b'backup-depot').derive(secret.encode())
    return Fernet(base64.urlsafe_b64encode(key))

@lru_cache
def _cipher() -> MultiFernet:
    """Also handles key rotation. DEPOT_SECRET_KEY encrypts and decrypts,
    while DEPOT_OLD_KEYS (semi-colon [;] seperated) decrypt only."""
    current = os.environ.get('DEPOT_SECRET_KEY', '')
    old = [k for k in os.environ.get('DEPOT_OLD_KEYS', '').split(';') if k]
    return MultiFernet([_fernet(k) for k in [current, *old]])


T = TypeVar('T')

class SecretBox(TypeDecorator[T]):
    impl = LargeBinary
    cache_ok = True

    def __init__(self, inner: type[T]):
        super().__init__()
        self.inner = inner
        self._adapter = TypeAdapter(inner)

    def process_bind_param(self, value: T | None, dialect: Dialect) -> bytes | None:
        if value is None:
            return None
        try:
            return _cipher().encrypt(self._adapter.dump_json(value))
        except ValidationError:
            raise SecretError('Failed to encrypt; check value!')

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        try:
            raw = _cipher().decrypt(value)
        except InvalidToken:
            raise SecretError('Cannot decrypt value: check DEPOT_SECRET_KEY / DEPOT_OLD_KEYS') from None
        return self._adapter.validate_json(raw)

    @same_signature(Column)
    def column(self, **kwargs) -> Column[T]:
        return Column(self, **kwargs)
