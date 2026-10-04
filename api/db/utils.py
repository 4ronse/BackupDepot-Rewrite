import json
import os
from cryptography.fernet import Fernet
from datetime import datetime, timezone
from typing import Any, Callable, ParamSpec, TypeVar

from fastapi import HTTPException
from sqlmodel import SQLModel, Session

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

T = TypeVar("T", bound=SQLModel)

def get_or_404(session: Session, model: type[T], id_: int, what: str | None = None) -> T:
    row = session.get(model, id_)
    if row is None:
        raise HTTPException(404, f"{what or model.__name__} not found")
    return row

P = ParamSpec("P")
R = TypeVar("R")

def same_signature(orig: Callable[P, R]) -> Callable[[Callable[..., Any]], Callable[P, R]]:
    def deco(f): return f
    return deco

# Crypto

_fernet = Fernet(os.environ['DEPOT_SECRET_KEY'])

def encrypt_secrets(secrets: dict) -> bytes | None:
    return _fernet.encrypt(json.dumps(secrets).encode()) if secrets else None

def decrypt_secrets(blob: bytes | None) -> dict[str, Any]:
    return json.loads(_fernet.decrypt(blob)) if blob else {}
