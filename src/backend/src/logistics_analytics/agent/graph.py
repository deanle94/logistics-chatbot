"""The chat graph: three nodes, one conditional edge, one checkpointer.

This is the mermaid diagram in ``docs/agent-design.md`` compiled rather than described. The
gate is the edge, so a question that fails scope physically cannot reach the answering
side; both branches then converge on ``enforce``, which is why "both refusal paths emit the
identical envelope" is a property of the topology instead of two call sites that have to be
kept in step.

Two graphs are nested here. The outer one is ours. The inner one is LangChain's
``create_agent``, added straight in as a node (decision D6): it still owns the answering
tool loop, and it inherits the outer graph's checkpointer, so one saver keyed by
``thread_id`` covers the whole conversation.

Nothing in this module knows which provider it is talking to, which tools it was handed, or
what those tools reach — model, tools, dataset columns and checkpointer all arrive from the
composition root.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import ModelRequest, ModelResponse, wrap_model_call
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from logistics_analytics.agent.nodes import ChatState, create_classify_node, enforce
from logistics_analytics.agent.prompts import ANSWER_PROMPT

#: Node names. They are ours, so the SSE stage enum is translated from them rather than
#: being them — renaming a node must not change user-visible text (decision D23).
CLASSIFY_NODE = "classify"
ANSWER_NODE = "answer"
ENFORCE_NODE = "enforce"

#: The compiled conversation graph, as the API layer sees it.
ChatGraph = CompiledStateGraph[ChatState, Any, Any, Any]


@wrap_model_call
async def force_a_tool_on_the_first_call(
    request: ModelRequest[Any],
    handler: Callable[[ModelRequest[Any]], Awaitable[ModelResponse[Any]]],
) -> ModelResponse[Any]:
    """Make a tool call the only legal first move of a turn (agent-design rule 2).

    Forced only until a tool result exists, because rule 2 permits — and the answer needs —
    free prose *after* one. Forcing every call would forbid the closing sentence.

    "Since the last question" rather than "anywhere in the history": on a follow-up turn the
    checkpoint still holds the previous turn's tool result, and matching that would leave
    the new question unforced.
    """
    if not _tool_result_this_turn(request.messages):
        request = request.override(tool_choice="any")
    return await handler(request)


def create_chat_graph(
    model: BaseChatModel,
    tools: Sequence[BaseTool],
    dimensions: Sequence[str],
    checkpointer: BaseCheckpointSaver[Any],
) -> ChatGraph:
    """Wire the gate, the answering agent and the envelope into one compiled graph.

    Every dependency is a parameter (coding rule 5). That is not only testability here: it
    is the mechanism that keeps ``agent/`` from importing ``tools/``, and with it the whole
    chain into ``calculator/`` that import-linter contract 1 forbids.
    """
    answer = create_agent(
        model=model,
        tools=list(tools),
        system_prompt=ANSWER_PROMPT,
        middleware=[force_a_tool_on_the_first_call],
    )

    builder: StateGraph[ChatState, Any, Any, Any] = StateGraph(ChatState)
    builder.add_node(CLASSIFY_NODE, create_classify_node(model, tools, dimensions))
    builder.add_node(ANSWER_NODE, answer)
    builder.add_node(ENFORCE_NODE, enforce)
    builder.add_edge(START, CLASSIFY_NODE)
    builder.add_conditional_edges(CLASSIFY_NODE, _route, [ANSWER_NODE, ENFORCE_NODE])
    builder.add_edge(ANSWER_NODE, ENFORCE_NODE)
    builder.add_edge(ENFORCE_NODE, END)
    return builder.compile(checkpointer=checkpointer)


def _route(state: ChatState) -> str:
    """The gate itself. Out of domain skips the answering side and still lands on enforce."""
    return ANSWER_NODE if state["is_allowed"] else ENFORCE_NODE


def _tool_result_this_turn(messages: Sequence[Any]) -> bool:
    """Whether a tool has already answered since the customer's most recent question."""
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            return False
        if isinstance(message, ToolMessage):
            return True
    return False
