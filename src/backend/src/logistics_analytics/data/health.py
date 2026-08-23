"""Database connectivity probe.

``DatabaseProbe`` is the seam that lets the API layer answer "is the database up?"
without importing SQLAlchemy (coding rule 5, and the "only data/ touches the database"
boundary). The API depends on the protocol; this module supplies the implementation.
"""

from __future__ import annotations

import logging
from typing import Protocol

from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


class DatabaseProbe(Protocol):
    """Answers whether the database is currently reachable."""

    def __call__(self) -> bool:
        """Return ``True`` when a trivial query succeeds."""
        ...


class SqlAlchemyDatabaseProbe:
    """Probe that opens a connection and runs ``SELECT 1``.

    Connectivity failures are reported as ``False`` rather than raised: an unreachable
    database is a health *result*, not an error in the health check itself. Anything
    that is not a SQLAlchemy error still propagates, so genuine bugs stay loud.
    """

    def __init__(self, engine: Engine) -> None:
        """Store the engine to probe. The engine is supplied, never constructed here."""
        self._engine = engine

    def __call__(self) -> bool:
        """Return ``True`` when the database answers, ``False`` when it does not."""
        try:
            with self._engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except SQLAlchemyError:
            logger.warning("database health probe failed", exc_info=True)
            return False
        return True
