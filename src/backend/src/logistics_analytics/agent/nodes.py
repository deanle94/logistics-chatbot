"""The two nodes this project writes itself: the scope gate, and the envelope.

Between them sits LangChain's ``create_agent``, which owns the answering tool loop. These
two exist because the behavioural contract in ``docs/agent-design.md`` cannot be delegated:
the gate decides whether the answering side runs at all, and ``enforce`` is the single
place an answer envelope is ever built, which is the only reason "both refusal paths emit
the identical envelope" can be a structural guarantee rather than a code-review promise.

This module imports LangChain and nothing from the rest of the package. The tools it
describes to the classifier arrive as an injected sequence, and the dataset's column names
arrive as injected strings, so no import edge exists from ``agent/`` into ``tools/``,
``calculator/`` or ``data/`` — import-linter contract 1 flags chains, not just direct
edges, so the injection is what keeps it green (agent-design rule 5).
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Sequence
from typing import Annotated, Any, Protocol, TypedDict, cast

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool, render_text_description
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from logistics_analytics.agent.prompts import CLASSIFY_PROMPT

logger = logging.getLogger(__name__)

#: Agent-design rule 6. A short reply ("last 3 months") looks out of scope on its own and
#: obviously in scope after the question it completes; ten messages is enough to see that
#: and few enough that the gate stays cheap.
CLASSIFY_CONTEXT_MESSAGES = 10

#: The display value both refusal layers emit (agent-design rule 4 / decision D23). This
#: module is the only place it is ever written, which ``tests/test_agent_rules.py`` gates.
DISPLAY_UNSUPPORTED = "unsupported"

#: The key an in-domain refusal tool puts its reason under. Spelled out here rather than
#: imported because ``agent/`` may not import ``tools/`` (rule 5); the tools layer names the
#: same constant next to the sentinel that writes it.
REFUSAL_REASON_KEY = "refusal_reason"

#: What the customer is told when the gate refused but named no reason.
DEFAULT_REJECT_REASON = (
    "I can't answer that one. Your orders don't record what that question needs, so "
    "anything I gave you would be made up rather than counted."
)

#: What the customer is told when the answering side produced no tool result at all.
NO_TOOL_RESULT_REASON = (
    "I couldn't turn that into something I can count. Try naming the figure you want, or "
    "the split you want it broken down by."
)

#: Every run of digits in a sentence, thousands separators included.
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


class ChatState(TypedDict):
    """The graph's state — the three fields ``docs/agent-design.md`` specifies, no more.

    ``messages`` is checkpointed under the request's conversation id, which is what makes a
    follow-up reply re-enter at the gate with the earlier turn still in view (rule 7).
    ``reject_reason`` is written by the gate and read only by ``enforce``; the answering
    side never sees it, so a refusal cannot leak into the prompt that writes an answer.
    """

    messages: Annotated[list[AnyMessage], add_messages]
    is_allowed: bool
    reject_reason: str


class ClassifyNode(Protocol):
    """The shape of the gate node, so the graph can name what it is handed.

    A Protocol rather than a bare ``Callable`` because LangGraph calls a node with a named
    ``state`` argument, which a positional-only callable type does not satisfy.
    """

    async def __call__(self, state: ChatState) -> dict[str, Any]:
        """Judge one turn and return the gate's two state fields."""
        ...


class Classification(BaseModel):
    """The gate's whole output. Domain scope, and the one sentence that explains a no."""

    is_allowed: bool = Field(
        description="True when the question is about the customer's own order data."
    )
    reject_reason: str = Field(
        default="",
        description="One short sentence naming what the orders do not hold. Empty when allowed.",
    )


def create_classify_node(
    model: BaseChatModel,
    tools: Sequence[BaseTool],
    dimensions: Sequence[str],
) -> ClassifyNode:
    """Build the scope gate around an injected model, tool list and column list.

    The prompt is rendered once, at wiring time, from the tools' own signatures and the
    dataset's own columns. Hard-coding either would let the prompt drift from the code the
    moment a tool or a column changed; rendering it means the two can only change together.

    Structured output rather than parsing prose: the provider validates the schema, so a
    malformed verdict is a provider error rather than a silently mis-read boolean.
    """
    prompt = CLASSIFY_PROMPT.format(
        dimensions=", ".join(dimensions),
        tools=render_text_description(list(tools)),
    )
    gate = model.with_structured_output(Classification)

    async def classify(state: ChatState) -> dict[str, Any]:
        """Judge domain scope only — never the parameters, never the answer."""
        verdict = cast(
            "Classification",
            await gate.ainvoke([SystemMessage(content=prompt), *_context(state["messages"])]),
        )
        return {"is_allowed": verdict.is_allowed, "reject_reason": verdict.reject_reason}

    return classify


def _context(messages: Sequence[AnyMessage]) -> list[AnyMessage]:
    """Rule 6's ten-message window, cut so that it always starts at a question.

    A plain slice is not safe here. Four messages accumulate per answered turn, so from the
    third turn onward the tenth-from-last lands between a tool call and its result — and a
    provider rejects a tool result whose call is not in the same request. Starting at the
    earliest question inside the window can only shorten the context, never split a pair,
    and the current question is itself one so the window is never empty.
    """
    window = list(messages[-CLASSIFY_CONTEXT_MESSAGES:])
    start = next(
        (index for index, message in enumerate(window) if isinstance(message, HumanMessage)),
        len(window) - 1,
    )
    return window[start:]


def enforce(state: ChatState) -> dict[str, Any]:
    """Build the one legal output of the turn. No model runs here.

    Both branches of the graph end at this node, which is what makes the two refusal layers
    emit byte-identical envelopes instead of two envelopes that merely look alike.

    Read backwards from the transcript: an in-domain refusal arrives as a bare reason and is
    turned into the envelope *here*, by the same call the scope gate makes three lines
    above, so rule 4's "identical envelope" is one dict literal rather than two that have to
    be kept in step; a follow-up sentinel already carries its own answer, so its envelope
    wins and any trailing prose is discarded; a query result is checked against
    rule 1 — every digit in the prose must appear in the tool's own JSON — and a sentence
    that fails falls back to a digit-free one built from the tool result. A drifting model
    therefore degrades to a duller answer, never to a wrong number.

    "No tool was called" is handled but should be unreachable: tool choice is forced on the
    first model call, so bare prose is not a legal first move at the provider.
    """
    if not state.get("is_allowed", False):
        return _final(state, _unsupported(state.get("reject_reason") or DEFAULT_REJECT_REASON))

    result = _last_tool_result(state["messages"])
    if result is None:
        logger.warning("answer node produced no tool result; refusing rather than guessing")
        return _final(state, _unsupported(NO_TOOL_RESULT_REASON))

    payload = _parsed(result)
    if payload is None:
        logger.warning("tool result was not the expected JSON envelope")
        return _final(state, _unsupported(NO_TOOL_RESULT_REASON))

    reason = payload.get(REFUSAL_REASON_KEY)
    if isinstance(reason, str) and reason:
        return _final(state, _unsupported(reason))

    envelope = {"follow_up": None, **payload}
    if envelope.get("answer"):
        return _final(state, envelope)

    prose = _trailing_prose(state["messages"])
    grounded = prose if prose and _digits_are_grounded(prose, str(result.content)) else ""
    if prose and not grounded:
        logger.warning("prose stated a figure the tool result does not contain; falling back")
    envelope["answer"] = grounded or _plain_answer(payload)
    return _final(state, envelope)


def _unsupported(answer: str) -> dict[str, Any]:
    """The refusal envelope. One shape, whichever layer refused (rule 4)."""
    return {
        "answer": answer,
        "display": DISPLAY_UNSUPPORTED,
        "data": None,
        "rows": [],
        "explanation": None,
        "follow_up": None,
    }


def _final(state: ChatState, envelope: dict[str, Any]) -> dict[str, Any]:
    """Append the answer to the transcript, carrying the envelope with it.

    The envelope rides on the message rather than on a fourth state field because the
    design fixes the state at three fields, and because the answer and the envelope that
    explains it should not be able to drift apart in the checkpoint.

    Re-using the id of a trailing prose message makes ``add_messages`` replace it rather
    than append, so the next turn's ten-message window sees the enforced answer once
    instead of the model's draft and the final text side by side.
    """
    last = state["messages"][-1]
    reuse = isinstance(last, AIMessage) and not last.tool_calls
    message = AIMessage(
        id=last.id if reuse else None,
        content=str(envelope["answer"]),
        additional_kwargs={"envelope": envelope},
    )
    return {"messages": [message]}


def _last_tool_result(messages: Sequence[AnyMessage]) -> ToolMessage | None:
    """The tool result from this turn only — anything before the question does not count."""
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            return None
        if isinstance(message, ToolMessage):
            return message
    return None


def _parsed(result: ToolMessage) -> dict[str, Any] | None:
    """The tool's JSON envelope, or ``None`` when the tool raised instead of answering."""
    try:
        payload = json.loads(str(result.content))
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def _trailing_prose(messages: Sequence[AnyMessage]) -> str:
    """The sentences the model wrote after the tool answered, if it wrote any."""
    last = messages[-1]
    return str(last.text) if isinstance(last, AIMessage) and not last.tool_calls else ""


def _digits_are_grounded(prose: str, tool_content: str) -> bool:
    """Rule 1: no figure in the prose that is absent from the bytes the model was shown.

    Compared as numbers rather than as text so that the thousands separators the prompt
    asks for do not read as invented digits — ``1,234`` and ``1234`` are the same figure —
    and so ``28.6`` matches whether the tool wrote it with or without a trailing zero.
    """
    allowed = _numbers_in(tool_content)
    return _numbers_in(prose) <= allowed


def _numbers_in(text: str) -> set[float]:
    """Every figure a reader would see in the text, normalised for comparison."""
    return {float(token.replace(",", "")) for token in _NUMBER.findall(text)}


def _plain_answer(payload: dict[str, Any]) -> str:
    """A sentence with no figure in it, built from the question the tool answered.

    The deliberate fallback of the digit check: the chart and the table below it already
    carry every number, so an answer that only says what was counted is still a true answer.
    """
    explanation = payload.get("explanation") or {}
    metrics = ", ".join(str(name).replace("_", " ") for name in explanation.get("metrics", []))
    group_by = str(explanation.get("group_by", "none")).replace("_", " ")
    if not metrics:
        return "Here is what your orders show. The table below carries the figures."
    if group_by == "none":
        return f"Here is the {metrics} counted from your orders, in the figure below."
    return f"Here is the {metrics}, split by {group_by}. Every figure is in the table below."
