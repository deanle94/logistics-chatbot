"""Shared fixtures for the Slice 0 acceptance checks.

The CSV oracle is deliberately read *here*, with the standard library, so that every
expectation is derived independently of the code under test. If the seeder ever
mis-parses the dataset the tests disagree with the database rather than agreeing
with the bug.
"""

from __future__ import annotations

import csv
import os
import shutil
import subprocess
from collections import Counter
from collections.abc import Iterator
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = BACKEND_ROOT.parent
REPO_ROOT = SRC_ROOT.parent
FRONTEND_ROOT = SRC_ROOT / "frontend"
PACKAGE_ROOT = BACKEND_ROOT / "src" / "logistics_analytics"
CSV_PATH = REPO_ROOT / "infra" / "data" / "mock_logistics_data.csv"

#: The five architecture layers (docs/architecture.md section 3).
LAYERS: tuple[str, ...] = ("agent", "api", "tools", "calculator", "data")

#: Seconds to allow ``docker compose up --wait`` before giving up.
COMPOSE_TIMEOUT_SECONDS = 600


def _load_dotenv() -> None:
    """Apply ``<repo>/.env`` to this process, without overriding a real env var.

    docker compose reads that file automatically; pytest does not. Parsing it here
    keeps the tests pointed at the same ports and credentials the stack is actually
    published on - most often when a busy host port has been overridden locally.
    Deliberately hand-rolled rather than adding a dependency: it needs to handle
    ``KEY=value`` and comments, nothing more.
    """
    env_file = REPO_ROOT / ".env"
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()


def resolve_executable(name: str) -> str:
    """Absolute path to a CLI on PATH.

    Windows installs npm and npx as ``.cmd`` shims, which ``subprocess`` cannot launch
    by bare name. Resolving through ``shutil.which`` keeps the calls shell-free, so no
    argument is ever re-parsed by a shell.
    """
    resolved = shutil.which(name)
    if resolved is None:
        message = f"{name!r} is not on PATH; it is required to run this gate"
        raise RuntimeError(message)
    return resolved


@pytest.fixture(scope="session")
def csv_rows() -> list[dict[str, str]]:
    """Every row of the source dataset, read straight from disk.

    Session-scoped because 400 rows are re-used by several assertions and the file
    never changes during a run.
    """
    with CSV_PATH.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(scope="session")
def expected_row_count(csv_rows: list[dict[str, str]]) -> int:
    """Row count the database must match. Derived, never hardcoded."""
    return len(csv_rows)


@pytest.fixture(scope="session")
def expected_status_counts(csv_rows: list[dict[str, str]]) -> dict[str, int]:
    """Per-status row counts the database must match. Derived, never hardcoded."""
    return dict(Counter(row["status"] for row in csv_rows))


@pytest.fixture(scope="session")
def compose_stack() -> Iterator[None]:
    """Bring the full docker compose stack up once for every ``stack``-marked test.

    Uses ``--wait`` so the fixture only yields after every service reports healthy;
    without healthchecks this would race and produce flaky connection errors. The
    teardown removes volumes so a rerun always starts from an empty database, which
    is what makes the S0.3 "seed twice" assertion meaningful.
    """
    subprocess.run(
        ["docker", "compose", "up", "-d", "--build", "--wait"],
        cwd=REPO_ROOT,
        check=True,
        timeout=COMPOSE_TIMEOUT_SECONDS,
    )
    try:
        yield
    finally:
        subprocess.run(
            ["docker", "compose", "down", "-v"],
            cwd=REPO_ROOT,
            check=False,
            timeout=COMPOSE_TIMEOUT_SECONDS,
        )


@pytest.fixture(scope="session")
def backend_base_url() -> str:
    """Base URL of the backend as published by docker compose."""
    return os.environ.get("BACKEND_BASE_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def readonly_database_url() -> str:
    """Connection URL for the read-only application role, as published by compose.

    Built from the environment with the same defaults docker-compose.yml uses, so a
    local port override in .env (a busy 5432 is common) needs no test change.
    """
    user = os.environ.get("APP_RO_USER", "app_ro")
    password = os.environ.get("APP_RO_PASSWORD", "app_ro_local_dev")
    port = os.environ.get("POSTGRES_PORT", "5432")
    database = os.environ.get("POSTGRES_DB", "logistics")
    return f"postgresql+psycopg://{user}:{password}@localhost:{port}/{database}"


@pytest.fixture(scope="session")
def frontend_base_url() -> str:
    """Base URL of the nginx-served front-end as published by docker compose."""
    return os.environ.get("FRONTEND_BASE_URL", "http://localhost:5173")
