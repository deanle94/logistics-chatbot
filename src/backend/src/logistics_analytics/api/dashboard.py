"""S1.4 — the three parameterless chart routes (decision D9).

Three fixed routes under ``/dashboard/`` rather than one composed ``/api/charts`` and
rather than a public generic query API. The front-end composes the page and owns the three
display types; a fourth chart is a backend change, which is the cost D9 accepted.

The only thing this module decides is *which three questions the dashboard asks* — the
three :class:`QuerySpec` constants below. It holds no formula: what a delay rate is, and
what a month bucket is, are both defined in ``calculator/``. Each route is one call into
the S1.2 engine.

**The routes take no parameters (decision D10).** No user-supplied string reaches the query
builder in Slice 1, which is what lets parameter validation stay S2.1 work.

**Empty is 200, not an error (decision D15).** ``rows`` comes back empty and ``params`` is
still echoed, so the explainability panel renders either way and the caller checks
``length === 0`` rather than a status code.

Paths are ``/dashboard/...`` because nginx strips the ``/api`` prefix on the way through.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from logistics_analytics.calculator.models import GroupBy, Metric, Ordering, QueryResult, QuerySpec
from logistics_analytics.calculator.query import run_query
from logistics_analytics.data.repository import QueryExecutor

#: Chart 1 - order volume over time. Orders per calendar month, in date order.
ORDER_VOLUME_SPEC = QuerySpec(metrics=(Metric.ORDER_COUNT,), group_by=GroupBy.MONTH)

#: Chart 2 - delivery performance. Both stacked-bar series in one pass, so the two are
#: guaranteed to be bucketed identically.
DELIVERY_PERFORMANCE_SPEC = QuerySpec(
    metrics=(Metric.DELIVERED_ORDERS, Metric.DELAYED_ORDERS),
    group_by=GroupBy.MONTH,
)

#: Chart 3 - carrier breakdown as delay rate, worst first (D14, following
#: ``docs/design/Main.dc.html``: "Share arriving late, per carrier"). This one does not sum
#: to 400, which is why the total cross-check applies only to the other two.
CARRIER_DELAY_RATE_SPEC = QuerySpec(
    metrics=(Metric.DELAY_RATE,),
    group_by=GroupBy.CARRIER,
    order=Ordering.VALUE_DESC,
)


class ChartParams(BaseModel):
    """The question that produced the rows, echoed back.

    This is the explainability mechanism of ``docs/requirement.md`` section 2.4, and Slice 2
    reuses it unchanged for chat answers. ``metrics`` is what tells a caller which keys in a
    row are metric keys, so it is always present even when there are no rows at all.
    """

    metrics: list[str]
    group_by: str
    filters: dict[str, str]
    order: str


class ChartResponse(BaseModel):
    """A chart's data and its explanation.

    Rows are flat — one ``group`` key plus one key per metric — because that is the shape
    recharts and the data table consume directly. A nested ``{group, values: {...}}`` would
    make every consumer unwrap it first.
    """

    rows: list[dict[str, str | float | int | None]]
    params: ChartParams


def _to_response(result: QueryResult) -> ChartResponse:
    """Flatten a query result onto the wire, adding nothing and dropping nothing."""
    return ChartResponse(
        rows=[
            {"group": row.group, **{metric.value: value for metric, value in row.values.items()}}
            for row in result.rows
        ],
        params=ChartParams(
            metrics=[metric.value for metric in result.spec.metrics],
            group_by=result.spec.group_by.value,
            filters=result.spec.filters.applied(),
            order=result.spec.order.value,
        ),
    )


def create_dashboard_router(execute: QueryExecutor) -> APIRouter:
    """Build the three chart routes around a given query executor.

    A factory taking the executor, like ``create_health_router``: the routes depend on the
    Protocol, so this layer never imports the database.
    """
    router = APIRouter(prefix="/dashboard", tags=["dashboard"])

    @router.get(
        "/order-volume",
        response_model=ChartResponse,
        summary="Orders per month, for the line chart",
    )
    def read_order_volume() -> ChartResponse:
        """Chart 1: how order volume moved across the dataset."""
        return _to_response(run_query(execute, ORDER_VOLUME_SPEC))

    @router.get(
        "/delivery-performance",
        response_model=ChartResponse,
        summary="Delivered against delayed per month, for the stacked bar chart",
    )
    def read_delivery_performance() -> ChartResponse:
        """Chart 2: on-time against late, month by month."""
        return _to_response(run_query(execute, DELIVERY_PERFORMANCE_SPEC))

    @router.get(
        "/carrier-delay-rate",
        response_model=ChartResponse,
        summary="Share of finished orders arriving late per carrier, worst first",
    )
    def read_carrier_delay_rate() -> ChartResponse:
        """Chart 3: which carrier is letting deliveries slip (D14)."""
        return _to_response(run_query(execute, CARRIER_DELAY_RATE_SPEC))

    return router
