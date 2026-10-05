import os

from pathlib import Path
from contextlib import contextmanager
from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

DB_PATH = Path(os.environ.get("DEPOT_DB", "data/depot.db")).resolve()
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
    echo=True
)

@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_conn, _):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA journal_mode=WAL")
    cur.close()


def init_db() -> None:
    from . import models
    from .. import models
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session

@contextmanager
def session_scope():
    with Session(engine, expire_on_commit=False) as session:
        yield session
