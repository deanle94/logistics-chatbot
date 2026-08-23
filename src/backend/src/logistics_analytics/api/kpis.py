"""S1.3 — ``GET /kpis``.

Orchestration only: call the calculator, shape the answer as JSON. There is no formula
here and no unit either — both belong to ``calculator/kpis.py`` (D13), and this route only
copies what it is given.

The path is ``/kpis``, not ``/api/kpis``: nginx proxies ``/api/`` with a trailing slash,
which strips the prefix before the request reaches FastAPI. The browser-facing path is the
proxy's business, not this module's.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from logistics_analytics.calculator.kpis import compute_kpis
from logistics_analytics.calculator.models import DashboardKpis, KpiValue
from logistics_analytics.data.repository import QueryExecutor


class KpiValueResponse(BaseModel):
    """One KPI card: the number and the unit it is printed in.

    ``unit`` is nullable rather than an empty string so a bare count is visibly "no unit"
    instead of a unit that happens to render as nothing.
    """

    value: float | int
    unit: str | None


class KpisResponse(BaseModel):
    """The five KPIs of ``docs/requirement.md`` section 2.1, one field each."""

    total_orders: KpiValueResponse
    delivered_orders: KpiValueResponse
    delayed_orders: KpiValueResponse
    on_time_rate: KpiValueResponse
    average_delivery_time: KpiValueResponse


def _to_response(kpi: KpiValue) -> KpiValueResponse:
    """Copy a calculated KPI onto the wire, changing nothing about it."""
    return KpiValueResponse(value=kpi.value, unit=kpi.unit)


def create_kpis_router(execute: QueryExecutor) -> APIRouter:
    """Build the KPI router around a given query executor.

    A factory taking the executor, like ``create_health_router``: the route depends on the
    Protocol, so the API layer never imports the database and every test can supply its own.
    """
    router = APIRouter(tags=["dashboard"])

    @router.get("/kpis", response_model=KpisResponse, summary="The five dashboard KPIs")
    def read_kpis() -> KpisResponse:
        """Return the five KPIs exactly as the calculator computed them."""
        kpis: DashboardKpis = compute_kpis(execute)
        return KpisResponse(
            total_orders=_to_response(kpis.total_orders),
            delivered_orders=_to_response(kpis.delivered_orders),
            delayed_orders=_to_response(kpis.delayed_orders),
            on_time_rate=_to_response(kpis.on_time_rate),
            average_delivery_time=_to_response(kpis.average_delivery_time),
        )

    return router
