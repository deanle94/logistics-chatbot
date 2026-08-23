"""The generic query engine: one spec in, one result out.

Every number in the product goes through here — the five KPI cards, the three charts, and
from Slice 2 the chat's query tool. That is the point: a metric can only have one
implementation if there is only one path to it.

**The engine is built but not exposed over HTTP (decision D10).** Only fixed callers reach
it in Slice 1. A public ``{metric, group_by, filters}`` endpoint would accept user-supplied
strings, and the parameter whitelist that makes that safe is S2.1 work.

**Building and running are separate on purpose (decision D18).** :func:`build_statement`
returns an unexecuted ``Select``; :func:`run_query` takes the thing that executes it as a
*parameter* (coding rule 5), so this layer never opens a connection and never learns which
database it is talking to. That is also what makes the whole builder testable without
PostgreSQL — see ``tests/test_query_statements.py``.
"""

from __future__ import annotations

import datetime
from collections.abc import Callable, Sequence
from decimal import Decimal
from typing import Any

from sqlalchemy import Row, Select, SQLColumnExpression, select

from logistics_analytics.calculator.dimensions import GROUP_EXPRESSIONS, filter_conditions
from logistics_analytics.calculator.metrics import METRIC_EXPRESSIONS
from logistics_analytics.calculator.models import (
    GROUP_LABEL,
    GroupBy,
    Ordering,
    QueryResult,
    QuerySpec,
    ResultRow,
)
from logistics_analytics.data.models import Order

#: What "something that can run a statement" looks like from in here.
#:
#: Structurally identical to ``data.repository.QueryExecutor``, and declared separately on
#: purpose: the calculator may describe a query but must never import the layer that
#: connects to the database, so the executor arrives by dependency injection rather than
#: by import. The import-linter contract "The calculator describes queries but never
#: connects" is what keeps that honest.
ExecuteQuery = Callable[[Select[Any]], Sequence[Row[Any]]]


def build_statement(spec: QuerySpec) -> Select[Any]:
    """Compose a spec into an unexecuted SELECT.

    Metric columns are labelled with the metric's own value, which is also its JSON key, so
    the SQL, the result mapping and the wire format all use one name for one number.

    ``select_from(Order)`` is stated rather than inferred. SQLAlchemy works the FROM clause
    out from the entities the selected columns mention, and ``count(*)`` mentions none: an
    ungrouped, unfiltered ``order_count`` compiled to a FROM-less ``SELECT count(*)``, which
    PostgreSQL evaluates over one virtual row and answers ``1`` for a 400-row table. Pinning
    the table here fixes that for every metric at once, including any future one whose
    expression also names no column, and leaves the emitted aggregate untouched.
    """
    if not spec.metrics:
        message = "a query spec must request at least one metric"
        raise ValueError(message)

    columns = [METRIC_EXPRESSIONS[metric]().label(metric.value) for metric in spec.metrics]
    conditions = filter_conditions(spec.filters)

    if spec.group_by is GroupBy.NONE:
        return select(*columns).select_from(Order).where(*conditions)

    bucket = GROUP_EXPRESSIONS[spec.group_by]()
    return (
        select(bucket.label(GROUP_LABEL), *columns)
        .select_from(Order)
        .where(*conditions)
        .group_by(bucket)
        .order_by(_order_clause(spec, bucket))
    )


def _order_clause(spec: QuerySpec, bucket: SQLColumnExpression[Any]) -> SQLColumnExpression[Any]:
    """Pick the ORDER BY: chronological for a series, worst-first for a ranking.

    ``NULLS LAST`` matters for the ranking: a bucket whose rate is undefined (nothing
    finished) would otherwise sort above every real answer in PostgreSQL, which puts NULLs
    first on a descending sort, and the "worst carrier" chart would be headed by a carrier
    with no data.
    """
    if spec.order is Ordering.VALUE_DESC:
        return METRIC_EXPRESSIONS[spec.metrics[0]]().desc().nulls_last()
    return bucket


def run_query(execute: ExecuteQuery, spec: QuerySpec) -> QueryResult:
    """Run a spec and return its rows together with the spec that produced them.

    The executor is a parameter, never constructed here (coding rule 5): that is the seam
    that keeps this layer off the database and lets tests drive it with canned rows.
    """
    rows = execute(build_statement(spec))
    return QueryResult(rows=tuple(_to_result_row(row, spec) for row in rows), spec=spec)


def _to_result_row(row: Row[Any], spec: QuerySpec) -> ResultRow:
    """Map one database row onto the spec that asked for it, by position.

    Position rather than column name because the statement was built from this same spec
    moments ago, so the order is guaranteed and no string lookup can silently miss.
    """
    grouped = spec.group_by is not GroupBy.NONE
    offset = 1 if grouped else 0
    return ResultRow(
        group=_to_group_key(row[0]) if grouped else None,
        values={
            metric: _to_number(row[offset + index]) for index, metric in enumerate(spec.metrics)
        },
    )


def _to_group_key(value: object) -> str | None:
    """Render a bucket key as the string the browser will use as an axis label.

    Dates become ISO strings here rather than in the API layer so that the week bucket
    (D12) reaches every caller — chart, table and Slice 2 chat — in one form.
    """
    if value is None:
        return None
    if isinstance(value, datetime.date):
        return value.isoformat()
    return str(value)


def _to_number(value: object) -> float | int | None:
    """Convert one aggregate cell into a JSON-friendly number.

    ``Decimal`` is what PostgreSQL returns for ``numeric``, and it does not survive JSON
    encoding; it is converted here, after rounding, so no precision decision is made
    outside the metric definitions. NULL stays ``None`` — see :class:`ResultRow`.
    """
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, Decimal | float):
        return float(value)
    message = f"unexpected aggregate value type: {type(value).__name__}"
    raise TypeError(message)
