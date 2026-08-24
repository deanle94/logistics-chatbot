"""S2.2 — the one tool that actually runs a query, plus the two that deliberately do not.

This layer is the seam between a validated request and the S1.2 engine. It adds no formula:
what a metric is and what a bucket is are both defined in ``calculator/``. What it does own
is everything the model must not decide — resolving a relative period to real dates
(agent-design rule 3), choosing the display type, and shaping the answer envelope.

Display selection lives here rather than in ``agent/`` because it is presentation routing,
not interpretation, and because a model that picks its own chart can pick one the data
cannot support. The four tests are applied in a fixed order and the order is itself the
rule — see :func:`_display_for`.

The tool hands the model a JSON *string* rather than an object. That is what lets the
enforce node check "every digit in the prose exists in the tool result" against the exact
bytes the model was shown, instead of against a re-serialisation that could differ.
"""

from __future__ import annotations

import calendar
import datetime
import json
from dataclasses import asdict, dataclass
from enum import StrEnum

from langchain_core.tools import BaseTool, StructuredTool

from logistics_analytics.calculator.models import (
    Filters,
    GroupBy,
    Metric,
    Ordering,
    QueryResult,
    QuerySpec,
)
from logistics_analytics.calculator.query import ExecuteQuery, run_query
from logistics_analytics.tools.schemas import (
    DateRangeSymbol,
    FollowUpParams,
    QueryToolParams,
    RefusalParams,
)

#: How far back each relative period reaches, in whole months from today.
MONTHS_BACK: dict[DateRangeSymbol, int] = {
    DateRangeSymbol.LAST_MONTH: 1,
    DateRangeSymbol.LAST_3_MONTHS: 3,
    DateRangeSymbol.LAST_6_MONTHS: 6,
    DateRangeSymbol.LAST_12_MONTHS: 12,
}

#: The two buckets that carry a natural order, so only they are drawn as a series.
TIME_BUCKETS: frozenset[GroupBy] = frozenset({GroupBy.WEEK, GroupBy.MONTH})

#: The one key an in-domain refusal hands back. Deliberately *not* an answer envelope: the
#: agent's enforce node is the single place a refusal envelope is ever built (agent-design
#: rule 4 / D23), so the two refusal layers cannot drift into two shapes that merely look
#: alike. This layer therefore reports only *why*, and the same constant is spelled out in
#: ``agent/nodes.py`` because ``agent/`` may not import this package (rule 5).
REFUSAL_REASON_KEY = "refusal_reason"


class DisplayType(StrEnum):
    """How an answer is drawn. The tool decides; neither the model nor the browser does."""

    STAT = "stat"
    LINE = "line"
    BAR = "bar"
    STACKED = "stacked"


@dataclass(frozen=True)
class QueryExplanation:
    """The question that produced the rows, echoed back field for field.

    Identical to the dashboard's ``ChartParams`` plus ``row_count``, on purpose: the chat's
    answer then feeds the same explainability panel and data table the dashboard already
    has, with no second type to keep in step.
    """

    metrics: list[str]
    group_by: str
    filters: dict[str, str]
    order: str
    row_count: int


@dataclass(frozen=True)
class QueryAnswer:
    """One tool result: what to draw, the headline figure, the rows, and the question."""

    display: DisplayType
    data: dict[str, str | float | int] | None
    rows: list[dict[str, str | float | int | None]]
    explanation: QueryExplanation

    def as_tool_content(self) -> str:
        """Serialise the answer as the JSON string handed back to the model.

        This string is both what the model reads and what the digit check is run against,
        so there is exactly one set of bytes and "the model saw this number" is a fact
        rather than an inference.
        """
        return json.dumps(
            {
                "display": self.display.value,
                "data": self.data,
                "rows": self.rows,
                "explanation": asdict(self.explanation),
            }
        )


def run_query_tool(
    execute: ExecuteQuery,
    params: QueryToolParams,
    today: datetime.date | None = None,
) -> QueryAnswer:
    """Answer one validated question against the database.

    ``today`` is a parameter rather than a call to the clock inside, so the relative-period
    resolution is testable without freezing time (coding rule 5). ``execute`` is a parameter
    for the same reason the calculator takes one — this layer never opens a connection.
    """
    anchor = today or datetime.date.today()
    filters = _filters_for(params, anchor)
    spec = QuerySpec(
        metrics=tuple(params.metrics),
        group_by=params.group_by,
        filters=filters,
        order=_ordering_for(params.group_by),
    )
    return _to_answer(run_query(execute, spec))


def build_agent_tools(execute: ExecuteQuery) -> list[BaseTool]:
    """The three legal outputs of the Answer node, as tools it can call.

    Two of them run nothing. Making the follow-up and the refusal *tools* rather than prose
    is what lets forced tool choice apply to all three: with the provider refusing to return
    bare text on the first turn, "a tool call before any text" is structural rather than an
    instruction the model may ignore.

    The executor is injected and the list is handed to ``agent/`` by the composition root,
    which is what keeps the agent layer free of any import into this one.
    """

    def query(**kwargs: object) -> str:
        """Validate the model's parameters, run them, and hand back the JSON it will read."""
        return run_query_tool(execute, QueryToolParams(**kwargs)).as_tool_content()  # type: ignore[arg-type]

    return [
        StructuredTool.from_function(
            func=query,
            name="query",
            description=(
                "Count and aggregate the orders on record. Use it for any question about "
                "how many, how often, how long or how much, optionally split by one "
                "attribute and narrowed to one period or one value."
            ),
            args_schema=QueryToolParams,
        ),
        StructuredTool.from_function(
            func=_ask_follow_up,
            name="ask_follow_up",
            description=(
                "Ask the customer for the one parameter a query needs and the question did "
                "not give. Only for a figure or a time bucket that is genuinely absent - "
                "not for an attribute no query offers, which is a refusal instead."
            ),
            args_schema=FollowUpParams,
        ),
        StructuredTool.from_function(
            func=_refuse_unsupported,
            name="refuse_unsupported",
            description=(
                "Decline a question no query can serve. Prefer this over asking a follow-up "
                "whenever the attribute or figure the customer named simply does not exist "
                "here - narrowing to the nearest available thing answers a question nobody "
                "asked."
            ),
            args_schema=RefusalParams,
        ),
    ]


def _ask_follow_up(**kwargs: object) -> str:
    """Turn a follow-up into the envelope the interface renders. Runs no query."""
    follow_up = FollowUpParams(**kwargs)  # type: ignore[arg-type]
    return json.dumps(
        {
            "answer": follow_up.question,
            "display": "follow_up",
            "data": None,
            "rows": [],
            "explanation": None,
            "follow_up": follow_up.model_dump(mode="json"),
        }
    )


def _refuse_unsupported(**kwargs: object) -> str:
    """Report why the question cannot be served, and build no envelope at all.

    Rule 4 says both refusal layers emit the identical envelope. Building one here as well
    would make that a resemblance kept up by hand; handing back only the reason makes it a
    single dict literal in ``agent/nodes.py`` that both branches of the graph execute.
    """
    refusal = RefusalParams(**kwargs)  # type: ignore[arg-type]
    return json.dumps({REFUSAL_REASON_KEY: refusal.reason})


def _filters_for(params: QueryToolParams, today: datetime.date) -> Filters:
    """Build the calculator's filter set, resolving a relative period on the way.

    Explicit dates win over a symbol: if the customer named a real window the model should
    not have sent a symbol at all, and honouring the concrete answer is the safer of the
    two readings.
    """
    date_from, date_to = params.date_from, params.date_to
    if date_from is None and date_to is None and params.date_range is not None:
        date_from = _months_before(today, MONTHS_BACK[params.date_range])
        date_to = today
    return Filters(
        date_from=date_from,
        date_to=date_to,
        carrier=params.carrier,
        status=params.status,
        sku=params.sku,
        product_category=params.product_category,
        region=params.region,
        warehouse=params.warehouse,
    )


def _months_before(day: datetime.date, months: int) -> datetime.date:
    """The same day-of-month, ``months`` calendar months earlier, clamped to a real date.

    Clamping matters at the end of a month: three months before 31 May is 28 or 29
    February, and a naive subtraction of 90 days would silently shift every window by a
    couple of days depending on which months it crossed.
    """
    total = day.year * 12 + (day.month - 1) - months
    year, month = divmod(total, 12)
    return datetime.date(year, month + 1, min(day.day, calendar.monthrange(year, month + 1)[1]))


def _ordering_for(group_by: GroupBy) -> Ordering:
    """Chronological for a series, worst-first for a comparison of peers.

    A ranking only reads as an answer when the worst is at the top, and a time series only
    reads as one when it runs forwards; there is no third case, so this is a single test.
    """
    if group_by is GroupBy.NONE or group_by in TIME_BUCKETS:
        return Ordering.GROUP
    return Ordering.VALUE_DESC


def _display_for(metrics: tuple[Metric, ...], group_by: GroupBy) -> DisplayType:
    """Pick the display type. The order of these tests is the rule, not an implementation.

    "Compare the two outcomes per month" is both a pair and a month bucket. Testing the
    bucket first would draw two overlapping lines instead of the stacked bar the design
    calls for, so the pair test has to come first.
    """
    if len(metrics) == 2:
        return DisplayType.STACKED
    if group_by is GroupBy.NONE:
        return DisplayType.STAT
    if group_by in TIME_BUCKETS:
        return DisplayType.LINE
    return DisplayType.BAR


def _to_answer(result: QueryResult) -> QueryAnswer:
    """Flatten a query result into the answer envelope, adding nothing to the numbers."""
    spec = result.spec
    rows: list[dict[str, str | float | int | None]] = [
        {"group": row.group, **{metric.value: value for metric, value in row.values.items()}}
        for row in result.rows
    ]
    display = _display_for(spec.metrics, spec.group_by)
    return QueryAnswer(
        display=display,
        data=_headline(display, spec.metrics[0], rows),
        rows=rows,
        explanation=QueryExplanation(
            metrics=[metric.value for metric in spec.metrics],
            group_by=spec.group_by.value,
            filters=spec.filters.applied(),
            order=spec.order.value,
            row_count=len(rows),
        ),
    )


def _headline(
    display: DisplayType,
    metric: Metric,
    rows: list[dict[str, str | float | int | None]],
) -> dict[str, str | float | int] | None:
    """The single figure a stat card prints, or ``None`` when there is a chart instead.

    Empty is a valid answer (D15), so an ungrouped query that matched nothing has no
    headline rather than a zero — "no data" and "zero" are different answers.
    """
    if display is not DisplayType.STAT or not rows:
        return None
    value = rows[0][metric.value]
    if value is None:
        return None
    return {"metric": metric.value, "value": value}
