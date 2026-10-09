from fastapi import APIRouter
from sqlmodel import col

from api.models.endpoint import Endpoint
from api.models.upload_key import UploadKey
from web import services
from web.deps import SessionDep, UserDep
from web.responses import ResponseModel, ok
from web.schemas.endpoint_schemas import EndpointImpact, EndpointRead, EndpointCreate, EndpointUpdate
from web.schemas.upload_key_schemas import UploadKeyRead


router = APIRouter(prefix='/endpoints', tags=['endpoints'])


# /endpoints

@router.get('/', response_model=ResponseModel[list[EndpointRead]])
def get_endpoints(session: SessionDep):
    return ok(data=(EndpointRead.from_row(row) for row in Endpoint.all(session)))

@router.post('/', response_model=ResponseModel[EndpointRead])
def create_endpoint(body: EndpointCreate, session: SessionDep, user: UserDep):
    row = body.row(created_by=user.id)  # type: ignore
    row.insert(session, user.actor_ref, commit=True)
    return ok(data=EndpointRead.from_row(row))


# /endpoints/{id}

@router.get('/{id}', response_model=ResponseModel[EndpointRead])
def get_single_endpoint(id: int, session: SessionDep):
    return ok(data=EndpointRead.from_row(
        Endpoint.get_or_404(session, id)
    ))

@router.delete('/{id}', status_code=204)
def delete_single_endpoint(id: int, session: SessionDep, user: UserDep, confirm: str | None = None):
    row = Endpoint.get_or_404(session, id)
    services.ep.delete_endpoint(session, row, user.actor_ref, confirm)

@router.patch('/{id}', response_model=ResponseModel[EndpointRead])
def update_single_endpoint(id: int, body: EndpointUpdate, session: SessionDep, user: UserDep):
    row = Endpoint.get_or_404(session, id)
    body.apply(row)
    row.update(session, user.actor_ref, commit=True)
    return ok(data=EndpointRead.from_row(row))

@router.get('/{id}/impact', response_model=ResponseModel[EndpointImpact])
def get_endpoint_impact(id: int, session: SessionDep):
    return ok(data=services.ep.compute_impact(session, id))

@router.get('/{id}/keys', response_model=ResponseModel[list[UploadKeyRead]], tags=['keys'])
def get_endpoint_keys_related(id: int, session: SessionDep):
    Endpoint.get_or_404(session, id)
    return ok(data=[UploadKeyRead.from_row(k) for k in UploadKey.find(session, col(UploadKey.endpoint_id) == id)])
