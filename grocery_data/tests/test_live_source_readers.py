import sqlite3
from contextlib import closing

import pytest

from grocery_data.app.storage.database import enable_live_sqlite_readers


@pytest.mark.parametrize('municipality', ['1281', '1280', '1480'])
def test_source_writer_keeps_committed_municipal_facts_readable(tmp_path, municipality):
    path = tmp_path / 'live.sqlite'
    with closing(sqlite3.connect(path)) as writer:
        writer.execute('CREATE TABLE facts (municipality TEXT, value TEXT)')
        writer.execute('INSERT INTO facts VALUES (?, ?)', (municipality, 'qualified'))
        writer.commit()
        assert writer.execute('PRAGMA journal_mode').fetchone()[0] == 'delete'
        enable_live_sqlite_readers(path)
        enable_live_sqlite_readers(path)  # Restarts preserve the same mode.
        writer.execute('BEGIN EXCLUSIVE')
        writer.execute('UPDATE facts SET value=?', ('uncommitted',))
        with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=0)) as reader:
            assert reader.execute('SELECT * FROM facts').fetchall() == [(municipality, 'qualified')]
        writer.rollback()
        assert writer.execute('SELECT * FROM facts').fetchall() == [(municipality, 'qualified')]
        assert writer.execute('PRAGMA synchronous').fetchone()[0] == 2


def test_reader_configuration_never_creates_missing_source(tmp_path):
    path = tmp_path / 'missing.sqlite'
    with pytest.raises(FileNotFoundError):
        enable_live_sqlite_readers(path)
    assert not path.exists()
