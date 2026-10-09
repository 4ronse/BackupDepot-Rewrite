from typing import Literal
from fastapi import APIRouter, Query

from sqlmodel import col, select
from api.db.audit_types import EntityType, Operation
from api.db.models.audit import Audit
from web.deps import SessionDep, UserDep
from web.responses import ResponseModel, ok
from web.schemas.audit_schemas import AuditRead


AuditSort = Literal['id', 'created_at', 'actor_id', 'operation', 'entity_type', 'entity_id']
router = APIRouter(prefix='/audits')


_SORT_COLUMNS = {
    'id': col(Audit.id),
    'created_at': col(Audit.created_at),
    'actor_id': col(Audit.actor_id),
    'operation': col(Audit.operation),
    'entity_type': col(Audit.entity_type),
    'entity_id': col(Audit.entity_id),
}


@router.get('/', response_model=ResponseModel[list[AuditRead]])
def read_audits(
    session: SessionDep,
    order_by: AuditSort = 'created_at',
    direction: Literal['asc', 'desc'] = 'asc',
    entity_type: EntityType | None = None,
    entity_id: int | None = None,
    actor_id: int | None = None,
    operation: Operation | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    stmt = select(Audit)
    if entity_type is not None:
        stmt = stmt.where(col(Audit.entity_type) == entity_type)
    if entity_id is not None:
        stmt = stmt.where(col(Audit.entity_id) == entity_id)
    if actor_id is not None:
        stmt = stmt.where(col(Audit.actor_id) == actor_id)
    if operation is not None:
        stmt = stmt.where(col(Audit.operation) == operation)

    column = _SORT_COLUMNS[order_by]
    id_col = col(Audit.id)
    if direction == 'asc':
        stmt = stmt.order_by(column.asc(), id_col.asc())
    else:
        stmt = stmt.order_by(column.desc(), id_col.desc())  # id tiebreaker keeps pages stable

    rows = session.exec(stmt.offset(offset).limit(limit)).all()
    return ok(data=[AuditRead.from_row(r) for r in rows])
