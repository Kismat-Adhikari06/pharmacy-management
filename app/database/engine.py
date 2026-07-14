from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import config


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""

    pass


_engine = None
_SessionFactory = None


def get_engine():
    """Return the singleton SQLAlchemy engine, creating it on first call."""
    global _engine
    if _engine is None:
        url = f"sqlite:///{config.db_path}"
        _engine = create_engine(
            url,
            echo=False,
            connect_args={"check_same_thread": False},
        )
    return _engine


def get_session_factory():
    """Return the singleton session factory, creating it on first call."""
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(bind=get_engine())
    return _SessionFactory


def new_session():
    """Create and return a new database session."""
    return get_session_factory()()
