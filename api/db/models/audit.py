from typing import Any
from sqlmodel import JSON, Column, Field, Index, Session

from api.db.mixins import DBModelMixIn
from api.db.audit_types import *


class Audit(DBModelMixIn, table=True):
    __tablename__: str = 'audits'

    __table_args__ = (
        Index('ix_audits_created_at', 'created_at'),
        Index('ix_audits_entity', 'entity_type', 'entity_id'),
        Index('ix_audits_actor', 'actor', 'actor_id'),
    )

    actor: Actor = Field(nullable=False)
    actor_id: int | None = Field(default=None, nullable=True)
    operation: Operation = Field(nullable=False)
    entity_type: EntityType = Field(nullable=False)
    entity_id: int | None = Field(default=None, nullable=True)
    entity_name: str | None = Field(default=None, nullable=True)
    rendered_message: str | None = Field(default=None, nullable=True)
    details: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    remote_addr: str | None = Field(default=None, nullable=True)

    @classmethod
    def record(cls, session: Session, /, *, actor_ref: ActorRef, entity_ref: EntityRef, operation: Operation, details: dict | None = None) -> 'Audit':
        audit = cls(
            actor=actor_ref.actor,
            actor_id=actor_ref.actor_id,
            remote_addr=actor_ref.remote_addr,
            entity_type=entity_ref.entity_type,
            entity_id=entity_ref.entity_id,
            entity_name=entity_ref.entity_name,
            operation=operation,
            details={} if details is None else details
        )
        session.add(audit)
        session.flush()

        return audit
