"""S1.3 / S1.4 — the four routes answered by the real service, checked against the CSV.

``test_api_contract.py`` pins the shape with a stub executor; this pins the *numbers*
coming out of the running container. Both are needed: a correct shape over wrong data and
correct data in the wrong shape are different bugs.

The last test goes through nginx instead of the backend port, which is the only check that
the browser-facing ``/api`` prefix really reaches these routes (the proxy strips it).

Marked ``stack``: run with ``pytest -m stack``.
"""

from __future__ import annotations

import itertools
from typing import Any

import httpx
import pytest

from tests.conftest import csv_grouped, csv_metric_value

pytestmark = pytest.mark.stack

REQUEST_TIMEOUT_SECONDS = 30

CsvRows = list[dict[str, str]]


@pytest.fixture(scope="module")
def _stack(compose_stack: None) -> None:
    """Alias so every test in this module implicitly requires the running stack."""
    return compose_stack


def get_json(url: str) -> dict[str, Any]:
    """Fetch a route and fail loudly on anything but 200.

    Asserting the status here rather than in each test keeps the failure message pointed
    at the route that broke instead of at a ``KeyError`` three lines later.
    """
    response = httpx.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
    assert response.status_code == 200, f"{url} -> {response.status_code}: {response.text}"
    body: dict[str, Any] = response.json()
    return body


def test_kpis_route_serves_the_csv_numbers(
    _stack: None, backend_base_url: str, csv_rows: CsvRows
) -> None:
    """S1.3: the live body equals the calculator's five KPIs, field for field."""
    body = get_json(f"{backend_base_url}/kpis")

    assert body["total_orders"] == {
        "value": csv_metric_value(csv_rows, "order_count"),
        "unit": None,
    }
    assert body["delivered_orders"]["value"] == csv_metric_value(csv_rows, "delivered_orders")
    assert body["delayed_orders"]["value"] == csv_metric_value(csv_rows, "delayed_orders")
    assert body["on_time_rate"] == {
        "value": csv_metric_value(csv_rows, "on_time_rate"),
        "unit": "%",
    }
    assert body["average_delivery_time"] == {
        "value": csv_metric_value(csv_rows, "avg_delivery_time"),
        "unit": "days",
    }


def test_order_volume_route_serves_every_month_and_sums_to_the_dataset(
    _stack: None, backend_base_url: str, csv_rows: CsvRows
) -> None:
    """Chart 1: one bucket per month, and the buckets account for all 400 rows."""
    body = get_json(f"{backend_base_url}/dashboard/order-volume")

    expected = {
        key: csv_metric_value(bucket, "order_count")
        for key, bucket in csv_grouped(csv_rows, "month").items()
    }
    actual = {row["group"]: row["order_count"] for row in body["rows"]}

    assert actual == expected
    assert sum(actual.values()) == csv_metric_value(csv_rows, "order_count")
    assert body["params"] == {
        "metrics": ["order_count"],
        "group_by": "month",
        "filters": {},
        "order": "group",
    }


def test_delivery_performance_route_sums_to_the_finished_orders(
    _stack: None, backend_base_url: str, csv_rows: CsvRows
) -> None:
    """Chart 2: the two stacked series cover delivered + delayed and nothing else.

    The total is deliberately not 400: the three statuses that state no delivery outcome
    are excluded by the business definition, and this assertion is what would catch them
    quietly creeping back in.
    """
    body = get_json(f"{backend_base_url}/dashboard/delivery-performance")

    expected = {
        key: (
            csv_metric_value(bucket, "delivered_orders"),
            csv_metric_value(bucket, "delayed_orders"),
        )
        for key, bucket in csv_grouped(csv_rows, "month").items()
    }
    actual = {
        row["group"]: (row["delivered_orders"], row["delayed_orders"]) for row in body["rows"]
    }

    assert actual == expected

    delivered = csv_metric_value(csv_rows, "delivered_orders")
    delayed = csv_metric_value(csv_rows, "delayed_orders")
    assert delivered is not None
    assert delayed is not None
    assert sum(sum(pair) for pair in actual.values()) == delivered + delayed

    # Echoed alongside the numbers, as for the other two charts: a route that drifted to
    # another bucketing could still sum to the same total, and only this catches it.
    assert body["params"] == {
        "metrics": ["delivered_orders", "delayed_orders"],
        "group_by": "month",
        "filters": {},
        "order": "group",
    }


def test_carrier_delay_rate_route_is_sorted_worst_first(
    _stack: None, backend_base_url: str, csv_rows: CsvRows
) -> None:
    """Chart 3 (D14): one row per carrier, rates never increasing down the list."""
    body = get_json(f"{backend_base_url}/dashboard/carrier-delay-rate")

    expected = {
        key: csv_metric_value(bucket, "delay_rate")
        for key, bucket in csv_grouped(csv_rows, "carrier").items()
    }
    rates = [row["delay_rate"] for row in body["rows"]]

    assert {row["group"]: row["delay_rate"] for row in body["rows"]} == expected
    assert len(body["rows"]) == len(expected), "one row per carrier, none dropped or repeated"
    assert rates == sorted(rates, reverse=True), "the worst carrier must be first"

    # Name the head rather than leaving it implied by the dict comparison: a regression to
    # a single row, or to every rate tied, would still satisfy a non-increasing check.
    worst_carrier, worst_rate = max(expected.items(), key=lambda item: item[1] or 0)
    assert (body["rows"][0]["group"], body["rows"][0]["delay_rate"]) == (worst_carrier, worst_rate)
    assert all(higher > lower for higher, lower in itertools.pairwise(rates)), (
        "no two carriers in this dataset share a delay rate, so the order is strict"
    )

    assert body["params"] == {
        "metrics": ["delay_rate"],
        "group_by": "carrier",
        "filters": {},
        "order": "value_desc",
    }


def test_the_browser_facing_api_prefix_reaches_the_same_route(
    _stack: None, frontend_base_url: str, backend_base_url: str
) -> None:
    """The browser only ever calls ``/api/...``; nginx strips the prefix.

    Without this, a route could be correct on :8000 and 404 for every user.
    """
    through_proxy = get_json(f"{frontend_base_url}/api/kpis")
    direct = get_json(f"{backend_base_url}/kpis")

    assert through_proxy == direct
