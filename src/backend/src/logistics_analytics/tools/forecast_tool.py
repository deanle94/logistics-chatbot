"""S3.2 — the forecast tool: the agent's 4th legal output. It computes nothing.

The tool validates ``{sku, horizon}``, announces the ``forecasting`` stage, calls the
calculator, and shapes the wire envelope — the same seam ``query_tool`` is, pointed at the
other calculator entry point. Every number it hands back was computed in
``calculator/forecast.py``; every history row went through the untouched S1.2 engine.

Two shapes leave here and both are decided elsewhere. The answer is the full envelope with
``display: "forecast_line"`` (architecture "Chat path (forecast)"): history and prediction
in ONE ``rows`` array under two value keys, plus the typed ``forecast`` block the card
renders. The refusal is the single-key reason JSON, identical in shape to
``_refuse_unsupported``'s, so ``agent/nodes.py`` stays the only module that ever builds an
``unsupported`` envelope (agent-design rule 4).
"""

from __future__ import annotations

import json
import logging

from langchain_core.tools import BaseTool, StructuredTool
from langgraph.config import get_stream_writer

from logistics_analytics.calculator.forecast import InsufficientHistoryError, run_forecast
from logistics_analytics.calculator.query import ExecuteQuery
from logistics_analytics.tools.schemas import REFUSAL_REASON_KEY, ForecastToolParams

logger = logging.getLogger(__name__)

#: The stage the tool announces while the projection runs (spec review Q3; D23b's enum is
#: hand-extended with it in the four places that spell the enum out).
FORECASTING_STAGE = "forecasting"


def run_forecast_tool(execute: ExecuteQuery, params: ForecastToolParams) -> str:
    """Answer one validated forecast request as the JSON string the model reads.

    A string for the same reason ``QueryAnswer.as_tool_content`` returns one: the enforce
    node checks the model's prose against these exact bytes, so "the model saw this
    number" is a fact rather than an inference. Insufficient history is a refusal, not a
    fault (D23) — the reason travels back under the one refusal key and the agent's
    enforce node builds the envelope.
    """
    _announce(FORECASTING_STAGE)
    try:
        result = run_forecast(execute, sku=params.sku, horizon=params.horizon)
    except InsufficientHistoryError as refusal:
        return json.dumps({REFUSAL_REASON_KEY: refusal.reason})

    rows = [
        *({"group": month, "quantity": value} for month, value in result.history),
        *({"group": month, "forecast": value} for month, value in result.forecast),
    ]
    return json.dumps(
        {
            "display": "forecast_line",
            "data": None,
            "rows": rows,
            "explanation": {
                "metrics": ["quantity"],
                "group_by": "month",
                "filters": {"sku": result.sku},
                "order": "group",
                "row_count": len(result.history),
            },
            "forecast": {
                "sku": result.sku,
                "horizon": result.horizon,
                "window": result.window,
                "total": result.total,
                "recommended_stock": result.recommended_stock,
                "buffer_pct": result.buffer_pct,
                "methodology": result.methodology,
            },
        }
    )


def build_forecast_tool(execute: ExecuteQuery) -> BaseTool:
    """The forecast as a tool, appended to ``build_agent_tools``'s list by ``query_tool``."""

    def forecast(**kwargs: object) -> str:
        """Validate the model's parameters, run them, and hand back the JSON it will read."""
        return run_forecast_tool(execute, ForecastToolParams(**kwargs))  # type: ignore[arg-type]

    return StructuredTool.from_function(
        func=forecast,
        name="forecast",
        description=(
            "Predict future monthly demand for one product and recommend how much stock "
            "to hold, computed from the order history. Use it whenever the customer asks "
            "to predict or forecast demand, plan inventory, or decide how much stock to "
            "keep - such questions are always about these orders and always in scope, "
            "with or without a product code. When none is named, ask a follow-up for the "
            "product code; never refuse for that."
        ),
        args_schema=ForecastToolParams,
    )


def _announce(stage: str) -> None:
    """Emit one custom stream event, or do nothing when no graph runtime is active.

    ``get_stream_writer`` reads LangGraph's runtime off a contextvar, so inside a graph
    run the event surfaces on the ``custom`` stream and ``api/chat.py`` turns it into a
    stage frame. A bare call — every unit test — has no runtime and raises instead; the
    stage is advisory (D23b), so silence is the correct behaviour there, not a fault.
    """
    try:
        writer = get_stream_writer()
    except (RuntimeError, KeyError):
        logger.debug("no graph runtime active; stage %s not announced", stage)
        return
    writer({"stage": stage})
