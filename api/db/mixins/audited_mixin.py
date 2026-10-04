from typing import Any, ClassVar, Self, cast

from pydantic_core import to_jsonable_python
from sqlalchemy.orm import InstanceState
from sqlmodel import Session, inspect

from api.db.utils import decrypt_secrets

from .db_model_mixin import DBModelMixIn
from ..audit_types import ActorRef, EntityRef, EntityType, Operation


_ALWAYS_EXCLUDED = frozenset({'id', 'created_at', 'updated_at'})
REDACTED = '[redacted]'


class AuditedMixIn(DBModelMixIn):
    __entity_type__: ClassVar[EntityType]
    __audit_name_field__: ClassVar[str] = 'name'
    __audit_redacted__: ClassVar[frozenset[str]] = frozenset()
    __audit_excluded__: ClassVar[frozenset[str]] = frozenset()
    __audit_secret_fields__: ClassVar[frozenset[str]] = frozenset()

    def _audit_fields(self) -> dict[str, Any]:
        skip = (
            _ALWAYS_EXCLUDED
            | self.__audit_excluded__
            | self.__audit_redacted__
            | self.__audit_secret_fields__
        )
        data = self.model_dump(mode='json', exclude=set(skip))

        for key in self.__audit_redacted__:
            if getattr(self, key, None) is not None:
                data[key] = REDACTED

        for key in self.__audit_secret_fields__:
            names = decrypt_secrets(getattr(self, key))
            if names:
                data[key] = {name: REDACTED for name in names}
        return data

    def _audit_diff(self) -> dict[str, Any]:
        skip = _ALWAYS_EXCLUDED | self.__audit_excluded__ | self.__audit_secret_fields__
        state = cast(InstanceState[Any], inspect(self))
        diff: dict[str, Any] = {}

        for col in state.mapper.column_attrs:
            key = col.key
            if key in skip:
                continue
            history = state.attrs[key].history
            if not history.has_changes():
                continue
            if key in self.__audit_redacted__:
                diff[key] = {'changed': True}
            else:
                old = history.deleted[0] if history.deleted else None
                new = history.added[0] if history.added else None
                diff[key] = {
                    'from': to_jsonable_python(old, fallback=str),
                    'to': to_jsonable_python(new, fallback=str),
                }

        for key in self.__audit_secret_fields__:
            history = state.attrs[key].history
            if not history.has_changes():
                continue
            old = decrypt_secrets(history.deleted[0] if history.deleted else None)
            new = decrypt_secrets(history.added[0] if history.added else None)
            changed = sorted(k for k in old.keys() | new.keys() if old.get(k) != new.get(k))
            if changed:
                diff[key] = {'changed': changed}
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

    def delete(self, session: Session, ctx: ActorRef, *, commit: bool = False) -> None:
        self._audit(session, ctx, Operation.DELETE, self._audit_fields())
        session.delete(self)
        session.flush()
        if commit:
            session.commit()
