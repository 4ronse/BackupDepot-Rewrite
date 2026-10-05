from datetime import datetime
from typing import Any, Self, Sequence

from sqlalchemy import ColumnElement
from sqlmodel import Field, SQLModel, Session, col, select
from api.db.utils import utcnow

from api.db.utc_datetime import UTCDateTime


class DBModelMixIn(SQLModel):
    id: int | None = Field(default=None, primary_key=True)

    created_at: datetime = UTCDateTime.Field(default_factory=utcnow, nullable=False)

    def insert(self, session: Session, *, commit: bool = False) -> Self:
        session.add(self)
        session.flush()
        if commit:
            session.commit()
        return self

    update = insert

    @classmethod
    def get(cls, session: Session, id: int) -> Self | None:
        return session.get(cls, id)

    @classmethod
    def all(cls, session: Session) -> list[Self]:
        return list(session.exec(select(cls)))

    @classmethod
    def find(
        cls,
        session: Session,
        *clauses: ColumnElement[bool] | bool,
        order_by: ColumnElement[Any] | Sequence[ColumnElement[Any]] | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[Self]:
        stmt = select(cls).where(*clauses)

        if order_by is not None:
            cols: Sequence[ColumnElement[Any]] = order_by if isinstance(order_by, Sequence) else [order_by]
            stmt = stmt.order_by(*cols)

        if limit is not None:
            stmt = stmt.limit(limit)
        if offset is not None:
            stmt = stmt.offset(offset)

        return list(session.exec(stmt))

    @classmethod
    def find_one(cls, session: Session, *clauses: ColumnElement[bool] | bool) -> Self | None:
        return session.exec(select(cls).where(*clauses)).first()

    @classmethod
    def last(cls, session: Session) -> Self | None:
        return session.exec(select(cls).order_by(col(cls.id).desc())).first()
