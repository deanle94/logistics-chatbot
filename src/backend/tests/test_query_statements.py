"""S1.2 / S1.4 — the query builder emits the SQL the business definitions call for.

These compile a statement instead of running one, so the builder is provable without
PostgreSQL: a broken FILTER clause, a lost GROUP BY or a missing NULLS LAST fails here in
milliseconds rather than only in the stack gate. The numbers themselves are proved
separately against the live database in ``test_query_oracle.py``.
"""

from __future__ import annotations

import datetime

import pytest
from sqlalchemy.dialects import postgresql

from logistics_analytics.api.dashboard import (
    CARRIER_DELAY_RATE_SPEC,
    DELIVERY_PERFORMANCE_SPEC,
    ORDER_VOLUME_SPEC,
)
from logistics_analytics.calculator.kpis import KPI_SPEC
from logistics_analytics.calculator.models import Filters, GroupBy, Metric, Ordering, QuerySpec
from logistics_analytics.calculator.query import build_statement


def compiled_sql(spec: QuerySpec) -> str:
    """Render a spec as the PostgreSQL text it will send, with values inlined.

    ``literal_binds`` matters: without it every value is a placeholder and an assertion
    about *which* status is being filtered on would pass no matter what was bound.
    """
    statement = build_statement(spec)
    # SQLAlchemy ships the dialect classes without typed constructors, so mypy sees an
    # untyped call here. Verified by compiling: the returned object renders the SQL.
    dialect = postgresql.dialect()  # type: ignore[no-untyped-call]
    compiled = statement.compile(dialect=dialect, compile_kwargs={"literal_binds": True})
    return str(compiled)


@pytest.mark.parametrize("group_by", tuple(GroupBy), ids=[g.value for g in GroupBy])
@pytest.mark.parametrize("metric", tuple(Metric), ids=[m.value for m in Metric])
def test_every_statement_selects_from_the_orders_table(metric: Metric, group_by: GroupBy) -> None:
    """A statement with no FROM clause silently answers about no rows at all.

    ``count(*)`` names no column, so SQLAlchemy had nothing to infer a FROM from and the
    ungrouped ``order_count`` compiled to ``SELECT count(*)``: PostgreSQL evaluates that
    over one virtual row and returns 1 for a 400-row table. Every other metric happened to
    mention ``orders``, and every dashboard route happened to group or filter, so only the
    one bare combination was wrong. This asserts the FROM for the whole cross product
    without a database, so the class of bug cannot come back behind the stack gate.
    """
    sql = compiled_sql(QuerySpec(metrics=(metric,), group_by=group_by))

    assert "FROM orders" in sql


def test_order_volume_counts_rows_per_calendar_month() -> None:
    """Chart 1 is a plain count bucketed by month, ordered by the bucket."""
    sql = compiled_sql(ORDER_VOLUME_SPEC)

    assert "count(*) AS order_count" in sql
    assert "to_char(orders.order_date, 'YYYY-MM') AS \"group\"" in sql
    assert "GROUP BY to_char(orders.order_date, 'YYYY-MM')" in sql
    assert "ORDER BY to_char(orders.order_date, 'YYYY-MM')" in sql


def test_delivery_performance_splits_the_two_delivery_outcomes() -> None:
    """Chart 2 needs both series in one pass, which is what FILTER buys us."""
    sql = compiled_sql(DELIVERY_PERFORMANCE_SPEC)

    assert "count(*) FILTER (WHERE orders.status = 'delivered') AS delivered_orders" in sql
    assert "count(*) FILTER (WHERE orders.status = 'delayed') AS delayed_orders" in sql
    assert "GROUP BY to_char(orders.order_date, 'YYYY-MM')" in sql


def test_carrier_delay_rate_is_a_ratio_sorted_worst_first() -> None:
    """Chart 3 (D14): delayed over finished, per carrier, biggest first, NULLs last.

    ``nullif`` is what keeps a carrier with no finished order out of the top slot: it
    turns a zero denominator into NULL instead of a division error.
    """
    sql = compiled_sql(CARRIER_DELAY_RATE_SPEC)

    assert "nullif(count(*) FILTER (WHERE orders.status IN ('delivered', 'delayed')), 0)" in sql
    assert "round(" in sql
    assert "GROUP BY orders.carrier" in sql
    assert "DESC NULLS LAST" in sql


def test_kpi_spec_is_a_single_ungrouped_row() -> None:
    """S1.1: the five KPIs come from one aggregate over the whole table, not five queries."""
    sql = compiled_sql(KPI_SPEC)

    assert "GROUP BY" not in sql
    assert "avg(orders.delivery_date - orders.order_date)" in sql
    assert "count(*) AS order_count" in sql


def test_week_buckets_are_cast_back_to_a_date() -> None:
    """D12: ``date_trunc`` returns a timestamp, so the key would serialise as midnight.

    Without the CAST the bucket key reaches the browser as ``2025-01-06T00:00:00``.
    """
    sql = compiled_sql(QuerySpec(metrics=(Metric.ORDER_COUNT,), group_by=GroupBy.WEEK))

    assert "CAST(date_trunc('week', orders.order_date) AS DATE)" in sql


def test_filters_become_where_clauses_not_string_interpolation() -> None:
    """Every filter narrows the rows through the query builder, never through SQL text."""
    spec = QuerySpec(
        metrics=(Metric.ORDER_COUNT,),
        group_by=GroupBy.CARRIER,
        filters=Filters(
            date_from=datetime.date(2025, 3, 1),
            date_to=datetime.date(2025, 3, 31),
            region="EU",
        ),
    )

    sql = compiled_sql(spec)

    assert "orders.order_date >= '2025-03-01'" in sql
    assert "orders.order_date <= '2025-03-31'" in sql
    assert "orders.region = 'EU'" in sql


def test_a_spec_with_no_metric_is_rejected() -> None:
    """An empty metric tuple would build a SELECT with nothing to aggregate."""
    with pytest.raises(ValueError, match="at least one metric"):
        build_statement(QuerySpec(metrics=(), group_by=GroupBy.MONTH, order=Ordering.VALUE_DESC))
