from typing import Annotated

from fastapi import Depends, HTTPException, Header, Request
from sqlmodel import Session

from api.db import get_session
from api.db.audit_types import ActorRef
from api.db.mixins.audited_mixin import ActorMixIn
from api.models.upload_key import UploadKey
from api.models.users import User

SessionDep = Annotated[Session, Depends(get_session)]


def get_user(session: Session = Depends(get_session)) -> User:
    u = User.last(session)
    if u is None:
        raise RuntimeError('Somehow, there are no users')
    return u
UserDep = Annotated[User, Depends(get_user)]

def get_upload_key(session: SessionDep, authorization: Annotated[str | None, Header()] = None) -> UploadKey:
    scheme, _, token = (authorization or '').partition(' ')
    key = UploadKey.find_key(session, token.strip()) if scheme.lower() == 'bearer' and token else None
    if key is None or key.is_revoked():
        raise HTTPException(401, 'invalid or expired upload key', headers={'WWW-Authenticate': 'Bearer'})
    return key
UploadKeyDep = Annotated[UploadKey, Depends(get_upload_key)]

def get_client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None

def get_actor(
    request: Request,
    session: SessionDep,
    authorization: Annotated[str | None, Header()] = None,
) -> ActorRef:
    """An upload key if the request carries credentials, otherwise the (test) user."""
    owner: ActorMixIn = get_upload_key(session, authorization) if authorization else get_user(session)
    return owner.actor_ref_for(get_client_ip(request))
ActorDep = Annotated[ActorRef, Depends(get_actor)]
