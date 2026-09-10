from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session


def get_session(request: Request) -> Iterator[Session]:
    """Yield one read-only unit of work from the app-injected factory."""

    factory = request.app.state.session_factory
    session = factory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
