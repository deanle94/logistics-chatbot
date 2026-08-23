"""S0.1 / S0.3 / S0.4 / S0.5 — assertions against the real running stack.

Everything here is marked ``stack`` and shares one ``docker compose up`` (see the
``compose_stack`` fixture). Run with ``pytest -m stack``.

The expected numbers all come from the CSV fixtures in ``conftest.py``, never from the
seeder, so a seeder that drops or duplicates rows fails here instead of agreeing with
itself.
"""

from __future__ import annotations

import subprocess

import httpx
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError

from tests.conftest import FRONTEND_ROOT, REPO_ROOT, resolve_executable

pytestmark = pytest.mark.stack

REQUEST_TIMEOUT_SECONDS = 30
SEED_TIMEOUT_SECONDS = 300
PLAYWRIGHT_TIMEOUT_SECONDS = 600


@pytest.fixture(scope="module")
def _stack(compose_stack: None) -> None:
    """Alias so every test in this module implicitly requires the running stack."""
    return compose_stack


# ------------------------------------------------------------------------------------
# S0.1 - back-end boots and reports the database as reachable, for real this time.
# ------------------------------------------------------------------------------------


def test_backend_health_reports_database_reachable(_stack: None, backend_base_url: str) -> None:
    """The live service must reach the live database."""
    response = httpx.get(f"{backend_base_url}/health", timeout=REQUEST_TIMEOUT_SECONDS)

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "reachable"}


# ------------------------------------------------------------------------------------
# S0.3 - dataset loaded, correct, and read-only.
# ------------------------------------------------------------------------------------


def test_database_holds_every_csv_row(
    _stack: None, expected_row_count: int, readonly_database_url: str
) -> None:
    """Row count must equal the CSV row count, computed independently."""
    engine = create_engine(readonly_database_url)
    with engine.connect() as connection:
        count = connection.execute(text("SELECT count(*) FROM orders")).scalar_one()

    assert count == expected_row_count


def test_status_counts_match_the_csv(
    _stack: None, expected_status_counts: dict[str, int], readonly_database_url: str
) -> None:
    """Per-status breakdown must equal the CSV breakdown, computed independently."""
    engine = create_engine(readonly_database_url)
    with engine.connect() as connection:
        rows = connection.execute(text("SELECT status, count(*) FROM orders GROUP BY status")).all()

    actual = {str(status): int(count) for status, count in rows}
    assert actual == expected_status_counts


def test_application_role_cannot_write(_stack: None, readonly_database_url: str) -> None:
    """The API's role holds SELECT and nothing else - a write is refused by PostgreSQL.

    This is a privilege, not a convention: no application code path can opt out of it.
    """
    engine = create_engine(readonly_database_url)

    with pytest.raises(ProgrammingError) as excinfo, engine.connect() as connection:
        connection.execute(
            text("INSERT INTO orders (order_id, client_id, status) VALUES ('X', 'Y', 'z')")
        )

    assert "permission denied" in str(excinfo.value).lower()


def test_seeding_twice_leaves_the_row_count_unchanged(
    _stack: None, expected_row_count: int, readonly_database_url: str
) -> None:
    """Re-running the seeder is idempotent - it replaces the data, it does not append."""
    subprocess.run(
        ["docker", "compose", "run", "--rm", "seeder"],
        cwd=REPO_ROOT,
        check=True,
        timeout=SEED_TIMEOUT_SECONDS,
    )

    engine = create_engine(readonly_database_url)
    with engine.connect() as connection:
        count = connection.execute(text("SELECT count(*) FROM orders")).scalar_one()

    assert count == expected_row_count


# ------------------------------------------------------------------------------------
# S0.4 / S0.5 - the front-end is served and renders backend state in a real browser.
# ------------------------------------------------------------------------------------


def test_frontend_renders_backend_status_in_a_browser(_stack: None) -> None:
    """Playwright visits the nginx-served page and asserts it shows /health's answer.

    This single check replaces a bare HTTP 200 on the front-end port: it proves the
    page is served, renders, and reaches the backend and database through the proxy.
    """
    result = subprocess.run(
        [resolve_executable("npx"), "playwright", "test"],
        cwd=FRONTEND_ROOT,
        capture_output=True,
        text=True,
        timeout=PLAYWRIGHT_TIMEOUT_SECONDS,
        check=False,
    )

    assert result.returncode == 0, (
        f"playwright failed with exit code {result.returncode}\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
