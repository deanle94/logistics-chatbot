"""S1.1 — the five dashboard KPIs, as one query through the generic engine.

There is deliberately no second query path here. Five separate calculations would be five
places for a definition to drift and five round trips to the database; instead this is one
ungrouped :class:`QuerySpec` over five metrics, run by the same :func:`run_query` that
serves every chart and, from Slice 2, the chat.

The units live here rather than in the API layer or the browser (decision D13): a number
whose unit is decided downstream can be printed as "84.7" by one caller and "84.7%" by
another, and S2.3 requires the chat and the dashboard to agree digit for digit.
"""

from __future__ import annotations

from collections.abc import Mapping

from logistics_analytics.calculator.models import (
    DashboardKpis,
    KpiValue,
    Metric,
    QuerySpec,
)
from logistics_analytics.calculator.query import ExecuteQuery, run_query

#: The one query behind the whole KPI row. Ungrouped, so PostgreSQL returns exactly one
#: row holding all five numbers.
KPI_SPEC = QuerySpec(
    metrics=(
        Metric.ORDER_COUNT,
        Metric.DELIVERED_ORDERS,
        Metric.DELAYED_ORDERS,
        Metric.ON_TIME_RATE,
        Metric.AVG_DELIVERY_TIME,
    )
)

#: The unit each KPI is printed in. ``None`` means a bare count.
KPI_UNITS: Mapping[Metric, str | None] = {
    Metric.ORDER_COUNT: None,
    Metric.DELIVERED_ORDERS: None,
    Metric.DELAYED_ORDERS: None,
    Metric.ON_TIME_RATE: "%",
    Metric.AVG_DELIVERY_TIME: "days",
}

#: What a KPI reports when its definition has nothing to work with — no finished order, or
#: no row with both dates. Zero rather than ``None`` because a KPI card always shows a
#: number; it can only be reached by an empty dataset, which the seeder rules out.
EMPTY_KPI = 0.0


def compute_kpis(execute: ExecuteQuery) -> DashboardKpis:
    """Compute all five KPIs in one pass.

    The executor is injected (coding rule 5) so this function has no idea a database
    exists; ``tests/test_kpis_oracle.py`` runs it against the real one and
    ``tests/test_api_contract.py`` runs the same code against canned rows.
    """
    result = run_query(execute, KPI_SPEC)
    if not result.rows:
        message = "an ungrouped aggregate must return exactly one row"
        raise ValueError(message)

    values = result.rows[0].values
    return DashboardKpis(
        total_orders=_to_kpi(values, Metric.ORDER_COUNT),
        delivered_orders=_to_kpi(values, Metric.DELIVERED_ORDERS),
        delayed_orders=_to_kpi(values, Metric.DELAYED_ORDERS),
        on_time_rate=_to_kpi(values, Metric.ON_TIME_RATE),
        average_delivery_time=_to_kpi(values, Metric.AVG_DELIVERY_TIME),
    )


def _to_kpi(values: Mapping[Metric, float | int | None], metric: Metric) -> KpiValue:
    """Pair one computed number with the unit its definition says it is measured in."""
    value = values[metric]
    return KpiValue(value=EMPTY_KPI if value is None else value, unit=KPI_UNITS[metric])
