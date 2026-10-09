from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from api.db.utils import utcnow
from api.models.endpoint import Endpoint
from api.models.upload_key import UploadKey
from web.deps import ActorDep, SessionDep, UserDep
from web.responses import ResponseModel as RM, ok
from web.schemas.upload_key_schemas import UploadKeyCreate, UploadKeyRead

router = APIRouter(prefix='/keys', tags=['keys'])
MAX_REVOKE_DELAY = timedelta(days=365)


@router.get('/', response_model=RM[list[UploadKeyRead]])
def get_keys(session: SessionDep):
    return ok(data=[UploadKeyRead.from_row(r) for r in UploadKey.all(session)])

@router.post('/', status_code=201, response_model=RM[UploadKeyRead])
def create_key(body: UploadKeyCreate, session: SessionDep, user: UserDep, actor: ActorDep):
    Endpoint.get_or_404(session, body.endpoint_id)  # the schema can't check that the endpoint exists
    key, plain = body.create(created_by=user.id)    # type: ignore
    key.insert(session, actor, commit=True)
    return ok(data=UploadKeyRead.from_row(key, plain=plain), headers={'Cache-Control': 'no-store'})

@router.get('/{id}', response_model=RM[UploadKeyRead])
def get_single_key(id: int, session: SessionDep):
    return ok(data=UploadKey.get_or_404(session, id))

@router.post('/{id}/revoke', response_model=RM[UploadKeyRead])
def revoke_key(
    id: int,
    session: SessionDep,
    user: UserDep,
    delay: Annotated[
        timedelta,
        Query(alias='in', description='Revoke after this long, ISO 8601 (PT1H, P7D). Omit to revoke now.'),
    ] = timedelta(0),
):
    if not timedelta(0) <= delay <= MAX_REVOKE_DELAY:
        raise HTTPException(422, f'`in` must be between 0 and {MAX_REVOKE_DELAY.days} days')

    row = UploadKey.get_or_404(session, id)
    target = utcnow() + delay

    # Revoking only ever moves the expiry earlier. Extending a key is a PATCH, not a "revoke".
    if row.revoked_at is None or target < row.revoked_at:
        row.revoked_at = target
        row.update(session, user.actor_ref, commit=True)

    return ok(data=UploadKeyRead.from_row(row))
