import sqlite3

from sqlalchemy import text

from grocery_data.app.storage import create_database_engine, create_session_factory
from grocery_data.app.storage.database import enable_sqlite_transactions


def _setup(path):
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("CREATE TABLE t (v INTEGER)")


def _visible(path):
    with sqlite3.connect(path) as db:
        return db.execute("SELECT count(*) FROM t").fetchone()[0]


def test_savepoints_stay_inside_the_outer_transaction(tmp_path):
    path = tmp_path / "c.sqlite3"
    _setup(path)
    engine = enable_sqlite_transactions(create_database_engine("sqlite+pysqlite:///" + path.as_posix()))
    factory = create_session_factory(engine)
    with factory() as session:
        for value in range(3):
            with session.begin_nested():
                session.execute(text("INSERT INTO t VALUES (:v)"), {"v": value})
        # Nothing is durable until the outer commit: one fsync per store.
        assert _visible(path) == 0
        session.commit()
    assert _visible(path) == 3


def test_failed_savepoint_rolls_back_only_itself(tmp_path):
    path = tmp_path / "c.sqlite3"
    _setup(path)
    engine = enable_sqlite_transactions(create_database_engine("sqlite+pysqlite:///" + path.as_posix()))
    factory = create_session_factory(engine)
    with factory() as session:
        with session.begin_nested():
            session.execute(text("INSERT INTO t VALUES (1)"))
        try:
            with session.begin_nested():
                session.execute(text("INSERT INTO t VALUES (2)"))
                raise RuntimeError("boom")
        except RuntimeError:
            pass
        session.commit()
    assert _visible(path) == 1


def test_default_engine_commits_each_savepoint(tmp_path):
    """Documents the pysqlite behaviour the relay engine opts out of."""
    path = tmp_path / "c.sqlite3"
    _setup(path)
    factory = create_session_factory(create_database_engine("sqlite+pysqlite:///" + path.as_posix()))
    with factory() as session:
        with session.begin_nested():
            session.execute(text("INSERT INTO t VALUES (1)"))
        leaked = _visible(path)
        session.rollback()
    assert leaked == 1
