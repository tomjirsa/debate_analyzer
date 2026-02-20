"""Database engine and session configuration."""

import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Default: SQLite for local dev; use DATABASE_URL for Postgres (e.g. RDS).
# Set FORCE_SQLITE=1 to use SQLite even when DATABASE_URL is set (e.g. local dev with RDS in env).
_default_sqlite = "sqlite:///./debate_analyzer.db"
_raw = os.environ.get("DATABASE_URL", _default_sqlite)
if os.environ.get("FORCE_SQLITE", "").lower() in ("1", "true") or not (_raw and _raw.strip()):
    DATABASE_URL = _default_sqlite
else:
    DATABASE_URL = _raw.strip()


def get_engine():
    """Create SQLAlchemy engine from DATABASE_URL."""
    connect_args = {}
    if DATABASE_URL.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(
        DATABASE_URL,
        connect_args=connect_args,
        echo=os.environ.get("SQL_ECHO", "").lower() in ("1", "true"),
    )


def get_session_factory():
    """Return a session factory bound to the engine."""
    engine = get_engine()
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency that yields a DB session (for FastAPI)."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()


def init_db() -> None:
    """Create all tables. Call after app startup or in migrations."""
    from debate_analyzer.db.models import Base

    engine = get_engine()
    Base.metadata.create_all(bind=engine)
