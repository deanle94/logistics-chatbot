"""S1.1 — the five KPIs, computed by the calculator against the live database.

Every expected number is re-derived here from ``infra/data/mock_logistics_data.csv`` with
the standard library (the ``csv_*`` helpers in ``conftest.py``), never from the calculator
under test. If a formula and the dataset ever disagree, this fails rather than agreeing
with the bug.

Marked ``stack`` because it needs the seeded PostgreSQL: run with ``pytest -m stack``.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from logistics_analytics.calculator.kpis import compute_kpis
from logistics_analytics.data.engine import create_database_engine
from logistics_analytics.data.repository import QueryExecutor, SqlAlchemyQueryExecutor
from tests.conftest import csv_metric_value

pytestmark = pytest.mark.stack

CsvRows = list[dict[str, str]]


@pytest.fixture(scope="module")
def _stack(compose_stack: None) -> None:
    """Alias so every test in this module implicitly requires the running stack."""
    return compose_stack


@pytest.fixture(scope="module")
def execute(_stack: None, readonly_database_url: str) -> Iterator[QueryExecutor]:
    """A real executor against the read-only role the API itself connects as.

    Yields rather than returns so the engine's pool is disposed when the module ends
    instead of being left open for the rest of the session.
    """
    engine = create_database_engine(readonly_database_url)
    try:
        yield SqlAlchemyQueryExecutor(engine)
    finally:
        engine.dispose()


def test_total_orders_counts_every_row(execute: QueryExecutor, csv_rows: CsvRows) -> None:
    """Total orders is every row, delivered or not (docs/business-definition.md)."""
    kpi = compute_kpis(execute).total_orders

    assert kpi.value == csv_metric_value(csv_rows, "order_count")
    assert kpi.unit is None


def test_delivered_orders_counts_only_the_delivered_status(
    execute: QueryExecutor, csv_rows: CsvRows
) -> None:
    """Delivered is a status count, not "everything that is not delayed"."""
    kpi = compute_kpis(execute).delivered_orders

    assert kpi.value == csv_metric_value(csv_rows, "delivered_orders")
    assert kpi.unit is None


def test_delayed_orders_counts_only_the_delayed_status(
    execute: QueryExecutor, csv_rows: CsvRows
) -> None:
    """`exception` is not `delayed` - it says something went wrong, not that it was late."""
    kpi = compute_kpis(execute).delayed_orders

    assert kpi.value == csv_metric_value(csv_rows, "delayed_orders")
    assert kpi.unit is None


def test_on_time_rate_divides_by_the_finished_orders_only(
    execute: QueryExecutor, csv_rows: CsvRows
) -> None:
    """The denominator is delivered + delayed, not 400.

    The three excluded statuses state no delivery outcome, so including them would
    silently depress the rate. The tolerance is the +/-0.05 the criterion allows.
    """
    expected = csv_metric_value(csv_rows, "on_time_rate")
    assert expected is not None

    kpi = compute_kpis(execute).on_time_rate

    assert kpi.unit == "%"
    assert kpi.value == pytest.approx(expected, abs=0.05)


def test_average_delivery_time_covers_only_rows_with_both_dates(
    execute: QueryExecutor, csv_rows: CsvRows
) -> None:
    """The 30 rows with no delivery date are absent from the mean, not counted as zero.

    D13: the calculator returns the value already rounded, so the dashboard and the
    Slice 2 chat print the identical digits.
    """
    expected = csv_metric_value(csv_rows, "avg_delivery_time")
    assert expected is not None

    kpi = compute_kpis(execute).average_delivery_time

    assert kpi.unit == "days"
    assert kpi.value == pytest.approx(expected, abs=1e-9)


def test_every_kpi_carries_the_unit_the_dashboard_prints(execute: QueryExecutor) -> None:
    """D13: the unit travels with the number, so no caller has to remember it."""
    kpis = compute_kpis(execute)

    units = (
        kpis.total_orders.unit,
        kpis.delivered_orders.unit,
        kpis.delayed_orders.unit,
        kpis.on_time_rate.unit,
        kpis.average_delivery_time.unit,
    )

    assert units == (None, None, None, "%", "days")
