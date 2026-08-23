"""Statement execution. This module defines nothing and computes nothing.

It is the other half of decision D18: the calculator owns the SQL *expression*, this layer
owns the *connection*. Everything here is plumbing — open a session, run what you were
handed, give back the rows.

Mirrors the ``DatabaseProbe`` seam in ``health.py``: a Protocol the upper layers depend on,
and one implementation that upper layers never name. That is what lets ``api/`` and
``calculator/`` stay free of any database import while still getting real data, and what
lets every route be tested with a stub.
"""

from __future__ import annotations

from typing import Any, Protocol

from sqlalchemy import Engine, Row, Select
from sqlalchemy.orm import Session


class QueryExecutor(Protocol):
    """Runs a prepared statement and returns its rows."""

    def __call__(self, statement: Select[Any]) -> tuple[Row[Any], ...]:
        """Execute the statement and return every row it produced."""
        ...


class SqlAlchemyQueryExecutor:
    """Executor backed by a real engine, one short-lived session per call.

    A session per call rather than a long-lived one: the dashboard's queries are
    independent reads, and holding a session open between them would keep a transaction
    (and its snapshot) alive across requests for no benefit.

    Rows are materialised into a tuple before the session closes. Returning the lazy result
    would hand the caller a cursor over a connection that is already back in the pool.
    """

    def __init__(self, engine: Engine) -> None:
        """Store the engine to run against. The engine is supplied, never constructed here."""
        self._engine = engine

    def __call__(self, statement: Select[Any]) -> tuple[Row[Any], ...]:
        """Run the statement in its own session (coding rule 6) and return the rows."""
        with Session(self._engine) as session:
            return tuple(session.execute(statement).all())
