"""S3.1 — the forecast math, proved against a hand-computed oracle.

Runs without PostgreSQL because ``run_forecast`` takes its executor as a parameter (D18),
exactly like the query tool's tests. What the *history* is on the real database is proved
separately under ``pytest -m stack``; this file proves the arithmetic that turns a history
into a projection, against numbers worked out by hand — including the worked example in
``docs/design/ChatForecast.dc.html``, which is the method's own specification.

The oracle rule: every expected value below is a hand computation written as a literal,
never a call into the code under test.
"""

from __future__ import annotations

from typing import Any

import pytest

from logistics_analytics.calculator.forecast import (
    SAFETY_BUFFER_PCT,
    WINDOW_MONTHS,
    InsufficientHistoryError,
    moving_average,
    run_forecast,
)


class FakeRow:
    """The one thing the row mapper uses: positional access."""

    def __init__(self, *values: object) -> None:
        """Store the cells in the order the statement selected them."""
        self._values = values

    def __getitem__(self, index: int) -> object:
        """Positional access, which is the only way the row mapper reads a row."""
        return self._values[index]


def executor_returning(*rows: FakeRow) -> Any:  # noqa: ANN401 - a callable, not a value
    """A stand-in for the database that yields exactly the rows a test cares about."""

    def execute(_statement: Any) -> tuple[Any, ...]:  # noqa: ANN401 - an unrun Select
        return tuple(rows)

    return execute


def test_the_design_files_worked_example_matches_by_hand() -> None:
    """The design's own series: Oct 172, Nov 168, Dec 180 project to 173, 174, 176, 174.

    Hand computation: (172+168+180)/3 = 173.33 -> 173; then the rounded 173 joins the
    window, (168+180+173)/3 = 173.67 -> 174; (180+173+174)/3 = 175.67 -> 176; and
    (173+174+176)/3 = 174.33 -> 174. Total 697 — the figure the design card prints.
    """
    forecast = moving_average([172, 168, 180], horizon=4, window=3)

    assert forecast == [173, 174, 176, 174]
    assert sum(forecast) == 697


def test_forecasts_feed_later_windows_recursively() -> None:
    """The recursion is the method: 1,5,5 -> 11/3=3.67->4, then 14/3=4.67->5, 5, 5."""
    assert moving_average([1, 5, 5], horizon=4, window=3) == [4, 5, 5, 5]


def test_rounding_is_half_up_to_whole_units() -> None:
    """(2+3)/2 = 2.5 must round to 3, not to banker's 2 — same convention as the KPIs."""
    assert moving_average([2, 3], horizon=1, window=2) == [3]


def test_a_series_shorter_than_the_window_is_rejected() -> None:
    """The pure function refuses too — the guard is not only at the tool boundary."""
    with pytest.raises(ValueError, match="window"):
        moving_average([1, 2], horizon=1, window=3)


def test_run_forecast_builds_all_four_parts() -> None:
    """S3.1's pass condition: history, forecast values, recommendation, methodology.

    The series is PENCIL-0213's real one (1, 5, 5) so the stack oracle later re-derives
    the same numbers from the CSV. By hand: forecasts 4, 5, 5, 5; total 19; recommended
    stock ceil(19 x 1.15) = ceil(21.85) = 22. Month labels continue from the last history
    month and roll over the year end.
    """
    result = run_forecast(
        executor_returning(FakeRow("2025-06", 1), FakeRow("2025-08", 5), FakeRow("2025-09", 5)),
        sku="PENCIL-0213",
        horizon=4,
    )

    assert result.sku == "PENCIL-0213"
    assert result.horizon == 4
    assert result.window == WINDOW_MONTHS
    assert result.history == (("2025-06", 1), ("2025-08", 5), ("2025-09", 5))
    assert result.forecast == (("2025-10", 4), ("2025-11", 5), ("2025-12", 5), ("2026-01", 5))
    assert result.total == 19
    assert result.recommended_stock == 22
    assert result.buffer_pct == SAFETY_BUFFER_PCT
    assert "average" in result.methodology
    assert str(result.total) in result.methodology


def test_the_recommended_stock_matches_the_design_example() -> None:
    """The design card's 802 = ceil(697 x 1.15), computed from its own series."""
    result = run_forecast(
        executor_returning(
            FakeRow("2025-10", 172), FakeRow("2025-11", 168), FakeRow("2025-12", 180)
        ),
        sku="SKU-1042",
        horizon=4,
    )

    assert result.total == 697
    assert result.recommended_stock == 802


def test_a_sparse_history_refuses_with_a_digit_free_reason() -> None:
    """Fewer months with data than the window -> refusal, and the reason states no figure.

    Digit-free matters because the reason becomes the ``unsupported`` envelope's answer
    verbatim, and a refusal may state no figure (agent-design rule 1 has no tool result to
    vouch for one). That also means the reason must not quote the SKU code itself — the
    codes carry digits.
    """
    with pytest.raises(InsufficientHistoryError) as caught:
        run_forecast(executor_returning(FakeRow("2025-10", 2)), sku="PAPER-0197", horizon=4)

    assert not any(character.isdigit() for character in caught.value.reason)
    assert "history" in caught.value.reason


def test_an_unknown_sku_takes_the_same_refusal_path() -> None:
    """No rows at all is zero months of history — the same refusal, not a special case."""
    with pytest.raises(InsufficientHistoryError):
        run_forecast(executor_returning(), sku="SKU-9999", horizon=4)
