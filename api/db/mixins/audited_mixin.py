from functools import cache
from typing import Any, ClassVar, Self, cast

from pydantic_core import to_jsonable_python
from sqlalchemy.orm import InstanceState, Mapper
from sqlmodel import Session, inspect

from api.db.secret_box import SecretBox
from api.db.utils import decrypt_secrets

from .db_model_mixin import DBModelMixIn
from ..audit_types import ActorRef, EntityRef, EntityType, Operation

_ALWAYS_EXCLUDED = frozenset({'id', 'created_at', 'updated_at'})
REDACTED = '[redacted]'

@cache
def _secret_keys_for(model: type) -> frozenset[str]:
    mapper = cast(Mapper[Any], inspect(model))
    return frozenset(
        attr.key
        for attr in mapper.column_attrs
        if isinstance(attr.columns[0].type, SecretBox)
    )

def _plain(value: Any) -> Any:
    return to_jsonable_python(value, fallback=str)

def _redact(value: Any) -> Any:
    value = _plain(value)
    if isinstance(value, dict):
        return {k: _redact(v) for k, v in value.items()}  # Replace every leaf with REDACTED while keeping branch names plain
    return REDACTED

def _redact_diff(old: Any, new: Any) -> Any:
    o, n = _plain(old), _plain(new)
    if o is None:
        return _redact(n)
    if n is None:
        return _redact(o)
    if not (isinstance(o, dict) and isinstance(o, dict)):
        return REDACTED

    # dict handle
    out: dict[str, Any] = {}
    for key in sorted(o.keys() | n.keys(), key=str):
        if key in o and key in n:
            if o[key] != n[key]:
                out[key] = _redact_diff(o[key], n[key])
        else:
            out[key] = _redact(o[key] if key in o else n[key])
    return out

class AuditedMixIn(DBModelMixIn):
    __entity_type__: ClassVar[EntityType]
    __audit_name_field__: ClassVar[str] = 'name'
    __audit_redacted__: ClassVar[frozenset[str]] = frozenset()
    __audit_excluded__: ClassVar[frozenset[str]] = frozenset()

    @classmethod
    def _secret_keys(cls) -> frozenset[str]:
        return _secret_keys_for(cast(type[Any], cls))  # bruh

    @classmethod
    def _excluded_keys(cls) -> frozenset[str]:
        return _ALWAYS_EXCLUDED | cls.__audit_excluded__

    def _audit_fields(self) -> dict[str, Any]:
        secrets = self._secret_keys()
        excluded = self._excluded_keys()
        redacted = self.__audit_redacted__ - secrets

        data = self.model_dump(mode='json', exclude=set(excluded | secrets | redacted))

        for key in secrets - excluded:
            value = getattr(self, key, None)
            if value is not None:
                data[key] = _redact(value)

        for key in redacted - excluded:
            value = getattr(self, key, None)
            if value is not None:
                data[key] = REDACTED

        return data

    def _audit_diff(self) -> dict[str, Any]:
        secrets = self._secret_keys()
        excluded = self._excluded_keys()
        state = cast(InstanceState[Any], inspect(self))
        diff: dict[str, Any] = {}

        for col in state.mapper.column_attrs:
            key = col.key
            if key in excluded:
                continue
            history = state.attrs[key].history
            if not history.has_changes():
                continue

            old = history.deleted[0] if history.deleted else None
            new = history.added[0] if history.added else None

            if key in secrets:
                if old != new:
                    diff[key] = _redact_diff(old, new)
            elif key in self.__audit_redacted__:
                diff[key] = {'chaged': True}
            else:
                diff[key] = {
                    'from': _plain(old),
                    'to': _plain(new)
                }

        return diff

    def _audit(self, session: Session, ctx: ActorRef, op: Operation, details: dict[str, Any] | None = None) -> None:
        from api.db.models import Audit
        Audit.record(
            session,
            actor_ref=ctx,
            entity_ref=EntityRef(
                entity_type=self.__entity_type__,
                entity_id=self.id,
                entity_name=getattr(self, self.__audit_name_field__, None),
            ),
            operation=op,
            details=details,
        )

    def insert(self, session: Session, ctx: ActorRef, *, commit: bool = False) -> Self:
        session.add(self)
        session.flush()
        self._audit(session, ctx, Operation.CREATE, self._audit_fields())
        if commit:
            session.commit()
        return self

    def update(self, session: Session, ctx: ActorRef, *, extra: dict[str, Any] | None = None, commit: bool = False) -> Self:
        diff = self._audit_diff()
        if extra:
            diff.update(extra)
        if diff:
            session.add(self)
            session.flush()
            self._audit(session, ctx, Operation.UPDATE, diff)
        if commit:
            session.commit()
        return self

    def delete(self, session: Session, ctx: ActorRef, *, extra: dict | None = None, commit: bool = False) -> None:
        details = self._audit_fields()
        if extra:
            details.update(extra)

        self._audit(session, ctx, Operation.DELETE, self._audit_fields())
        session.delete(self)
        session.flush()
        if commit:
            session.commit()
