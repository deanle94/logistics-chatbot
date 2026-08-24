"""Composition root.

This is the one module allowed to know about every layer at once: its job is to wire
them together. The import-linter contracts deliberately do not cover it, because a
composition root that could not reach across layers could not compose anything. Every
*other* module stays inside its boundary.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.memory import InMemorySaver

from logistics_analytics.agent.graph import ChatGraph, create_chat_graph
from logistics_analytics.api.chat import create_chat_router
from logistics_analytics.api.dashboard import create_dashboard_router
from logistics_analytics.api.health import create_health_router
from logistics_analytics.api.kpis import create_kpis_router
from logistics_analytics.config import LlmSettings, Settings
from logistics_analytics.data.engine import create_database_engine
from logistics_analytics.data.health import DatabaseProbe, SqlAlchemyDatabaseProbe
from logistics_analytics.data.models import Order
from logistics_analytics.data.repository import QueryExecutor, SqlAlchemyQueryExecutor
from logistics_analytics.tools.query_tool import build_agent_tools

logger = logging.getLogger(__name__)

#: Ceiling on one answer. Three sentences and a tool call need far less; the cap is there
#: so a drifting model cannot run up a bill or blow the route's 30 s budget.
ANSWER_MAX_TOKENS = 1024


def create_app(
    database_probe: DatabaseProbe,
    execute_query: QueryExecutor,
    chat_graph: ChatGraph | None = None,
) -> FastAPI:
    """Build the application around an injected probe, query executor and chat graph.

    Every dependency is an argument rather than a module-level singleton: that is what
    makes every route testable without PostgreSQL and keeps this function free of
    environment lookups.

    ``chat_graph`` is optional because it is the only dependency that needs a funded API
    key. Omitting it mounts the dashboard without the chat route, which is what lets the
    static gate build and exercise the real application offline.

    The routes are mounted without an ``/api`` prefix on purpose. nginx proxies ``/api/``
    with a trailing slash, which strips the prefix, so the browser's ``/api/kpis`` arrives
    here as ``/kpis``. Prefixing the routers as well would produce ``/api/api/kpis``.
    """
    app = FastAPI(
        title="Logistics Analytics API",
        version="0.2.0",
        summary="Dashboard KPIs, the three fixed chart routes, and the chat agent.",
    )
    app.include_router(create_health_router(database_probe))
    app.include_router(create_kpis_router(execute_query))
    app.include_router(create_dashboard_router(execute_query))
    if chat_graph is not None:
        app.include_router(create_chat_router(chat_graph))
    return app


def create_llm(settings: LlmSettings) -> BaseChatModel:
    """Build the chat model. This is the only place in the project a provider is named.

    Named by configuration, in fact: ``init_chat_model`` parses ``LLM_MODEL``'s
    ``provider:model`` form, so swapping provider is one ``.env`` line plus the matching
    ``langchain-*`` dependency, and no module below this one learns what it got.

    **The abstraction hides the interface, not the capabilities.** This design leans on
    forced tool choice and provider-side structured output; a provider that does not honour
    both will not fail at startup, it will fail at the first question. A swap is one line,
    and trusting it costs a run of ``pytest -m stack``.

    ``temperature=0`` because the same question should not route two ways between a
    recorded gate and a reviewer's rerun.
    """
    return init_chat_model(
        settings.llm_model,
        temperature=0,
        timeout=settings.llm_timeout_seconds,
        max_tokens=ANSWER_MAX_TOKENS,
        api_key=settings.anthropic_api_key,
    )


def create_default_chat_graph(execute_query: QueryExecutor) -> ChatGraph:
    """Assemble the chat graph from environment configuration.

    The three things ``agent/`` refuses to import arrive here instead: the tools built over
    the query executor, the dataset's column names taken from the ORM model, and the
    checkpointer. That injection is the whole reason import-linter contract 1 stays green —
    a single ``agent`` → ``tools`` import would drag ``calculator`` in behind it.

    ``InMemorySaver`` rather than a database-backed checkpointer because the application
    connects as a read-only role (D4) and cannot write a conversation anywhere. A restart
    therefore forgets every conversation, which is the cost this slice accepted.
    """
    # pydantic-settings populates this from the environment at runtime; mypy cannot
    # see that, so the constructor looks like it is missing arguments.
    settings = LlmSettings()  # type: ignore[call-arg]
    return create_chat_graph(
        model=create_llm(settings),
        tools=build_agent_tools(execute_query),
        dimensions=[column.name for column in Order.__table__.columns],
        checkpointer=InMemorySaver(),
    )


def create_default_app() -> FastAPI:
    """Build the application from environment configuration.

    This is the uvicorn entry point (``--factory``). It fails at startup if the
    configuration is incomplete, which is the intended behaviour.
    """
    logging.basicConfig(level=logging.INFO)
    # pydantic-settings populates this from the environment at runtime; mypy cannot
    # see that, so the constructor looks like it is missing an argument.
    settings = Settings()  # type: ignore[call-arg]
    engine = create_database_engine(settings.database_url)
    execute_query = SqlAlchemyQueryExecutor(engine)
    logger.info("application configured")
    return create_app(
        database_probe=SqlAlchemyDatabaseProbe(engine),
        execute_query=execute_query,
        chat_graph=create_default_chat_graph(execute_query),
    )
