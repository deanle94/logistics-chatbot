"""S2.5 — ``POST /api/chat`` over SSE: the transport contract, not the answer's content.

The agent tests ask whether the model chose correctly. These ask whether the *stream* is
what decisions D20-D23 specify: the right content type, stages from the closed enum, then
exactly one result validating against its schema, then ``done``. A refusal is a result, a
fault is the only thing that is an error, and one answer fits inside 30 seconds.

The last test goes through nginx rather than the backend port, which is the only check that
a browser's ``POST /api/chat`` reaches this route at all — the proxy strips the prefix, and
SSE through a buffering proxy is a bug you cannot see from the backend side.

Marked ``stack``: run with ``pytest -m stack``.
"""

from __future__ import annotations

import httpx
import pytest

from tests.sse_reader import ANSWER_BUDGET_SECONDS, LEGAL_STAGES, Answer, ask

pytestmark = pytest.mark.stack

REQUEST_TIMEOUT_SECONDS = 30

#: One question whose answer the dashboard already publishes, so the two can be compared.
TOTAL_ORDERS_QUESTION = "How many orders do we have in total?"


@pytest.fixture(scope="module")
def _stack(compose_stack: None) -> None:
    """Alias so every test in this module implicitly requires the running stack."""
    return compose_stack


@pytest.fixture(scope="module")
def total_orders_answer(_stack: None, backend_base_url: str) -> Answer:
    """One real turn, reused by the frame-grammar assertions.

    Module-scoped because each of these checks is about a different property of the *same*
    stream, and asking the model five times to inspect five properties would cost five
    times as much and prove nothing more.
    """
    return ask(backend_base_url, TOTAL_ORDERS_QUESTION)


def test_the_route_answers_as_an_event_stream(total_orders_answer: Answer) -> None:
    """The content type is what makes a browser read this incrementally at all."""
    assert total_orders_answer.content_type.startswith("text/event-stream")


def test_the_frames_arrive_in_the_order_the_transport_specifies(
    total_orders_answer: Answer,
) -> None:
    """D20: ``stage``* then exactly one ``result`` then ``done``, and nothing else."""
    events = [frame.event for frame in total_orders_answer.frames]

    assert events.count("result") == 1
    assert events[-1] == "done"
    assert set(events) <= {"stage", "result", "done"}
    assert events.index("result") == len(events) - 2


def test_at_least_one_progress_stage_arrives_before_the_answer(
    total_orders_answer: Answer,
) -> None:
    """The interface has something honest to show while the model is still thinking."""
    events = [frame.event for frame in total_orders_answer.frames]

    assert events[0] == "stage"
    assert set(total_orders_answer.stages) <= LEGAL_STAGES
    assert total_orders_answer.stages[0] == "interpreting"


def test_the_result_frame_carries_every_field_the_interface_needs(
    total_orders_answer: Answer,
) -> None:
    """One envelope: answer, display, data, rows, explanation, follow-up, forecast."""
    result = total_orders_answer.result

    assert set(result) == {
        "answer",
        "display",
        "data",
        "rows",
        "explanation",
        "follow_up",
        "forecast",
    }
    assert result["answer"]
    assert result["display"] == "stat"
    assert set(result["explanation"]) == {
        "metrics",
        "group_by",
        "filters",
        "order",
        "row_count",
    }


def test_one_answer_fits_inside_the_budget(total_orders_answer: Answer) -> None:
    """S2.5's 30 s ceiling, measured end to end through the real provider."""
    assert total_orders_answer.seconds < ANSWER_BUDGET_SECONDS, (
        f"the answer took {total_orders_answer.seconds:.1f}s"
    )


def test_the_chat_and_the_kpi_route_agree_digit_for_digit(
    total_orders_answer: Answer, backend_base_url: str
) -> None:
    """The chat's oracle it gets for free: an endpoint already proved against the CSV.

    Two paths to one number — the dashboard's fixed spec and a sentence the model turned
    into parameters — and they run through the same calculator, so any disagreement here
    means the chat took a different route to the data than the dashboard did.
    """
    kpis = httpx.get(f"{backend_base_url}/kpis", timeout=REQUEST_TIMEOUT_SECONDS).json()

    assert total_orders_answer.result["data"] == {
        "metric": "order_count",
        "value": kpis["total_orders"]["value"],
    }


def test_a_refusal_arrives_as_a_result_and_never_as_an_error(
    _stack: None, backend_base_url: str
) -> None:
    """D23c: declining to invent a number is the service working, not failing."""
    answer = ask(backend_base_url, "What's the weather in Hong Kong?")
    events = [frame.event for frame in answer.frames]

    assert "error" not in events
    assert answer.result["display"] == "unsupported"


def test_a_malformed_request_is_rejected_before_any_model_call(
    _stack: None, backend_base_url: str
) -> None:
    """An empty question is a 422, not a paid round trip that ends in a refusal."""
    response = httpx.post(
        f"{backend_base_url}/chat",
        json={"question": "", "conversation_id": "x"},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )

    assert response.status_code == 422


def test_the_browser_facing_path_reaches_the_route_through_nginx(
    _stack: None, frontend_base_url: str
) -> None:
    """``/api/chat`` is what the bundle posts to; the proxy strips the prefix.

    Also the only place the proxy's buffering is exercised: with it on, every stage frame
    would arrive at the same instant as the answer and the progress display would be a lie.
    """
    answer = ask(f"{frontend_base_url}/api", TOTAL_ORDERS_QUESTION)

    assert answer.content_type.startswith("text/event-stream")
    assert answer.result["display"] == "stat"
