from fastapi import APIRouter

from api.models.endpoint import Endpoint
from web.deps import SessionDep, UserDep
from web.responses import ResponseModel, ok
from web.schemas.endpoint_schemas import EndpointRead, EndpointCreate


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
