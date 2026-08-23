"""Shared fixtures for the Slice 0 acceptance checks.

The CSV oracle is deliberately read *here*, with the standard library, so that every
expectation is derived independently of the code under test. If the seeder ever
mis-parses the dataset the tests disagree with the database rather than agreeing
with the bug.
"""

from __future__ import annotations

import csv
import datetime
import os
import shutil
import subprocess
from collections import Counter, defaultdict
from collections.abc import Iterator
from decimal import ROUND_HALF_UP, Decimal
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


# --------------------------------------------------------------------------------------
# Slice 1 oracle helpers.
#
# These re-derive every expected number from the CSV with the standard library, so a
# test can never agree with a bug in the calculator. Rounding uses Decimal with
# ROUND_HALF_UP because that is what PostgreSQL's ``round(numeric, n)`` does; Python's
# built-in ``round`` is banker's rounding and would disagree on exact .5 boundaries.
# --------------------------------------------------------------------------------------

#: The two statuses that state a delivery outcome (docs/business-definition.md).
DELIVERY_OUTCOMES: tuple[str, ...] = ("delivered", "delayed")

#: Metric name -> the number of decimals PostgreSQL rounds it to in the calculator.
ROUNDED_METRICS: dict[str, int] = {"delay_rate": 4, "on_time_rate": 1, "avg_delivery_time": 1}

#: Metrics that are sums over rows, so a grouped result must add back to the ungrouped
#: total. Rates and averages deliberately do not.
ADDITIVE_METRICS: tuple[str, ...] = (
    "order_count",
    "delivered_orders",
    "delayed_orders",
    "quantity",
)


def parse_csv_date(value: str) -> datetime.date | None:
    """Read an ISO date cell, or ``None`` for the 30 rows with no delivery date yet."""
    return datetime.date.fromisoformat(value) if value else None


def _round_half_up(value: Decimal, digits: int) -> float:
    """Round the way PostgreSQL rounds ``numeric``, not the way Python rounds ``float``."""
    return float(value.quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP))


def csv_group_key(row: dict[str, str], group_by: str) -> str | None:
    """Bucket key a row falls into, computed independently of any SQL.

    ``week`` is the Monday of the row's order date (decision D12) — this function is the
    independent half of the assertion that PostgreSQL's ``date_trunc('week', ...)``
    agrees with ``d - timedelta(days=d.weekday())``.
    """
    if group_by == "week":
        ordered = parse_csv_date(row["order_date"])
        if ordered is None:
            return None
        return (ordered - datetime.timedelta(days=ordered.weekday())).isoformat()
    if group_by == "month":
        ordered = parse_csv_date(row["order_date"])
        return None if ordered is None else f"{ordered.year:04d}-{ordered.month:02d}"
    return row[group_by] or None


def csv_metric_value(rows: list[dict[str, str]], metric: str) -> float | int | None:
    """Compute one metric over a set of CSV rows, straight from the business definitions.

    Returns ``None`` where the definition is undefined for the rows given (no finished
    order, or no row with both dates) — SQL returns NULL in exactly those cases.
    """
    delivered = sum(1 for row in rows if row["status"] == "delivered")
    delayed = sum(1 for row in rows if row["status"] == "delayed")
    finished = delivered + delayed
    if metric == "order_count":
        return len(rows)
    if metric == "delivered_orders":
        return delivered
    if metric == "delayed_orders":
        return delayed
    if metric == "quantity":
        return sum(int(row["quantity"]) for row in rows if row["quantity"])
    if metric == "delay_rate":
        if finished == 0:
            return None
        return _round_half_up(Decimal(delayed) / Decimal(finished), 4)
    if metric == "on_time_rate":
        if finished == 0:
            return None
        return _round_half_up(Decimal(100 * delivered) / Decimal(finished), 1)
    if metric == "avg_delivery_time":
        return _average_delivery_days(rows)
    message = f"unknown metric: {metric!r}"
    raise ValueError(message)


def _average_delivery_days(rows: list[dict[str, str]]) -> float | None:
    """Mean of ``delivery_date - order_date`` over the rows that have both dates."""
    spans = [
        (delivered - ordered).days
        for row in rows
        if (ordered := parse_csv_date(row["order_date"])) is not None
        and (delivered := parse_csv_date(row["delivery_date"])) is not None
    ]
    if not spans:
        return None
    return _round_half_up(Decimal(sum(spans)) / Decimal(len(spans)), 1)


def csv_grouped(
    rows: list[dict[str, str]], group_by: str
) -> dict[str | None, list[dict[str, str]]]:
    """Split the CSV rows into the buckets a ``GROUP BY`` would produce."""
    buckets: dict[str | None, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        buckets[csv_group_key(row, group_by)].append(row)
    return dict(buckets)


def csv_filtered(rows: list[dict[str, str]], **filters: str) -> list[dict[str, str]]:
    """Rows matching every given ``column=value`` pair, as the calculator's filters do."""
    return [row for row in rows if all(row[column] == value for column, value in filters.items())]


def csv_between(
    rows: list[dict[str, str]], date_from: datetime.date, date_to: datetime.date
) -> list[dict[str, str]]:
    """Rows whose ``order_date`` falls in an inclusive range, as the date filter does."""
    return [
        row
        for row in rows
        if (ordered := parse_csv_date(row["order_date"])) is not None
        and date_from <= ordered <= date_to
    ]
