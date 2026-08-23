"""S1.3 / S1.4 — the four routes' wire contract, proved without a database.

The executor is injected (coding rule 5), so these tests pin the exact JSON the browser
will receive while the database stays out of the picture. Canned rows are used on
purpose: the point here is the *shape*, and the numbers are proved against the CSV
oracle in the stack tests.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Row, Select

from logistics_analytics.main import create_app


class RecordingExecutor:
    """Query executor stub that returns canned rows and keeps the statements it saw.

    Recording the statement is what lets a test assert the route *built* something,
    rather than only that it answered 200 with a hardcoded body.
    """

    def __init__(self, rows: Sequence[tuple[object, ...]]) -> None:
        """Store the rows every call will return. Nothing is constructed here."""
        self._rows = tuple(rows)
        self.statements: list[Select[Any]] = []

    def __call__(self, statement: Select[Any]) -> tuple[Row[Any], ...]:
        """Record the statement and hand back the canned rows."""
        self.statements.append(statement)
        return cast("tuple[Row[Any], ...]", self._rows)


def app_returning(rows: Sequence[tuple[object, ...]]) -> tuple[FastAPI, RecordingExecutor]:
    """Build the real application wired to a stub executor."""
    executor = RecordingExecutor(rows)
    return create_app(database_probe=lambda: True, execute_query=executor), executor


KPI_ROW = (400, 304, 55, Decimal("84.7"), Decimal("3.8"))


def test_kpis_route_returns_the_five_dashboard_kpis_with_units() -> None:
    """S1.3: field for field, including the unit that D13 says the calculator owns."""
    app, executor = app_returning([KPI_ROW])

    response = TestClient(app).get("/kpis")

    assert response.status_code == 200
    assert response.json() == {
        "total_orders": {"value": 400, "unit": None},
        "delivered_orders": {"value": 304, "unit": None},
        "delayed_orders": {"value": 55, "unit": None},
        "on_time_rate": {"value": 84.7, "unit": "%"},
        "average_delivery_time": {"value": 3.8, "unit": "days"},
    }
    assert len(executor.statements) == 1, "the five KPIs must come from one query, not five"


def test_order_volume_route_returns_flat_rows_and_echoes_its_params() -> None:
    """S1.4 chart 1. Flat rows are what recharts and the data table consume directly."""
    app, executor = app_returning([("2025-01", 26), ("2025-02", 30)])

    response = TestClient(app).get("/dashboard/order-volume")

    assert response.status_code == 200
    assert response.json() == {
        "rows": [
            {"group": "2025-01", "order_count": 26},
            {"group": "2025-02", "order_count": 30},
        ],
        "params": {
            "metrics": ["order_count"],
            "group_by": "month",
            "filters": {},
            "order": "group",
        },
    }
    assert len(executor.statements) == 1, "one fixed call into the engine, not one per row"


def test_delivery_performance_route_returns_both_series_on_each_row() -> None:
    """S1.4 chart 2: one row per month carrying both stacked-bar series."""
    app, executor = app_returning([("2025-01", 20, 4)])

    response = TestClient(app).get("/dashboard/delivery-performance")

    assert response.status_code == 200
    assert response.json() == {
        "rows": [{"group": "2025-01", "delivered_orders": 20, "delayed_orders": 4}],
        "params": {
            "metrics": ["delivered_orders", "delayed_orders"],
            "group_by": "month",
            "filters": {},
            "order": "group",
        },
    }
    assert len(executor.statements) == 1, "both series come from one pass, not one query each"


def test_carrier_delay_rate_route_echoes_its_descending_order() -> None:
    """S1.4 chart 3 (D14). The echoed order is part of the explanation, not decoration."""
    app, executor = app_returning([("GLS", Decimal("0.2857")), ("USPS", Decimal("0.2391"))])

    response = TestClient(app).get("/dashboard/carrier-delay-rate")

    assert response.status_code == 200
    assert response.json() == {
        "rows": [
            {"group": "GLS", "delay_rate": 0.2857},
            {"group": "USPS", "delay_rate": 0.2391},
        ],
        "params": {
            "metrics": ["delay_rate"],
            "group_by": "carrier",
            "filters": {},
            "order": "value_desc",
        },
    }
    assert len(executor.statements) == 1, "one fixed call into the engine, not one per carrier"


@pytest.mark.parametrize(
    "path",
    ["/dashboard/order-volume", "/dashboard/delivery-performance", "/dashboard/carrier-delay-rate"],
)
def test_an_empty_result_is_a_200_with_the_params_still_echoed(path: str) -> None:
    """D15: nothing matched is an answer, not an error — and it still explains itself."""
    app, _ = app_returning([])

    response = TestClient(app).get(path)

    assert response.status_code == 200
    body = response.json()
    assert body["rows"] == []
    assert body["params"]["metrics"], "the params must survive an empty result set"
    assert body["params"]["filters"] == {}


def test_the_metric_keys_are_named_by_the_echoed_params() -> None:
    """The explainability mechanism Slice 2 reuses: params tell you which keys are metrics."""
    app, _ = app_returning([("2025-01", 20, 4)])

    body = TestClient(app).get("/dashboard/delivery-performance").json()

    row = body["rows"][0]
    assert set(row) == {"group", *body["params"]["metrics"]}
