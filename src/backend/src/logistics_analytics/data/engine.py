"""Engine construction.

Kept separate from the models so that callers choose *which* database identity they
connect as. The API is wired with the read-only role and the seeder with the owning
role; sharing a module-level engine would make that distinction impossible to enforce.
"""

from __future__ import annotations

from sqlalchemy import Engine, create_engine


def create_database_engine(database_url: str) -> Engine:
    """Build an engine for the given URL.

    ``pool_pre_ping`` is on because in a compose stack PostgreSQL can restart underneath
    a long-lived pool; without it the first request after a restart fails with a stale
    connection rather than transparently reconnecting.
    """
    return create_engine(database_url, pool_pre_ping=True, future=True)
