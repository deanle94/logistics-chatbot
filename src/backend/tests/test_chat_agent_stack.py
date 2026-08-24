"""S2.3 / S2.4 / S2.8 — the agent answers from the tool, refuses, or asks. Real model.

These call the live Anthropic model through the running service, so they assert *structure*
and never wording: which tool ran, which parameters it ran with, and that every figure in
the prose exists in the tool's own result. A model is free to phrase an answer differently
on a rerun; it is not free to pick a different metric or to state a number nothing
computed.

Each question is retried at most twice. A hosted model at ``temperature=0`` is stable but
not deterministic, and the spec allows the retry; what it does not allow is a skip. When
the provider is unreachable or unauthorised the service emits an error frame and
``result_of`` fails — a green suite that never called the model proves nothing (D19).

Marked ``stack``: run with ``pytest -m stack``. Every run costs real money.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from tests.conftest import csv_expected_rows
from tests.sse_reader import Answer, ask, invented_digits, new_conversation_id, numbers_in

pytestmark = pytest.mark.stack

#: The spec's two-retry allowance: three attempts, then the last failure is the verdict.
MAX_ATTEMPTS = 3

CsvRows = list[dict[str, str]]


@pytest.fixture(scope="module")
def _stack(compose_stack: None) -> None:
    """Alias so every test in this module implicitly requires the running stack."""
    return compose_stack


def until_it_holds(attempt: Callable[[], None]) -> None:
    """Run a whole turn, assertions included, up to the spec's limit.

    The retry wraps the *assertions*, not just the request: a wrong tool choice is exactly
    the flake the allowance exists for, and re-asserting on a fresh answer is the only way
    to use it. Taking the whole attempt as a callable is what lets a two-turn conversation
    use the same allowance as a one-turn question — both turns are re-run together, on a
    fresh conversation, because half a retried conversation is not a retry. The final
    failure is re-raised untouched so the report names the real mismatch rather than
    "retried 3 times".
    """
    failure: AssertionError | None = None
    for _ in range(MAX_ATTEMPTS):
        try:
            attempt()
        except AssertionError as exc:
            failure = exc
        else:
            return
    assert failure is not None
    raise failure


def ask_until(base_url: str, question: str, check: Callable[[dict[str, Any]], None]) -> None:
    """Ask one question and assert against the answer, retrying the pair up to the limit."""

    def attempt() -> None:
        check(ask(base_url, question).result)

    until_it_holds(attempt)


def assert_grounded(result: dict[str, Any]) -> None:
    """Agent-design rule 1, re-derived from the wire: no figure without evidence."""
    invented = invented_digits(result)
    assert not invented, f"prose states figures the tool result does not contain: {invented}"


def assert_matches_csv(result: dict[str, Any], csv_rows: CsvRows) -> None:
    """Every row the service returned equals the same query run over the raw file."""
    expected = csv_expected_rows(csv_rows, result["explanation"])
    actual = {
        row["group"]: {metric: row[metric] for metric in result["explanation"]["metrics"]}
        for row in result["rows"]
    }
    assert actual == expected


def test_a_single_figure_question_is_a_stat_answered_from_the_tool(
    _stack: None, backend_base_url: str, csv_rows: CsvRows
) -> None:
    """Canonical 1: total orders. One figure, no split, and the figure is the CSV's."""

    def check(result: dict[str, Any]) -> None:
        assert result["display"] == "stat"
        assert result["explanation"]["metrics"] == ["order_count"]
        assert result["explanation"]["group_by"] == "none"
        assert result["data"] == {"metric": "order_count", "value": len(csv_rows)}
        assert_matches_csv(result, csv_rows)
        assert_grounded(result)

    ask_until(backend_base_url, "How many orders do we have in total?", check)


def test_a_dated_time_series_question_is_a_line_over_the_period_asked_for(
    _stack: None, backend_base_url: str, csv_rows: CsvRows
) -> None:
    """Canonical 2: late orders by week, Oct-Dec 2025.

    The dates are asserted by month rather than to the day: the customer named three
    months, and whether the model writes the 31st or the 30th of December is phrasing.
    Which *months* it counted is not.
    """

    def check(result: dict[str, Any]) -> None:
        explanation = result["explanation"]
        assert result["display"] == "line"
        assert explanation["metrics"] == ["delayed_orders"]
        assert explanation["group_by"] == "week"
        assert explanation["filters"]["date_from"].startswith("2025-10")
        assert explanation["filters"]["date_to"].startswith("2025-12")
        assert_matches_csv(result, csv_rows)
        assert_grounded(result)

    ask_until(backend_base_url, "Show delayed orders by week from October to December 2025", check)


def test_a_ranking_question_is_a_bar_sorted_worst_first(
    _stack: None, backend_base_url: str, csv_rows: CsvRows
) -> None:
    """Canonical 3: which carrier is worst. A comparison of peers, worst at the top."""

    def check(result: dict[str, Any]) -> None:
        explanation = result["explanation"]
        assert result["display"] == "bar"
        assert explanation["metrics"] == ["delay_rate"]
        assert explanation["group_by"] == "carrier"
        assert explanation["order"] == "value_desc"
        rates = [row["delay_rate"] for row in result["rows"] if row["delay_rate"] is not None]
        assert rates == sorted(rates, reverse=True)
        assert_matches_csv(result, csv_rows)
        assert_grounded(result)

    ask_until(backend_base_url, "Which carrier has the highest delay rate?", check)


def test_two_outcomes_compared_is_a_stacked_bar_of_two_counts(
    _stack: None, backend_base_url: str, csv_rows: CsvRows
) -> None:
    """Canonical 4: on time against late, per month.

    Two counts, never two rates — the tool's own validator rejects the rate pairing and
    the model corrects itself inside the turn, so a passing run also proves that loop.
    """

    def check(result: dict[str, Any]) -> None:
        explanation = result["explanation"]
        assert result["display"] == "stacked"
        assert set(explanation["metrics"]) == {"delivered_orders", "delayed_orders"}
        assert explanation["group_by"] == "month"
        assert_matches_csv(result, csv_rows)
        assert_grounded(result)

    ask_until(backend_base_url, "Compare on-time vs delayed orders per month", check)


@pytest.mark.parametrize(
    "question",
    ["What's the weather in Hong Kong?", "Write a poem about logistics"],
    ids=["weather", "poem"],
)
def test_an_out_of_domain_question_is_refused_as_a_result(
    _stack: None, backend_base_url: str, question: str
) -> None:
    """S2.4, refusal layer 1: the scope gate declines and states no figure.

    It arrives as a ``result``, not an ``error`` (D23): the service worked correctly when
    it declined, and an error frame would tell the interface to offer a retry for something
    that will never succeed.
    """
    answer = ask(backend_base_url, question)
    result = answer.result

    assert result["display"] == "unsupported"
    assert result["data"] is None
    assert result["rows"] == []
    assert result["explanation"] is None
    assert not numbers_in(result["answer"]), "a refusal must not state a figure"


def test_an_unsupported_split_is_refused_with_the_same_envelope(
    _stack: None, backend_base_url: str
) -> None:
    """S2.4, refusal layer 2: in domain, but the split does not exist.

    What this proves is that the *live* second layer reaches the same envelope. That the two
    envelopes are equal rather than merely alike is asserted structurally and without a key
    in ``tests/test_agent_rules.py``, which compares them field for field and gates the fact
    that only one module builds one at all. Two parallel five-line checks in a stack test
    would go on passing long after the shapes had drifted.
    """

    def check(result: dict[str, Any]) -> None:
        assert result["display"] == "unsupported"
        assert result["data"] is None
        assert result["rows"] == []
        assert result["explanation"] is None
        assert not numbers_in(result["answer"])

    ask_until(backend_base_url, "Delayed orders by destination city", check)


def test_an_ambiguous_question_asks_one_structured_follow_up(
    _stack: None, backend_base_url: str
) -> None:
    """S2.8: a missing parameter becomes a structured question, not a guess.

    ``missing_info`` is a closed enum on purpose. An unstated filter is not missing
    information — it means every order on record — so "which period do you mean?" must be
    unaskable, and the two members are what enforce that.
    """

    def check(result: dict[str, Any]) -> None:
        assert result["display"] == "follow_up"
        assert result["rows"] == []
        follow_up = result["follow_up"]
        assert follow_up is not None
        assert follow_up["missing_info"] in {"metric", "time_bucket"}
        assert not numbers_in(follow_up["question"]), "a follow-up may state no figure"

    ask_until(backend_base_url, "Show me the delayed orders trend", check)


def test_the_reply_to_a_follow_up_resolves_against_the_conversation(
    _stack: None, backend_base_url: str, csv_rows: CsvRows
) -> None:
    """S2.8 / rule 7: the turn ended, and the reply re-enters at the gate with context.

    "By week" is meaningless on its own and would look out of scope to a gate with no
    memory. Answering it correctly is the only proof that the checkpointer, the
    conversation id and rule 6's ten-message window are actually wired together.
    """

    def attempt() -> None:
        conversation = new_conversation_id()
        first: Answer = ask(backend_base_url, "Show me the delayed orders trend", conversation)
        assert first.result["display"] == "follow_up"

        result = ask(backend_base_url, "By week please", conversation).result

        assert result["display"] == "line"
        assert result["explanation"]["group_by"] == "week"
        assert_matches_csv(result, csv_rows)
        assert_grounded(result)

    until_it_holds(attempt)
