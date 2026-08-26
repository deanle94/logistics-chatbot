"""S3.1 — the demand forecast: history, projection, recommendation, methodology.

Every formula of requirement 2.5 lives in this module and nowhere else — the AI fills in
``{sku, horizon}`` and computes nothing (architecture Decision 1). The method is the
3-month moving average the spec review chose (Q1): each month ahead is the average of the
three months before it, forecasts included once the real months run out, which is exactly
the worked example in ``docs/design/ChatForecast.dc.html`` and the reason a reviewer can
check every projected number by hand.

History comes from the untouched S1.2 engine — the same ``run_query`` the dashboard and
the chat's query tool use — so the plotted history can never disagree with the same
question asked as a plain query. The constants below are mirrored in
``docs/business-definition.md``, which owns the business rulebook.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from logistics_analytics.calculator.models import Filters, GroupBy, Metric, QuerySpec
from logistics_analytics.calculator.query import ExecuteQuery, run_query

#: The moving-average window, in months (spec review Q1; docs/business-definition.md).
WINDOW_MONTHS = 3

#: The safety buffer on the recommended stock, as a percentage (spec review Q2 — buffer
#: only, no reorder point; docs/business-definition.md). Our assumption, and said so.
SAFETY_BUFFER_PCT = 15.0

#: Why a forecast was declined, in words the customer reads verbatim as the refusal
#: answer. Deliberately digit-free — a refusal may state no figure (agent-design rule 1
#: has no tool result to vouch for one) — which is also why it cannot quote the SKU code:
#: the codes carry digits. The window length is therefore spelled out in words.
INSUFFICIENT_HISTORY_REASON = (
    "I can only forecast a product with at least three whole months of order history, and "
    "this product code has less than that on record. I can show its monthly quantity "
    "instead, or forecast a product that has been ordered for longer."
)


class InsufficientHistoryError(Exception):
    """Raised when a SKU has fewer months with data than the window needs.

    An unknown SKU is the same condition — zero months of history — so both refusals take
    one path and the tool layer cannot invent a second refusal shape (spec review Q4).
    """

    def __init__(self, reason: str) -> None:
        """Carry the customer-facing reason; the tool hands it back verbatim."""
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class ForecastResult:
    """The four parts of requirement 2.5, plus the parameters that produced them.

    ``history`` and ``forecast`` are (month, value) pairs rather than a merged series so
    the tool layer can shape the wire rows without knowing which values were measured and
    which were projected — that distinction is this module's to make.
    """

    sku: str
    horizon: int
    window: int
    history: tuple[tuple[str, float | int], ...]
    forecast: tuple[tuple[str, int], ...]
    total: int
    recommended_stock: int
    buffer_pct: float
    methodology: str


def moving_average(
    series: Sequence[float | int], horizon: int, window: int = WINDOW_MONTHS
) -> list[int]:
    """Project ``horizon`` values ahead of a series, each the mean of the last ``window``.

    Recursive on purpose: once the real months run out, earlier forecasts join the window
    — that is what the design file's worked example does (January's 173 feeds February).
    Each projection is rounded half-up to whole units before it feeds the next window,
    because demand is counted in units and PostgreSQL's ``round`` — the convention every
    other figure in this project follows — rounds half up, not banker's.
    """
    if len(series) < window:
        message = f"a series of {len(series)} cannot fill a window of {window}"
        raise ValueError(message)

    values: list[float | int] = list(series)
    forecast: list[int] = []
    for _ in range(horizon):
        mean = Decimal(str(sum(values[-window:]))) / Decimal(window)
        value = int(mean.quantize(Decimal(1), rounding=ROUND_HALF_UP))
        forecast.append(value)
        values.append(value)
    return forecast


def run_forecast(execute: ExecuteQuery, sku: str, horizon: int) -> ForecastResult:
    """Answer one validated forecast request: history via S1.2, then the projection.

    The executor is a parameter, never constructed here (coding rule 5) — this module
    describes the history query and does the arithmetic, and nothing else. A month with no
    orders simply is not in the series: the moving average runs over the months that had
    demand, in order, rather than inventing zero-demand months the query never returned.
    """
    result = run_query(
        execute,
        QuerySpec(metrics=(Metric.QUANTITY,), group_by=GroupBy.MONTH, filters=Filters(sku=sku)),
    )
    history = tuple(
        (row.group, value)
        for row in result.rows
        if row.group is not None and (value := row.values[Metric.QUANTITY]) is not None
    )
    if len(history) < WINDOW_MONTHS:
        raise InsufficientHistoryError(INSUFFICIENT_HISTORY_REASON)

    values = moving_average([value for _, value in history], horizon)
    months = _months_after(history[-1][0], horizon)
    total = sum(values)
    return ForecastResult(
        sku=sku,
        horizon=horizon,
        window=WINDOW_MONTHS,
        history=history,
        forecast=tuple(zip(months, values, strict=True)),
        total=total,
        recommended_stock=math.ceil(total * (1 + SAFETY_BUFFER_PCT / 100)),
        buffer_pct=SAFETY_BUFFER_PCT,
        methodology=_methodology(sku, horizon, total),
    )


def _months_after(last: str, horizon: int) -> list[str]:
    """The next ``horizon`` month labels after a ``YYYY-MM``, rolling over year ends.

    Date arithmetic is computation, so it lives here rather than in the tool or the model
    (agent-design rule 3's reasoning, applied forwards instead of backwards).
    """
    year, month = int(last[:4]), int(last[5:7])
    total = year * 12 + (month - 1)
    return [
        f"{index // 12:04d}-{index % 12 + 1:02d}" for index in range(total + 1, total + 1 + horizon)
    ]


def _methodology(sku: str, horizon: int, total: int) -> str:
    """The plain-words explanation of requirement 2.5, built beside the numbers it cites.

    Every digit in it comes from this module's own result, so the prose the model wraps
    around it can echo these figures without failing the no-invented-digit check.
    """
    return (
        f"Each month ahead is the average of the {WINDOW_MONTHS} months before it, using "
        f"earlier projections once the recorded months run out. Monthly demand is the "
        f"total quantity ordered for {sku} in that month. Averaging smooths the series, "
        f"so read the {horizon}-month total of {total} units as a floor rather than an "
        f"exact figure; the recommended stock adds a {SAFETY_BUFFER_PCT:g}% safety buffer "
        f"on top — our assumption, not something the orders state."
    )
