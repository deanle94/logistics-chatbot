"""S1.2 — the generic query engine, every metric x every group-by, against the CSV oracle.

The whole cross product is parametrized rather than sampled: the engine is what Slice 2's
chat will drive with model-chosen parameters, so a combination nobody tried in the
dashboard is exactly the one that will be tried first in chat.

Expected values come from ``csv_metric_value`` / ``csv_grouped`` in ``conftest.py``, which
re-read the dataset with the standard library. Nothing here asks the calculator what the
answer should be.

Marked ``stack``: run with ``pytest -m stack``.
"""

from __future__ import annotations

import datetime
from collections.abc import Iterator

import pytest

from logistics_analytics.calculator.models import Filters, GroupBy, Metric, Ordering, QuerySpec
from logistics_analytics.calculator.query import run_query
from logistics_analytics.data.engine import create_database_engine
from logistics_analytics.data.repository import QueryExecutor, SqlAlchemyQueryExecutor
from tests.conftest import (
    ADDITIVE_METRICS,
    csv_between,
    csv_filtered,
    csv_group_key,
    csv_grouped,
    csv_metric_value,
)

pytestmark = pytest.mark.stack

CsvRows = list[dict[str, str]]

#: Every group-by except NONE, i.e. the ones that actually produce buckets.
BUCKETED_GROUP_BYS: tuple[GroupBy, ...] = tuple(g for g in GroupBy if g is not GroupBy.NONE)

#: The two time buckets. Only these are asserted to arrive in ascending order: a chart's
#: x-axis has to be chronological, whereas the order of carrier names is a database
#: collation detail and not a business rule.
TIME_GROUP_BYS: tuple[GroupBy, ...] = (GroupBy.WEEK, GroupBy.MONTH)

#: One filter case per dimension, using values known to exist in the dataset. The column
#: and the Filters object are both spelled out so the CSV side and the SQL side are
#: written independently of each other.
#:
#: All six ``Filters`` dimensions are listed: this test is the only thing that would catch
#: a filter wired to the wrong column, so a dimension missing from here is a dimension
#: nothing checks.
DIMENSION_FILTER_CASES: tuple[tuple[str, str, Filters], ...] = (
    ("carrier", "DHL", Filters(carrier="DHL")),
    ("status", "delivered", Filters(status="delivered")),
    ("sku", "CRAYON-0008", Filters(sku="CRAYON-0008")),
    ("product_category", "PAPER", Filters(product_category="PAPER")),
    ("region", "EU", Filters(region="EU")),
    ("warehouse", "LON-FC1", Filters(warehouse="LON-FC1")),
)


@pytest.fixture(scope="module")
def _stack(compose_stack: None) -> None:
    """Alias so every test in this module implicitly requires the running stack."""
    return compose_stack


@pytest.fixture(scope="module")
def execute(_stack: None, readonly_database_url: str) -> Iterator[QueryExecutor]:
    """A real executor against the read-only role, disposed when the module ends."""
    engine = create_database_engine(readonly_database_url)
    try:
        yield SqlAlchemyQueryExecutor(engine)
    finally:
        engine.dispose()


def assert_same_number(actual: float | int | None, expected: float | int | None) -> None:
    """Compare a computed number with its oracle, treating SQL NULL and None alike.

    Both sides are already rounded to the same decimals by the metric definition, so this
    is equality with a floating-point epsilon rather than a tolerance wide enough to hide
    a genuinely different answer.
    """
    if expected is None or actual is None:
        assert actual is expected, f"expected {expected!r}, got {actual!r}"
        return
    assert actual == pytest.approx(expected, abs=1e-9)


# --------------------------------------------------------------------------------------
# S1.2 - the full cross product: 7 metrics x 9 group-bys.
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("group_by", tuple(GroupBy), ids=[g.value for g in GroupBy])
@pytest.mark.parametrize("metric", tuple(Metric), ids=[m.value for m in Metric])
def test_metric_by_group_matches_the_csv(
    execute: QueryExecutor, csv_rows: CsvRows, metric: Metric, group_by: GroupBy
) -> None:
    """Every metric, in every bucketing, equals the same number computed in Python."""
    result = run_query(execute, QuerySpec(metrics=(metric,), group_by=group_by))

    if group_by is GroupBy.NONE:
        assert len(result.rows) == 1, "an ungrouped aggregate is exactly one row"
        assert result.rows[0].group is None
        assert_same_number(result.rows[0].values[metric], csv_metric_value(csv_rows, metric.value))
        return

    expected = {
        key: csv_metric_value(bucket, metric.value)
        for key, bucket in csv_grouped(csv_rows, group_by.value).items()
    }
    actual = {row.group: row.values[metric] for row in result.rows}

    assert actual.keys() == expected.keys()
    for key, value in expected.items():
        assert_same_number(actual[key], value)


@pytest.mark.parametrize("group_by", TIME_GROUP_BYS, ids=[g.value for g in TIME_GROUP_BYS])
def test_time_buckets_arrive_in_chronological_order(
    execute: QueryExecutor, group_by: GroupBy
) -> None:
    """``Ordering.GROUP`` means a line chart's x-axis needs no sorting in the browser."""
    result = run_query(execute, QuerySpec(metrics=(Metric.ORDER_COUNT,), group_by=group_by))

    keys = [row.group for row in result.rows]

    assert keys, "the dataset has orders, so there must be time buckets"
    assert keys == sorted(keys, key=lambda key: key or "")


# --------------------------------------------------------------------------------------
# S1.2 - grouped results add back to the ungrouped total, for the metrics that can.
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("group_by", BUCKETED_GROUP_BYS, ids=[g.value for g in BUCKETED_GROUP_BYS])
@pytest.mark.parametrize("metric", ADDITIVE_METRICS)
def test_a_grouped_total_adds_back_to_the_ungrouped_total(
    execute: QueryExecutor, metric: str, group_by: GroupBy
) -> None:
    """A bucketing that loses or duplicates rows fails here even if each bucket looks sane."""
    target = Metric(metric)
    grouped = run_query(execute, QuerySpec(metrics=(target,), group_by=group_by))
    ungrouped = run_query(execute, QuerySpec(metrics=(target,)))

    total = sum(row.values[target] or 0 for row in grouped.rows)

    assert_same_number(total, ungrouped.rows[0].values[target])


def test_rates_and_averages_deliberately_do_not_add_back(
    execute: QueryExecutor, csv_rows: CsvRows
) -> None:
    """Stated rather than skipped: summing a ratio is meaningless, so it is not asserted.

    What keeps that honest is asserting both halves - these metrics are absent from
    ``ADDITIVE_METRICS``, *and* their monthly parts really do not sum to the whole. If one
    ever did, the sum-back test above would be silently under-covering it.
    """
    for metric in (Metric.DELAY_RATE, Metric.ON_TIME_RATE, Metric.AVG_DELIVERY_TIME):
        assert metric.value not in ADDITIVE_METRICS

        grouped = run_query(execute, QuerySpec(metrics=(metric,), group_by=GroupBy.MONTH))
        summed = sum(row.values[metric] or 0 for row in grouped.rows)
        whole = csv_metric_value(csv_rows, metric.value)

        assert whole is not None
        assert summed != pytest.approx(whole, abs=1e-6), f"{metric.value} unexpectedly summed"


def test_the_two_rates_are_one_ratio_read_from_both_ends(execute: QueryExecutor) -> None:
    """Over the whole dataset the on-time and delay rates add to exactly 100.0 (D19c).

    This is the reason both are rounded to one decimal. At two decimals the pair came to
    100.02, which is the kind of thing a reviewer checks with a calculator and does not
    forget. Asserted over the ungrouped dataset only: per group the two halves can each
    land on a .x5 boundary and round apart, so a universal claim here would be false.
    """
    spec = QuerySpec(metrics=(Metric.ON_TIME_RATE, Metric.DELAY_RATE))
    (row,) = run_query(execute, spec).rows

    on_time = row.values[Metric.ON_TIME_RATE]
    delayed = row.values[Metric.DELAY_RATE]

    assert on_time is not None
    assert delayed is not None
    assert on_time + delayed == pytest.approx(100.0, abs=1e-9)


# --------------------------------------------------------------------------------------
# D12 - the week bucket is the Monday of the order date.
# --------------------------------------------------------------------------------------


def test_week_buckets_are_the_monday_of_the_order_date(
    execute: QueryExecutor, csv_rows: CsvRows
) -> None:
    """Proves D12's assumption that Postgres ``date_trunc('week')`` is Monday-keyed.

    The spec recorded it as UNVERIFIED because Docker was not running when it was
    written. This is the verification: the Python side computes the Monday itself with
    ``d - timedelta(days=d.weekday())`` and the two must agree bucket for bucket.
    """
    result = run_query(execute, QuerySpec(metrics=(Metric.ORDER_COUNT,), group_by=GroupBy.WEEK))

    actual = {row.group for row in result.rows}
    expected = {csv_group_key(row, "week") for row in csv_rows}

    assert actual == expected
    for key in actual:
        assert key is not None
        assert datetime.date.fromisoformat(key).weekday() == 0, f"{key} is not a Monday"


# --------------------------------------------------------------------------------------
# S1.2 - filters.
# --------------------------------------------------------------------------------------


def test_a_date_range_filter_narrows_the_rows(execute: QueryExecutor, csv_rows: CsvRows) -> None:
    """The range is inclusive at both ends, matching how a manager reads "March"."""
    date_from = datetime.date(2025, 3, 1)
    date_to = datetime.date(2025, 3, 31)
    spec = QuerySpec(
        metrics=(Metric.ORDER_COUNT,),
        filters=Filters(date_from=date_from, date_to=date_to),
    )

    result = run_query(execute, spec)

    expected = csv_metric_value(csv_between(csv_rows, date_from, date_to), "order_count")
    assert_same_number(result.rows[0].values[Metric.ORDER_COUNT], expected)


@pytest.mark.parametrize(
    ("column", "value", "filters"),
    DIMENSION_FILTER_CASES,
    ids=[column for column, _, _ in DIMENSION_FILTER_CASES],
)
def test_a_dimension_filter_narrows_the_rows(
    execute: QueryExecutor, csv_rows: CsvRows, column: str, value: str, filters: Filters
) -> None:
    """One filter per dimension - a filter wired to the wrong column fails here."""
    result = run_query(execute, QuerySpec(metrics=(Metric.ORDER_COUNT,), filters=filters))

    expected = csv_metric_value(csv_filtered(csv_rows, **{column: value}), "order_count")

    # Non-vacuous by construction: a value that matched nothing, or that matched every row,
    # would make "SQL agrees with the CSV" true even for a filter wired to another column.
    assert isinstance(expected, int)
    assert 0 < expected < len(csv_rows), f"{column}={value!r} is not a discriminating filter"

    assert_same_number(result.rows[0].values[Metric.ORDER_COUNT], expected)


def test_a_filter_matching_nothing_returns_no_rows_rather_than_an_error(
    execute: QueryExecutor,
) -> None:
    """D15: an empty answer is an answer. The spec still comes back so it can be echoed."""
    spec = QuerySpec(
        metrics=(Metric.ORDER_COUNT,),
        group_by=GroupBy.CARRIER,
        filters=Filters(carrier="NO-SUCH-CARRIER"),
    )

    result = run_query(execute, spec)

    assert result.rows == ()
    assert result.spec is spec


def test_value_ordering_sorts_by_the_first_metric_descending(execute: QueryExecutor) -> None:
    """D14: the carrier chart's whole point is that the worst carrier is first."""
    spec = QuerySpec(
        metrics=(Metric.DELAY_RATE,),
        group_by=GroupBy.CARRIER,
        order=Ordering.VALUE_DESC,
    )

    result = run_query(execute, spec)

    rates = [row.values[Metric.DELAY_RATE] for row in result.rows]

    assert all(rate is not None for rate in rates)
    assert rates == sorted(rates, key=lambda rate: -(rate or 0))
