"""S3.1 (history oracle) / S3.2 / S3.4 — forecasting through the live service. Real model.

Same discipline as ``test_chat_agent_stack.py``: structure, never wording, retried at most
twice. The forecast adds one oracle of its own — the projected values are re-derived here
by hand-implementing the 3-month moving average over the CSV's own series, independently
of ``calculator/forecast.py``, so the test can never agree with a bug in it.

The SKUs are picked from the dataset deliberately. 400 rows spread over 355 SKUs means
almost every SKU is sparse; PENCIL-0213 is one of the two with the three months of history
the window needs, and PAPER-0197 (one month) is the sparse refusal case.

Marked ``stack``: run with ``pytest -m stack``. Every run costs real money.
"""

from __future__ import annotations

import math
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import pytest

from tests.conftest import csv_expected_rows
from tests.sse_reader import ask, numbers_in
from tests.test_chat_agent_stack import ask_until, assert_grounded, until_it_holds

pytestmark = pytest.mark.stack

#: The one SKU a reviewer should ask about: three months with data in the CSV.
FORECAST_SKU = "PENCIL-0213"

#: One month with data — under the 3-month window, so the tool must refuse.
SPARSE_SKU = "PAPER-0197"

#: Matches the SKU pattern but exists nowhere in the dataset: zero months of history.
UNKNOWN_SKU = "SKU-9999"

CsvRows = list[dict[str, str]]


@pytest.fixture(scope="module")
def _stack(compose_stack: None) -> None:
    """Alias so every test in this module implicitly requires the running stack."""
    return compose_stack


def hand_moving_average(series: list[float | int], horizon: int, window: int) -> list[int]:
    """The 3-month moving average, re-implemented here as the independent oracle.

    Recursive (forecasts join the window), rounded half-up to whole units — the rule the
    design file's worked example fixes. Deliberately written from the business definition
    rather than imported from the calculator, per the oracle rule.
    """
    values: list[float | int] = list(series)
    forecast: list[int] = []
    for _ in range(horizon):
        mean = Decimal(sum(values[-window:])) / Decimal(window)
        value = int(mean.quantize(Decimal(1), rounding=ROUND_HALF_UP))
        forecast.append(value)
        values.append(value)
    return forecast


def test_a_forecast_question_routes_to_the_tool_and_every_number_is_derivable(
    _stack: None, backend_base_url: str, csv_rows: CsvRows
) -> None:
    """S3.2 + S3.1's history oracle, through the live service in one paid turn.

    The history rows must equal the plain S1.2 quantity-by-month query for the same SKU,
    re-run over the raw CSV; the forecast rows must equal the hand oracle applied to that
    same series; and the prose may state no figure the tool result does not contain.
    """

    def check(result: dict[str, Any]) -> None:
        assert result["display"] == "forecast_line"
        explanation = result["explanation"]
        assert explanation["metrics"] == ["quantity"]
        assert explanation["group_by"] == "month"
        assert explanation["filters"] == {"sku": FORECAST_SKU}

        history = {
            row["group"]: {"quantity": row["quantity"]}
            for row in result["rows"]
            if "quantity" in row
        }
        assert history == csv_expected_rows(csv_rows, explanation)
        assert explanation["row_count"] == len(history)

        forecast = result["forecast"]
        assert forecast is not None
        assert forecast["sku"] == FORECAST_SKU
        assert forecast["horizon"] == 4
        assert forecast["window"] == 3

        series = [row["quantity"] for row in result["rows"] if "quantity" in row]
        expected_values = hand_moving_average(series, horizon=4, window=3)
        forecast_rows = [row for row in result["rows"] if "forecast" in row]
        assert [row["forecast"] for row in forecast_rows] == expected_values

        assert forecast["total"] == sum(expected_values)
        assert forecast["recommended_stock"] == math.ceil(sum(expected_values) * 1.15)
        assert_grounded(result)

    ask_until(
        backend_base_url,
        f"Predict demand for {FORECAST_SKU} for the next 4 months",
        check,
    )


def test_the_forecasting_stage_is_streamed_while_the_tool_runs(
    _stack: None, backend_base_url: str
) -> None:
    """D3: the custom stream event reaches the wire as a stage frame, in order."""

    def attempt() -> None:
        answer = ask(backend_base_url, f"Predict demand for {FORECAST_SKU} for the next 4 months")
        assert answer.result["display"] == "forecast_line"
        stages = list(answer.stages)
        assert "forecasting" in stages
        assert stages.index("querying") < stages.index("forecasting")

    until_it_holds(attempt)


@pytest.mark.parametrize("sku", [UNKNOWN_SKU, SPARSE_SKU], ids=["unknown", "sparse"])
def test_a_sku_without_enough_history_is_refused_with_the_one_envelope(
    _stack: None, backend_base_url: str, sku: str
) -> None:
    """S3.4: unknown and sparse SKUs take the identical ``unsupported`` path, no digits.

    The envelope equality itself is gated statically in ``test_agent_rules.py``; what this
    proves is that the *live* forecast refusal reaches it — refusal is a result, never an
    error (D23).
    """

    def check(result: dict[str, Any]) -> None:
        assert result["display"] == "unsupported"
        assert result["data"] is None
        assert result["rows"] == []
        assert result["explanation"] is None
        assert not numbers_in(result["answer"]), "a refusal must not state a figure"

    ask_until(backend_base_url, f"Predict demand for {sku} for the next 4 months", check)
