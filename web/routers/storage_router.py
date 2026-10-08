from fastapi import APIRouter, HTTPException

from api.models.storage_backend import StorageBackend
from api.storage import registry
from api.storage.base_provider import StorageType, StorageUsage
from web import services
from web.deps import UserDep, SessionDep
from web.responses import ResponseModel, ok
from web.schemas import StorageBackendCreate, StorageBackendRead, StorageBackendImpact
from web.schemas.storage import StorageBackendUpdate, StorageTypeInfo

router = APIRouter(prefix='/storage', tags=['storage'])

# /storage

@router.get('/', response_model=ResponseModel[list[StorageBackendRead]])
def get_backends(session: SessionDep):
    return ok(data=[StorageBackendRead.from_row(row) for row in StorageBackend.all(session)])

@router.post('/', response_model=ResponseModel[StorageBackendRead])
def create_backend(storage_create: StorageBackendCreate, session: SessionDep, user: UserDep):
    row = storage_create.row(created_by=user.id)  # type: ignore
    row.insert(session, user.actor_ref, commit=True)
    return ok(data=StorageBackendRead.from_row(row))


# /storage/types
@router.get('/types', response_model=ResponseModel[list[StorageType]])
def get_provider_types():
    return ok(data=set(registry.registered_providers().keys()))

@router.get('/schemas', response_model=ResponseModel[list[StorageTypeInfo]])
def get_all_provider_schemas():
    return ok(data=[
        StorageTypeInfo.from_provider(p) for _, p in registry.registered_providers().items()
    ])

@router.get('/schema', response_model=ResponseModel[StorageTypeInfo])
def get_provider_schema(storage_type: StorageType):
    p_type = next(filter(lambda i: i[0] == storage_type, registry.registered_providers().items()))[1]
    return ok(data=StorageTypeInfo.from_provider(p_type))


# /storage/{id}...

@router.get('/{id}', response_model=ResponseModel[StorageBackendRead])
def get_single_backend(id: int, session: SessionDep):
    return ok(data=StorageBackend.get_or_404(session, id))

@router.delete('/{id}', status_code=204)
def delete_single_backend(id: int, session: SessionDep, user: UserDep, confirm: str | None = None):
    row = StorageBackend.get_or_404(session, id)
    services.storage.delete_backend(session, row, user.actor_ref, confirm)

@router.patch('/{id}', response_model=ResponseModel[StorageBackendRead])
def update_single_backend(id: int, body: StorageBackendUpdate, session: SessionDep, user: UserDep):
    row = StorageBackend.get_or_404(session, id)
    changed = body.apply(row)
    moved = changed & registry.registered_providers()[row.type].location_fields

    if moved and services.storage.has_backups(session, row):
        session.rollback()
        raise HTTPException(409, f'Cannot change {sorted(moved)}: existing backups are stored at the current location.')

    row.update(session, user.actor_ref, commit=True)
    return ok(data=StorageBackendRead.from_row(row))

@router.get('/{id}/impact', response_model=ResponseModel[StorageBackendImpact])
def get_impact(id: int, session: SessionDep):
    StorageBackend.get_or_404(session, id)
    return ok(data=services.storage.compute_impact(session, id))

@router.get('/{id}/usage', response_model=ResponseModel[StorageUsage])
def get_usage(id: int, session: SessionDep):
    row = StorageBackend.get_or_404(session, id)
    return ok(data=row.provider().usage())

@router.post('/{id}/check', response_model=ResponseModel[None])
def check_backend(id: int, session: SessionDep):
    row = StorageBackend.get_or_404(session, id)
    row.provider().check()
    return ok()
