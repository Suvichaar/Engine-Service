"""Database utilities for SQLAlchemy engine and session management."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def create_session_factory(database_url: str, echo: bool = False) -> sessionmaker[Session]:
    """
    Create SQLAlchemy session factory with connection pool settings.
    
    Connection pool settings help prevent "server closed the connection unexpectedly" errors
    by:
    - Maintaining a pool of reusable connections
    - Validating connections before use (pool_pre_ping)
    - Recycling stale connections (pool_recycle)
    - Setting appropriate timeouts
    """
    engine = create_engine(
        database_url,
        echo=echo,
        future=True,
        # Connection pool settings
        pool_size=5,                    # Number of connections to maintain in pool
        max_overflow=10,                # Max additional connections beyond pool_size
        pool_pre_ping=True,             # Validate connections before use (prevents stale connection errors)
        pool_recycle=3600,              # Recycle connections after 1 hour (Azure PostgreSQL timeout)
        pool_timeout=30,                # Timeout when getting connection from pool
        # Connection arguments for PostgreSQL/Azure
        connect_args={
            "connect_timeout": 10,       # Connection timeout in seconds
            "sslmode": "require"         # Require SSL for Azure PostgreSQL
        } if "postgres" in database_url.lower() else {}
    )
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

