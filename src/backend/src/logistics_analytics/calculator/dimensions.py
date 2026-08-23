"""THE BUCKETS. How rows are split, and which rows a query considers.

The second of the two files allowed to hold a business definition (architecture
Decision 1). A time bucket is a definition as much as a metric is: "per week" means
something specific, and the moment two layers each decide what it means, the dashboard and
the chat start drawing different charts from the same dataset.

**D12 — the week bucket.** ISO week, Monday start, keyed by that Monday's date. The
``CAST(... AS DATE)`` is load-bearing: ``date_trunc`` returns a timestamp, so without it
the bucket key serialises to the browser as ``2025-01-06T00:00:00`` instead of
``2025-01-06`` and every week label on the x-axis carries a meaningless midnight. The
assumption that PostgreSQL's ``date_trunc('week', ...)`` matches Python's
``d - timedelta(days=d.weekday())`` is proved, not assumed, by
``tests/test_query_oracle.py::test_week_buckets_are_the_monday_of_the_order_date``.

**Why the month bucket is text, not a date.** ``to_char(..., 'YYYY-MM')`` gives a key that
is already the axis label and that sorts correctly as a string, so nothing downstream has
to know it was ever a date.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from sqlalchemy import ColumnElement, Date, SQLColumnExpression, cast, func
from sqlalchemy.orm import InstrumentedAttribute

from logistics_analytics.calculator.models import Filters, GroupBy
from logistics_analytics.data.models import Order


def _week_bucket() -> SQLColumnExpression[Any]:
    """Monday of the week the order was placed in, as a date (D12)."""
    return cast(func.date_trunc("week", Order.order_date), Date)


def _month_bucket() -> SQLColumnExpression[Any]:
    """Calendar month the order was placed in, as ``YYYY-MM``."""
    return func.to_char(Order.order_date, "YYYY-MM")


#: Bucket expression per group-by. ``GroupBy.NONE`` is deliberately absent: "no bucket" is
#: the absence of a column, not a column, and the query builder branches on it.
GROUP_EXPRESSIONS: Mapping[GroupBy, Callable[[], SQLColumnExpression[Any]]] = {
    GroupBy.WEEK: _week_bucket,
    GroupBy.MONTH: _month_bucket,
    GroupBy.CARRIER: lambda: Order.carrier,
    GroupBy.STATUS: lambda: Order.status,
    GroupBy.SKU: lambda: Order.sku,
    GroupBy.PRODUCT_CATEGORY: lambda: Order.product_category,
    GroupBy.REGION: lambda: Order.region,
    GroupBy.WAREHOUSE: lambda: Order.warehouse,
}


DimensionFilter = tuple[InstrumentedAttribute[str | None], str | None]


def _dimension_filters(filters: Filters) -> tuple[DimensionFilter, ...]:
    """Pair each dimension filter with the column it narrows.

    Spelled out rather than derived by ``getattr`` from the field names: a typo in a field
    name would then silently filter on nothing, and a filter that quietly does nothing is
    worse than one that fails to compile.
    """
    return (
        (Order.carrier, filters.carrier),
        (Order.status, filters.status),
        (Order.sku, filters.sku),
        (Order.product_category, filters.product_category),
        (Order.region, filters.region),
        (Order.warehouse, filters.warehouse),
    )


def filter_conditions(filters: Filters) -> tuple[ColumnElement[bool], ...]:
    """Turn a filter set into WHERE clauses, skipping every filter that was not set.

    The date range is inclusive at both ends because that is how a manager reads a month,
    and it applies to ``order_date`` for the reason given on :class:`Filters`.
    """
    conditions: list[ColumnElement[bool]] = []
    if filters.date_from is not None:
        conditions.append(Order.order_date >= filters.date_from)
    if filters.date_to is not None:
        conditions.append(Order.order_date <= filters.date_to)
    conditions.extend(
        column == value for column, value in _dimension_filters(filters) if value is not None
    )
    return tuple(conditions)
