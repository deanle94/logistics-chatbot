"""S2.2 — the query tool: result, rows, echoed params, display type.

Runs without PostgreSQL because ``run_query`` takes its executor as a parameter (D18), so a
canned row set proves the mapping and the display rule in milliseconds. What the numbers
*are* is proved separately against the live database — that is the stack gate's job and
D19's whole point. This file is about shape, not arithmetic.

Display-type selection lives here rather than in ``agent/`` on purpose: it is presentation
routing, not a formula, and a model that chooses its own chart can choose one the data
cannot support.
"""

from __future__ import annotations

import datetime
import json
from typing import Any

import pytest
from sqlalchemy import Row

from logistics_analytics.calculator.models import GroupBy, Metric
from logistics_analytics.tools.query_tool import DisplayType, run_query_tool
from logistics_analytics.tools.schemas import DateRangeSymbol, QueryToolParams


class FakeRow:
    """The two things ``_to_result_row`` uses: positional access and nothing else."""

    def __init__(self, *values: object) -> None:
        """Store the cells in the order the statement selected them."""
        self._values = values

    def __getitem__(self, index: int) -> object:
        """Positional access, which is the only way the row mapper reads a row."""
        return self._values[index]


def executor_returning(*rows: FakeRow) -> Any:  # noqa: ANN401 - a callable, not a value
    """A stand-in for the database that yields exactly the rows a test cares about."""

    def execute(_statement: Any) -> tuple[Row[Any], ...]:  # noqa: ANN401 - an unrun Select
        return tuple(rows)  # type: ignore[arg-type]

    return execute


def test_a_single_number_is_a_stat() -> None:
    """No split means one figure, and one figure has no chart to draw."""
    answer = run_query_tool(
        executor_returning(FakeRow(400)),
        QueryToolParams(metrics=[Metric.ORDER_COUNT]),
    )

    assert answer.display is DisplayType.STAT
    assert answer.rows == [{"group": None, "order_count": 400}]
    assert answer.data == {"metric": "order_count", "value": 400}


@pytest.mark.parametrize("bucket", [GroupBy.WEEK, GroupBy.MONTH])
def test_a_time_series_is_a_line(bucket: GroupBy) -> None:
    """Week and month are the only buckets that carry an order, so only they get a line."""
    answer = run_query_tool(
        executor_returning(FakeRow("2025-01", 31), FakeRow("2025-02", 28)),
        QueryToolParams(metrics=[Metric.ORDER_COUNT], group_by=bucket),
    )

    assert answer.display is DisplayType.LINE
    assert answer.data is None


@pytest.mark.parametrize(
    "bucket",
    [
        GroupBy.CARRIER,
        GroupBy.STATUS,
        GroupBy.SKU,
        GroupBy.PRODUCT_CATEGORY,
        GroupBy.REGION,
        GroupBy.WAREHOUSE,
    ],
)
def test_a_category_comparison_is_a_bar(bucket: GroupBy) -> None:
    """Categories that have no natural order are compared, not tracked."""
    answer = run_query_tool(
        executor_returning(FakeRow("GLS", 28.6), FakeRow("DHL", 23.9)),
        QueryToolParams(metrics=[Metric.DELAY_RATE], group_by=bucket),
    )

    assert answer.display is DisplayType.BAR


def test_two_counts_are_a_stacked_bar_even_over_a_time_bucket() -> None:
    """The pair test must be applied before the bucket test.

    "On time vs delayed per month" is both two series and a month bucket. Checking the
    bucket first would draw two overlapping lines instead of the stacked bar the design
    specifies, so the ordering of these two rules is itself the acceptance criterion.
    """
    answer = run_query_tool(
        executor_returning(FakeRow("2025-01", 24, 5), FakeRow("2025-02", 22, 4)),
        QueryToolParams(
            metrics=[Metric.DELIVERED_ORDERS, Metric.DELAYED_ORDERS], group_by=GroupBy.MONTH
        ),
    )

    assert answer.display is DisplayType.STACKED
    assert answer.rows[0] == {"group": "2025-01", "delivered_orders": 24, "delayed_orders": 5}


def test_echoed_params_equal_the_input_field_for_field() -> None:
    """Requirement 2.4: the panel must describe the query that actually ran."""
    params = QueryToolParams(
        metrics=[Metric.DELAYED_ORDERS],
        group_by=GroupBy.WEEK,
        date_from=datetime.date(2025, 10, 1),
        date_to=datetime.date(2025, 12, 31),
        region="US-E",
    )
    answer = run_query_tool(executor_returning(FakeRow("2025-10-06", 2)), params)

    assert answer.explanation.metrics == ["delayed_orders"]
    assert answer.explanation.group_by == "week"
    assert answer.explanation.filters == {
        "date_from": "2025-10-01",
        "date_to": "2025-12-31",
        "region": "US-E",
    }
    assert answer.explanation.row_count == 1


def test_an_empty_result_is_a_valid_answer() -> None:
    """D15: no rows is 200 with the params still echoed, never an error."""
    answer = run_query_tool(
        executor_returning(),
        QueryToolParams(metrics=[Metric.ORDER_COUNT], carrier="Nonexistent"),
    )

    assert answer.rows == []
    assert answer.explanation.filters == {"carrier": "Nonexistent"}
    assert answer.explanation.row_count == 0


def test_a_relative_period_is_resolved_by_the_tools_layer() -> None:
    """Rule 3: the model emits ``last_3_months``; concrete dates are computed here.

    The resolved window is echoed as dates, not as the symbol, because the explainability
    panel has to show which period was actually counted — "last 3 months" is not an answer
    to "which three".
    """
    params = QueryToolParams(metrics=[Metric.ORDER_COUNT], date_range=DateRangeSymbol.LAST_3_MONTHS)
    answer = run_query_tool(
        executor_returning(FakeRow(0)), params, today=datetime.date(2026, 8, 24)
    )

    assert answer.explanation.filters["date_from"] == "2026-05-24"
    assert answer.explanation.filters["date_to"] == "2026-08-24"


def test_the_tool_hands_the_model_json_it_can_be_checked_against() -> None:
    """The model is shown a string, and rule 1 is checked against those exact bytes.

    Returning an object and re-serialising it for the digit check would leave room for the
    two to differ; then "the model saw this number" would be an inference rather than a
    fact.
    """
    answer = run_query_tool(
        executor_returning(FakeRow("GLS", 28.6)),
        QueryToolParams(metrics=[Metric.DELAY_RATE], group_by=GroupBy.CARRIER),
    )
    payload = json.loads(answer.as_tool_content())

    assert payload["rows"] == [{"group": "GLS", "delay_rate": 28.6}]
    assert payload["display"] == "bar"
