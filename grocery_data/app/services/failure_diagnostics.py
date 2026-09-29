"""Useful exception chains without SQL parameters, request bodies or credentials."""
import sqlite3
import traceback


def failure_details(exc):
    result = []
    seen = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        row = {"error_type": type(exc).__name__, "frames": [
            {"file": f.filename, "line": f.lineno, "function": f.name}
            for f in traceback.extract_tb(exc.__traceback__)]}
        # SQLAlchemy's string includes SQL and bound parameters. Its underlying
        # SQLite exception carries the actual engine reason without parameters.
        if isinstance(exc, sqlite3.Error):
            row.update(sqlite_errorcode=getattr(exc, "sqlite_errorcode", None),
                       sqlite_errorname=getattr(exc, "sqlite_errorname", None),
                       reason=str(exc))
        result.append(row)
        exc = getattr(exc, "orig", None) or exc.__cause__ or exc.__context__
    return result
