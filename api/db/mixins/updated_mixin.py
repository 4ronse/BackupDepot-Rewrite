from datetime import datetime

from sqlmodel import SQLModel

from api.db.utc_datetime import UTCDateTime
from api.db.utils import utcnow


class UpdatedMixIn(SQLModel):
    updated_at: datetime = UTCDateTime.Field(
        default_factory=utcnow,
        nullable=False,
        sa_column_kwargs={"onupdate": utcnow}
    )
