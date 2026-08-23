"""Composition root.

This is the one module allowed to know about every layer at once: its job is to wire
them together. The import-linter contracts deliberately do not cover it, because a
composition root that could not reach across layers could not compose anything. Every
*other* module stays inside its boundary.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI

from logistics_analytics.api.health import create_health_router
from logistics_analytics.config import Settings
from logistics_analytics.data.engine import create_database_engine
from logistics_analytics.data.health import DatabaseProbe, SqlAlchemyDatabaseProbe

logger = logging.getLogger(__name__)


def create_app(database_probe: DatabaseProbe) -> FastAPI:
    """Build the application around an injected database probe.

    Taking the probe as an argument is what makes the API testable without PostgreSQL
    and keeps this function free of environment lookups.
    """
    app = FastAPI(
        title="Logistics Analytics API",
        version="0.1.0",
        summary="Slice 0 skeleton - health only.",
    )
    app.include_router(create_health_router(database_probe))
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
    return create_app(SqlAlchemyDatabaseProbe(engine))
