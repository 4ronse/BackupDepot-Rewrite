from typing import Annotated

from fastapi import Depends
from sqlmodel import Session

from api.db import get_session
from api.models.users import User

SessionDep = Annotated[Session, Depends(get_session)]


def get_user(session: Session = Depends(get_session)) -> User:
    u = User.last(session)
    if u is None:
        raise RuntimeError('Somehow, there are no users')
    return u
UserDep = Annotated[User, Depends(get_user)]

