"""Health endpoint.

The probe is injected rather than constructed here, which is what lets the route be
tested without a database and keeps this layer free of any database import.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Response, status
from pydantic import BaseModel

from logistics_analytics.data.health import DatabaseProbe


class HealthResponse(BaseModel):
    """The health payload.

    ``database`` is reported explicitly because a service that is running but cannot
    reach its data is not useful, and a bare "ok" would hide that.
    """

    status: Literal["ok", "degraded"]
    database: Literal["reachable", "unreachable"]


def create_health_router(database_probe: DatabaseProbe) -> APIRouter:
    """Build the health router around a given probe."""
    router = APIRouter(tags=["health"])

    @router.get(
        "/health",
        response_model=HealthResponse,
        summary="Liveness and database reachability",
    )
    def read_health(response: Response) -> HealthResponse:
        """Report service and database state.

        Returns 503 when the database is unreachable so that orchestrators and smoke
        tests treat a data-less service as down instead of healthy.
        """
        if not database_probe():
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return HealthResponse(status="degraded", database="unreachable")
        return HealthResponse(status="ok", database="reachable")

    return router
