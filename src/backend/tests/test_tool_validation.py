"""S2.1 — the parameter whitelist, the first place a user-influenced string is stopped.

Until Slice 2 no user string reached the query builder at all: the dashboard routes take no
parameters (D10), which is exactly why that decision could defer this work. From today the
model fills these fields, so this module is the boundary D10 promised would become
load-bearing on its first day.

The whitelist is not a second list. ``QueryToolParams`` types its fields with the
calculator's own ``Metric`` and ``GroupBy`` enums, so "what may be asked for" and "what can
be computed" are the same object and cannot drift apart. These tests assert that property
rather than a copy of the vocabulary.
"""

from __future__ import annotations

import datetime
from collections.abc import Sequence
from typing import Any

import pytest
from pydantic import ValidationError

from logistics_analytics.calculator.models import GroupBy, Metric
from logistics_analytics.tools.query_tool import build_agent_tools
from logistics_analytics.tools.schemas import (
    DateRangeSymbol,
    FollowUpParams,
    MissingInfo,
    QueryToolParams,
)

#: Strings a prompt-injection or SQL-injection attempt would plausibly contain. None of
#: them can reach the query builder, but they must be rejected at the schema rather than
#: relied on to be harmless downstream.
INJECTION_ATTEMPTS: tuple[str, ...] = (
    "'; DROP TABLE orders; --",
    "carrier' OR '1'='1",
    "UNION SELECT * FROM pg_shadow",
    "../../etc/passwd",
    "${jndi:ldap://evil}",
    "<script>alert(1)</script>",
    "GLS\x00",
    "GLS; SELECT 1",
)


def test_valid_input_round_trips_unchanged() -> None:
    """The echoed parameters must be the request, field for field.

    This is the explainability contract (requirement 2.4) at its source: if the tool
    quietly normalised a value, the panel would describe a query nobody asked for.
    """
    params = QueryToolParams(
        metrics=[Metric.DELAYED_ORDERS],
        group_by=GroupBy.WEEK,
        date_from=datetime.date(2025, 10, 1),
        date_to=datetime.date(2025, 12, 31),
        region="US-E",
    )

    assert params.metrics == [Metric.DELAYED_ORDERS]
    assert params.group_by is GroupBy.WEEK
    assert params.date_from == datetime.date(2025, 10, 1)
    assert params.date_to == datetime.date(2025, 12, 31)
    assert params.region == "US-E"


@pytest.mark.parametrize("unknown", ["revenue", "profit_margin", "order_count; DROP", "", "*"])
def test_unknown_metric_is_rejected(unknown: str) -> None:
    """A metric outside the calculator's vocabulary never becomes a query."""
    with pytest.raises(ValidationError):
        QueryToolParams(metrics=[unknown])  # type: ignore[list-item]


@pytest.mark.parametrize("unknown", ["destination_city", "customer", "price_band", "", "1"])
def test_unknown_group_by_is_rejected(unknown: str) -> None:
    """A split outside the calculator's vocabulary never becomes a GROUP BY."""
    with pytest.raises(ValidationError):
        QueryToolParams(metrics=[Metric.ORDER_COUNT], group_by=unknown)  # type: ignore[arg-type]


@pytest.mark.parametrize("attempt", INJECTION_ATTEMPTS, ids=range(len(INJECTION_ATTEMPTS)))
def test_injection_looking_filter_values_are_rejected(attempt: str) -> None:
    """Dimension values are pattern-checked, not merely bound as parameters.

    SQLAlchemy would bind these safely, so this is defence in depth rather than the only
    guard. It is worth having: a value that cannot match any row should fail loudly at the
    edge instead of returning a confidently empty answer (D15) that looks like a fact.
    """
    with pytest.raises(ValidationError):
        QueryToolParams(metrics=[Metric.ORDER_COUNT], carrier=attempt)


def test_every_calculator_metric_is_askable() -> None:
    """The whitelist must not silently shrink the vocabulary it claims to mirror.

    Without this, deleting a member from the tool's enum would make the negative tests
    above pass while quietly removing a supported question.
    """
    for metric in Metric:
        assert QueryToolParams(metrics=[metric]).metrics == [metric]


def test_every_calculator_group_by_is_askable() -> None:
    """Same guard for the splits."""
    for group_by in GroupBy:
        params = QueryToolParams(metrics=[Metric.ORDER_COUNT], group_by=group_by)
        assert params.group_by is group_by


def test_two_metrics_may_be_paired_only_when_both_are_counts() -> None:
    """A pair is drawn as one stacked bar, so both halves must be counts of rows.

    Discovered against the real model, not reasoned about: asked to "compare on-time vs
    delayed orders per month" it requested ``on_time_rate`` with ``delay_rate`` — two
    percentages stacked on one axis, which means nothing. Stating the rule in the prompt
    did not hold it; rejecting it here does, because the tool node hands the error back and
    the model corrects itself.
    """
    with pytest.raises(ValidationError):
        QueryToolParams(metrics=[Metric.ON_TIME_RATE, Metric.DELAY_RATE], group_by=GroupBy.MONTH)

    paired = QueryToolParams(
        metrics=[Metric.DELIVERED_ORDERS, Metric.DELAYED_ORDERS], group_by=GroupBy.MONTH
    )
    assert len(paired.metrics) == 2


def test_more_than_two_metrics_is_rejected() -> None:
    """Three series in one answer has no display type, so it is not a legal request."""
    with pytest.raises(ValidationError):
        QueryToolParams(
            metrics=[Metric.ORDER_COUNT, Metric.DELIVERED_ORDERS, Metric.DELAYED_ORDERS]
        )


def test_at_least_one_metric_is_required() -> None:
    """An answer with no figure in it is not an answer."""
    with pytest.raises(ValidationError):
        QueryToolParams(metrics=[])


@pytest.mark.parametrize("symbol", tuple(DateRangeSymbol), ids=[s.value for s in DateRangeSymbol])
def test_relative_periods_are_accepted_as_symbols(symbol: DateRangeSymbol) -> None:
    """Rule 3: the model emits a symbol and the tools layer resolves it, never the model."""
    assert QueryToolParams(metrics=[Metric.ORDER_COUNT], date_range=symbol).date_range is symbol


def test_an_unknown_relative_period_is_rejected() -> None:
    """The symbol set is closed, so a model-invented period cannot reach the resolver."""
    with pytest.raises(ValidationError):
        QueryToolParams(metrics=[Metric.ORDER_COUNT], date_range="since_the_merger")  # type: ignore[arg-type]


def test_unknown_fields_are_rejected() -> None:
    """``extra="forbid"``: a hallucinated parameter is an error, not something ignored.

    Silently dropping an unknown field would let the model believe it had filtered when it
    had not, and the echoed params would then describe the wrong query.
    """
    with pytest.raises(ValidationError):
        QueryToolParams(metrics=[Metric.ORDER_COUNT], destination_city="Hong Kong")  # type: ignore[call-arg]


# --------------------------------------------------------------------------------------
# S2.8 - the follow-up schema. Both of its guarantees are asserted here rather than only
# observed through the live model in ``tests/test_chat_agent_stack.py``: a stack gate that
# happens to see a well-formed follow-up proves the model behaved, not that the schema
# would have stopped it. These are the branches that do the stopping.
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("question", ["Which quarter - Q1 or the last 3 months?", "2025 or 2024?"])
def test_a_follow_up_question_may_state_no_figure(question: str) -> None:
    """Agent-design D3: no tool has run yet, so a digit here is one nothing can vouch for.

    Parametrised over shapes a model actually reaches for - a quarter label, a relative
    window, a year - because each of them carries its digit somewhere different in the
    sentence and the validator has to catch all three the same way.
    """
    with pytest.raises(ValidationError):
        FollowUpParams(missing_info=MissingInfo.TIME_BUCKET, question=question, options=["week"])


def test_a_digit_free_follow_up_round_trips_unchanged() -> None:
    """The positive control: the validator rejects figures, not follow-ups.

    Without this the test above would still pass if ``FollowUpParams`` rejected everything.
    """
    follow_up = FollowUpParams(
        missing_info=MissingInfo.TIME_BUCKET,
        question="Would you like that by week or by month?",
        options=["week", "month"],
    )

    assert follow_up.missing_info is MissingInfo.TIME_BUCKET
    assert follow_up.options == ["week", "month"]


def test_missing_info_is_a_closed_enum() -> None:
    """``"time range"`` is the drift case, not a hypothetical one.

    It is the example ``docs/agent-design.md`` itself uses for ``missing_info``, and an
    unstated period is not missing information - it means every order on record. The enum
    is what makes "which period do you mean?" unaskable rather than merely discouraged.
    """
    assert set(MissingInfo) == {MissingInfo.METRIC, MissingInfo.TIME_BUCKET}

    with pytest.raises(ValidationError):
        FollowUpParams(missing_info="time range", question="Which period?")  # type: ignore[arg-type]


def _nothing_runs(statement: object) -> Sequence[Any]:  # noqa: ARG001
    """A stand-in executor. A rejected follow-up must never reach a query at all."""
    raise AssertionError("no query may run while a follow-up is being validated")


def test_the_bound_follow_up_tool_rejects_a_question_with_a_figure() -> None:
    """The schema is reached through the tool the model actually calls, not only directly.

    ``args_schema`` is what makes the validator load-bearing at the boundary: the model
    never constructs the object itself, it fills in a JSON payload, so this is the call
    site the no-digit rule has to hold at.
    """
    ask_follow_up = {tool.name: tool for tool in build_agent_tools(_nothing_runs)}["ask_follow_up"]

    with pytest.raises(ValidationError):
        ask_follow_up.invoke(
            {"missing_info": "time_bucket", "question": "Q1 or the last 3 months?"}
        )
