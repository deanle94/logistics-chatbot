"""The one SSE frame reader every Slice 2 gate uses.

Every chat criterion — S2.3, S2.4, S2.5, S2.7 and the eval runner — asks the same two
questions of the same stream: did the frames arrive in the order D20 specifies, and what
was in the single result frame. Parsing that in five places would let five gates disagree
about what a well-formed answer looks like, so it is parsed once here and the grammar is
asserted on every read.

The grammar itself is the contract: ``stage``* then exactly one ``result`` then ``done``,
or ``stage``* then ``error`` then ``done``. A refusal is a *result*, never an error (D23),
so a gate that accepts an error frame for "what's the weather" would be passing the wrong
thing.

Nothing here skips. When the provider is unreachable or unauthorised the service emits an
``error`` frame and :func:`result_of` fails the test — a skip that reads as green is what
decision D19 rejected.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass
from typing import Any

import httpx

#: The closed stage enum of decision D23b, hand-extended with ``forecasting`` for Slice 3
#: (spec review Q3). Anything else in a stage frame is a contract break, not a new feature.
LEGAL_STAGES: frozenset[str] = frozenset({"interpreting", "querying", "forecasting", "composing"})

#: S2.5's budget for one answer, end to end, through the real model.
ANSWER_BUDGET_SECONDS = 30.0


@dataclass(frozen=True)
class Frame:
    """One Server-Sent Event: its type and its decoded JSON payload."""

    event: str
    data: dict[str, Any]


@dataclass(frozen=True)
class Answer:
    """One chat turn: the frames it produced, and how long the whole thing took."""

    frames: tuple[Frame, ...]
    seconds: float
    content_type: str

    @property
    def stages(self) -> tuple[str, ...]:
        """The progress stages, in the order they arrived."""
        return tuple(str(frame.data["stage"]) for frame in self.frames if frame.event == "stage")

    @property
    def result(self) -> dict[str, Any]:
        """The single result frame's payload, asserting the grammar on the way through."""
        return result_of(self)


def new_conversation_id() -> str:
    """A fresh conversation, so one test's history can never leak into another's."""
    return str(uuid.uuid4())


def ask(
    base_url: str,
    question: str,
    conversation_id: str | None = None,
    timeout: float = ANSWER_BUDGET_SECONDS * 2,
) -> Answer:
    """Ask one question over ``POST /chat`` and read the whole stream.

    The timeout is deliberately looser than the budget the tests then assert: a test that
    times out reports a connection error, while one that measures the elapsed time reports
    "the answer took 41 s", which is the failure the reviewer actually needs to see.
    """
    started = time.monotonic()
    with (
        httpx.Client(timeout=timeout) as client,
        client.stream(
            "POST",
            f"{base_url}/chat",
            json={
                "question": question,
                "conversation_id": conversation_id or new_conversation_id(),
            },
        ) as response,
    ):
        assert response.status_code == 200, f"POST /chat -> {response.status_code}"
        body = "".join(response.iter_text())
        content_type = response.headers.get("content-type", "")

    return Answer(
        frames=tuple(read_frames(body)),
        seconds=time.monotonic() - started,
        content_type=content_type,
    )


def read_frames(body: str) -> list[Frame]:
    """Split a raw SSE body into frames.

    Hand-rolled rather than adding an SSE client dependency: the wire format is two
    prefixes and a blank-line delimiter, and a parser we can read is worth more here than
    one we have to trust.
    """
    frames: list[Frame] = []
    for block in body.split("\n\n"):
        lines = [line for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        fields = {
            name.strip(): value.strip()
            for name, _, value in (line.partition(":") for line in lines)
        }
        event, payload = fields.get("event", ""), fields.get("data", "")
        assert event, f"a frame arrived with no event type: {block!r}"
        frames.append(Frame(event=event, data=json.loads(payload) if payload else {}))
    return frames


def result_of(answer: Answer) -> dict[str, Any]:
    """The single result frame, after checking the stream is well formed.

    An ``error`` frame fails here with the service's own message rather than with a
    ``KeyError`` three assertions later, which matters most when the failure is "no API
    key" and the reviewer needs to be told exactly that.
    """
    events = [frame.event for frame in answer.frames]
    errors = [frame.data.get("message") for frame in answer.frames if frame.event == "error"]
    assert not errors, f"the service reported a fault instead of an answer: {errors}"

    results = [frame.data for frame in answer.frames if frame.event == "result"]
    assert len(results) == 1, f"expected exactly one result frame, got {events}"
    assert events[-1] == "done", f"the stream must end with done, got {events}"
    assert events.index("result") == len(events) - 2, (
        f"result must be the last frame but one: {events}"
    )

    unknown = set(answer.stages) - LEGAL_STAGES
    assert not unknown, f"stage frames outside the closed enum: {unknown}"
    return results[0]


def numbers_in(text: str) -> set[float]:
    """Every figure a reader would see in the text, normalised for comparison.

    The same normalisation the service applies: thousands separators are stripped, so a
    prose ``1,234`` and a tool result's ``1234`` are recognised as one figure rather than
    reported as an invented one.
    """
    return {float(token.replace(",", "")) for token in re.findall(r"\d[\d,]*(?:\.\d+)?", text)}


def invented_digits(result: dict[str, Any]) -> set[float]:
    """Figures the answer states that its own evidence does not contain (rule 1).

    Checked against the result frame's data, rows and explanation — which is exactly what
    the tool handed the model — so this is the acceptance criterion re-derived from the
    wire rather than a re-run of the service's own check.
    """
    evidence = json.dumps(
        {
            "data": result.get("data"),
            "rows": result.get("rows"),
            "explanation": result.get("explanation"),
            "forecast": result.get("forecast"),
        }
    )
    return numbers_in(str(result.get("answer", ""))) - numbers_in(evidence)
