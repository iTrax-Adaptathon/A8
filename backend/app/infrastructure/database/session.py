import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./flowcare_2.db")


def is_sqlite_url(url: str) -> bool:
    return url.startswith("sqlite")


def build_engine(url: str):
    """Create an engine with SQLite-appropriate settings.

    - ``timeout`` makes a second writer wait for the file lock instead of failing
      immediately, so concurrent claims are serialised by SQLite itself.
    - ``PRAGMA foreign_keys=ON`` enforces FK constraints (off by default in SQLite).
    - ``PRAGMA journal_mode=WAL`` for file databases lets readers proceed while a
      writer holds the lock.
    """
    connect_args = {}
    if is_sqlite_url(url):
        connect_args = {"check_same_thread": False, "timeout": 30}
    eng = create_engine(url, connect_args=connect_args, echo=False)
    if is_sqlite_url(url):
        register_sqlite_pragmas(eng, wal=":memory:" not in url)
    return eng


def register_sqlite_pragmas(eng, wal: bool = True):
    @event.listens_for(eng, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        if wal:
            cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


engine = build_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Request-scoped session. Any exception rolls the transaction back so a failed
    operation never leaves partial writes behind."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
