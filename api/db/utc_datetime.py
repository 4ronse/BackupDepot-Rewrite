from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Dialect
from sqlmodel import DateTime, Field, TypeDecorator

from api.db.utils import same_signature


class UTCDateTime(TypeDecorator):
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, _: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError('UTCDateTime requires a timezone-aware datetime')

        return value.astimezone(timezone.utc)

    def process_result_value(self, value: datetime | None, _: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)  # stored as UTC, so just label it
        return value.astimezone(timezone.utc)

    @staticmethod
    @same_signature(Field)
    def Field(*args, **kw) -> Any:
        return Field(*args, **{"sa_type": UTCDateTime, **kw})
