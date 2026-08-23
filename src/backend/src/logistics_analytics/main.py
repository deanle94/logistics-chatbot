"""Composition root.

This is the one module allowed to know about every layer at once: its job is to wire
them together. The import-linter contracts deliberately do not cover it, because a
composition root that could not reach across layers could not compose anything. Every
*other* module stays inside its boundary.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI

from logistics_analytics.api.dashboard import create_dashboard_router
from logistics_analytics.api.health import create_health_router
from logistics_analytics.api.kpis import create_kpis_router
from logistics_analytics.config import Settings
from logistics_analytics.data.engine import create_database_engine
from logistics_analytics.data.health import DatabaseProbe, SqlAlchemyDatabaseProbe
from logistics_analytics.data.repository import QueryExecutor, SqlAlchemyQueryExecutor

logger = logging.getLogger(__name__)


def create_app(database_probe: DatabaseProbe, execute_query: QueryExecutor) -> FastAPI:
    """Build the application around an injected probe and query executor.

    Both dependencies are arguments rather than module-level singletons: that is what
    makes every route testable without PostgreSQL and keeps this function free of
    environment lookups.

    The routes are mounted without an ``/api`` prefix on purpose. nginx proxies ``/api/``
    with a trailing slash, which strips the prefix, so the browser's ``/api/kpis`` arrives
    here as ``/kpis``. Prefixing the routers as well would produce ``/api/api/kpis``.
    """
    app = FastAPI(
        title="Logistics Analytics API",
        version="0.1.0",
        summary="Dashboard KPIs and the three fixed chart routes. No AI in this slice.",
    )
    app.include_router(create_health_router(database_probe))
    app.include_router(create_kpis_router(execute_query))
    app.include_router(create_dashboard_router(execute_query))
    return app


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
    logger.info("application configured")
    return create_app(
        database_probe=SqlAlchemyDatabaseProbe(engine),
        execute_query=SqlAlchemyQueryExecutor(engine),
    )
