"""S0.1 — the service boots, reports database reachability, and is configured by env only.

The database probe is injected (coding rule 5), so these tests exercise the real routing
and response contract without needing PostgreSQL. The *live* health check against a real
database is asserted separately in ``test_stack.py``.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import Row, Select

from logistics_analytics.config import Settings
from logistics_analytics.main import create_app


def no_rows(statement: Select[Any]) -> tuple[Row[Any], ...]:
    """Query executor stub for the health tests, which never reach the database.

    Slice 1 made the executor a constructor argument of the application. Health does not
    use it, so the stub asserts only that something statement-shaped was handed over.
    """
    assert statement is not None
    return ()


def test_health_reports_ok_when_database_is_reachable() -> None:
    """The happy path: 200 plus an explicit statement about the database."""
    client = TestClient(create_app(database_probe=lambda: True, execute_query=no_rows))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "reachable"}


def test_health_reports_unavailable_when_database_is_unreachable() -> None:
    """A booted service with a dead database is not healthy - 503, not a cheerful 200."""
    client = TestClient(create_app(database_probe=lambda: False, execute_query=no_rows))

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "database": "unreachable"}


def test_settings_require_database_url_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Config comes from env vars only - no default connection string is baked in."""
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_settings_read_the_database_url_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The one required setting is picked up from the process environment."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pw@db:5432/logistics")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.database_url == "postgresql+psycopg://user:pw@db:5432/logistics"
