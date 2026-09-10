from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from grocery_data.app.storage.models import Base

SessionFactory = sessionmaker[Session]


def create_database_engine(
    database_url: str,
    *,
    echo: bool = False,
    **engine_options: Any,
) -> Engine:
    """Create a synchronous SQLAlchemy engine for PostgreSQL or SQLite.

    Configuration is explicit: this module intentionally does not read environment
    variables. In-memory SQLite uses one shared connection so independent sessions see
    the same test database.
    """

    url = make_url(database_url)
    if url.get_backend_name() not in {"postgresql", "sqlite"}:
        raise ValueError("database_url must use PostgreSQL or SQLite")

    options: dict[str, Any] = {"echo": echo}
    options.update(engine_options)

    if url.get_backend_name() == "sqlite":
        connect_args = dict(options.pop("connect_args", {}))
        connect_args.setdefault("check_same_thread", False)
        options["connect_args"] = connect_args
        if url.database in {None, "", ":memory:"}:
            options.setdefault("poolclass", StaticPool)

    engine = create_engine(url, **options)

    if url.get_backend_name() == "sqlite":

        @event.listens_for(engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection: Any, _: Any) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def create_session_factory(engine: Engine) -> SessionFactory:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def create_schema(engine: Engine) -> None:
    Base.metadata.create_all(engine)


def drop_schema(engine: Engine) -> None:
    Base.metadata.drop_all(engine)


@contextmanager
def session_scope(factory: SessionFactory) -> Iterator[Session]:
    """Commit one unit of work or roll it back as a whole."""

    session = factory()
    try:
        yield session
        session.commit()
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()
