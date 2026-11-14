from collections.abc import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for ORM models (models arrive in phase 2)."""


def make_engine(url: str) -> Engine:
    # pool_pre_ping drops dead connections instead of failing the next request.
    return create_engine(url, pool_pre_ping=True)


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = make_engine(get_settings().database_url)
    return _engine


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a session bound to the configured engine."""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    with _session_factory() as session:
        yield session
