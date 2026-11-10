"""
app/db/session.py — engine και sessions (SQLAlchemy 2.x, sync).

PostgreSQL (psycopg) στην παραγωγή· SQLite στα tests. Για SQLite in-memory χρησιμοποιείται StaticPool, ώστε όλα
τα threads του TestClient να βλέπουν την ίδια βάση, και ενεργοποιούνται τα foreign keys.
"""
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        kwargs = {"connect_args": {"check_same_thread": False}}
        if url in ("sqlite://", "sqlite:///:memory:") or "mode=memory" in url:
            kwargs["poolclass"] = StaticPool
        engine = create_engine(url, **kwargs)

        @event.listens_for(engine, "connect")
        def _sqlite_fk(dbapi_conn, _record):
            dbapi_conn.execute("PRAGMA foreign_keys=ON")
        return engine
    return create_engine(url, pool_pre_ping=True)


def make_sessionmaker(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)
