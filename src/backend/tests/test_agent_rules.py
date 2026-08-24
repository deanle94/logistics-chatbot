"""Agent-design rules 2 and 4, asserted without a model and without a stack.

Both rules are *structural* claims, and both were until now only visible through the live
model: the stack gates saw a tool call arrive before any prose, and saw two refusals that
looked alike. Neither is proof. A model that happened to behave says nothing about what the
code would have permitted, and two five-line checks in two tests are exactly how "identical
envelope" quietly becomes "similar envelope".

So these run in the static gate, cost nothing, and need no key:

* **Rule 2** — a tool call is the only legal first move of a turn. Asserted against the
  middleware that forces it, including the case the reverse scan in
  ``_tool_result_this_turn`` exists for: a *new* question asked after an earlier turn's
  tool result is still in the checkpoint.
* **Rule 4** — both refusal layers emit the identical envelope. Asserted twice over: once
  by running ``enforce`` down each branch and comparing the two envelopes field for field,
  and once by reading the source of every module to prove only one of them writes the
  ``unsupported`` display at all.
"""

from __future__ import annotations

import ast
import asyncio
import json
from pathlib import Path
from typing import Any

from langchain.agents.middleware import ModelRequest, ModelResponse
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage

from logistics_analytics.agent.graph import force_a_tool_on_the_first_call
from logistics_analytics.agent.nodes import (
    DISPLAY_UNSUPPORTED,
    REFUSAL_REASON_KEY,
    ChatState,
    enforce,
)
from tests.conftest import PACKAGE_ROOT

#: Never called: every test here replaces the model with a stub handler. It exists because
#: ``ModelRequest`` requires one, not because anything asks it a question.
UNUSED_MODEL = GenericFakeChatModel(messages=iter([AIMessage(content="")]))

#: The provider-level value that means "you must call one of the tools".
FORCED = "any"

#: The one module allowed to build the refusal envelope.
ENVELOPE_MODULE = "agent/nodes.py"


# --------------------------------------------------------------------------------------
# Rule 2 - free text is legal only after a tool result.
# --------------------------------------------------------------------------------------


def _tool_choice_the_model_is_given(messages: list[AnyMessage]) -> object:
    """Run the middleware over a transcript and report what reached the provider.

    The handler stands in for the model call, so what is asserted is the request the
    provider *would* have received — which is where the rule is actually enforced.
    """
    seen: list[object] = []

    async def handler(request: ModelRequest[Any]) -> ModelResponse[Any]:
        seen.append(request.tool_choice)
        return ModelResponse(result=[AIMessage(content="")])

    request: ModelRequest[Any] = ModelRequest(model=UNUSED_MODEL, messages=messages, tools=[])
    asyncio.run(force_a_tool_on_the_first_call.awrap_model_call(request, handler))
    return seen[0]


def _tool_call() -> AIMessage:
    """An assistant turn that called the query tool and is waiting for the result."""
    return AIMessage(
        content="",
        tool_calls=[{"name": "query", "args": {"metrics": ["order_count"]}, "id": "call-1"}],
    )


def _tool_result() -> ToolMessage:
    """The query tool answering, in the JSON shape the model is handed."""
    return ToolMessage(content=json.dumps({"rows": []}), tool_call_id="call-1")


def test_the_first_move_of_a_turn_must_be_a_tool_call() -> None:
    """A bare question reaches the provider with tool choice forced, so prose is illegal."""
    assert _tool_choice_the_model_is_given([HumanMessage(content="How many orders?")]) == FORCED


def test_the_closing_prose_after_a_tool_result_is_left_free() -> None:
    """Rule 2 permits free text *after* a tool result, and the answer needs it.

    Forcing every call would forbid the closing sentence entirely, so the answer would be
    a second tool call forever.
    """
    messages: list[AnyMessage] = [
        HumanMessage(content="How many orders?"),
        _tool_call(),
        _tool_result(),
    ]

    assert _tool_choice_the_model_is_given(messages) is None


def test_a_fresh_question_is_forced_again_even_with_an_earlier_tool_result_in_view() -> None:
    """The bug the reverse scan exists to prevent, and the only way to see it.

    From the second turn onward the checkpoint still holds the previous turn's tool result.
    Matching that anywhere in the history would leave every follow-up question unforced —
    free prose as the first move, which is precisely rule 2's failure mode.
    """
    messages: list[AnyMessage] = [
        HumanMessage(content="How many orders?"),
        _tool_result(),
        HumanMessage(content="And by carrier?"),
    ]

    assert _tool_choice_the_model_is_given(messages) == FORCED


# --------------------------------------------------------------------------------------
# Rule 4 - both refusal paths emit the identical envelope.
# --------------------------------------------------------------------------------------


def _envelope_of(update: dict[str, Any]) -> dict[str, Any]:
    """The envelope ``enforce`` attached to the message it appended."""
    message = update["messages"][0]
    envelope = message.additional_kwargs["envelope"]
    assert isinstance(envelope, dict)
    return envelope


def test_both_refusal_layers_emit_the_identical_envelope() -> None:
    """Rule 4 as an equality, not as two parallel checks that can drift apart.

    The two branches are genuinely different journeys — the gate never runs the answering
    side, the sentinel runs it and calls a tool — so the only thing that can make their
    envelopes equal is that one dict literal builds both.
    """
    out_of_domain: ChatState = {
        "messages": [HumanMessage(content="What's the weather in Hong Kong?")],
        "is_allowed": False,
        "reject_reason": "Your orders don't record the weather.",
    }
    unsupported_params: ChatState = {
        "messages": [
            HumanMessage(content="Delayed orders by destination city"),
            _tool_call(),
            ToolMessage(
                content=json.dumps({REFUSAL_REASON_KEY: "There is no city on an order."}),
                tool_call_id="call-1",
            ),
        ],
        "is_allowed": True,
        "reject_reason": "",
    }

    gate = _envelope_of(enforce(out_of_domain))
    sentinel = _envelope_of(enforce(unsupported_params))

    assert gate["display"] == DISPLAY_UNSUPPORTED
    assert gate["answer"] != sentinel["answer"], "the two layers explain different things"
    assert {name: value for name, value in gate.items() if name != "answer"} == {
        name: value for name, value in sentinel.items() if name != "answer"
    }


def _is_wire_contract(node: ast.AST) -> bool:
    """Whether a node is a ``Literal[...]`` annotation rather than a value being built.

    ``api/chat.py`` names every display value in the result frame's schema. That declares
    what may cross the wire; it does not build an answer, and a guard that could not tell
    the two apart would forbid the contract from naming its own vocabulary.
    """
    if not isinstance(node, ast.Subscript):
        return False
    target = node.value
    name = target.id if isinstance(target, ast.Name) else getattr(target, "attr", "")
    return name == "Literal"


def _writes(node: ast.AST, value: str) -> bool:
    """Whether the source builds ``value`` as a string somewhere outside an annotation."""
    if isinstance(node, ast.Constant):
        return node.value == value
    if _is_wire_contract(node):
        return False
    return any(_writes(child, value) for child in ast.iter_child_nodes(node))


def _modules_writing(value: str) -> set[str]:
    """Every module in the package that writes ``value`` as a string."""
    return {
        path.relative_to(PACKAGE_ROOT).as_posix()
        for path in sorted(PACKAGE_ROOT.rglob("*.py"))
        if _writes(ast.parse(Path(path).read_text(encoding="utf-8")), value)
    }


def test_only_one_module_writes_the_unsupported_display() -> None:
    """A second envelope builder is a static-gate failure, not a review comment.

    The equality above proves today's two branches agree. This proves they cannot stop
    agreeing: the moment a tool, a route or a node starts assembling its own ``unsupported``
    answer, there are two homes for the refusal shape again and this fails.
    """
    assert _modules_writing(DISPLAY_UNSUPPORTED) == {ENVELOPE_MODULE}
