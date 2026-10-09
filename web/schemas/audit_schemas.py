from typing import Any

from api.db.audit_types import ActorRef, EntityRef
from api.db.models.audit import Audit
from web.schemas.shared import ReadSchema


class AuditRead(ReadSchema[Audit]):
    actor: ActorRef
    entity: EntityRef
    details: dict[str, Any]

    @classmethod
    def from_row(cls, row: Audit) -> AuditRead:
        actor = ActorRef(
            row.actor,
            row.actor_id or -1,
            row.remote_addr or ''
        )

        entity = EntityRef(
            row.entity_type,
            row.entity_id or -1,
            row.entity_name or ''
        )

        return cls(
            id=row.id,  # type: ignore
            actor=actor,
            entity=entity,
            details=row.details or {},

            created_at=row.created_at
        )
