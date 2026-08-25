"""S3.2 / S3.4 — the forecast tool: envelope shape, validation, refusal. No model, no DB.

Same division of labour as ``test_query_tool.py``: this file is about shape, not
arithmetic. The numbers the envelope carries are proved in ``test_forecast_calculator.py``
against a hand oracle, and against the live database under ``pytest -m stack``.

What is asserted here is the contract the rest of the system leans on: the two value keys
in one ``rows`` array (D2), the typed ``forecast`` block (D1), the echoed explanation the
CSV oracle re-derives history from, the horizon bounds, and that a sparse or unknown SKU
hands back the same refusal-reason JSON the refusal sentinel does — so ``enforce`` turns
both into the one ``unsupported`` envelope.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import ValidationError

from logistics_analytics.tools.forecast_tool import run_forecast_tool
from logistics_analytics.tools.query_tool import build_agent_tools
from logistics_analytics.tools.schemas import (
    REFUSAL_REASON_KEY,
    ForecastToolParams,
    MissingInfo,
)
from tests.test_forecast_calculator import FakeRow, executor_returning

#: PENCIL-0213's real monthly series, so every figure below is checkable by hand.
HISTORY_ROWS = (FakeRow("2025-06", 1), FakeRow("2025-08", 5), FakeRow("2025-09", 5))


def test_the_envelope_carries_history_and_forecast_in_one_rows_array() -> None:
    """D2: history rows keep the S1.2 shape, forecast rows use the second value key."""
    payload = json.loads(
        run_forecast_tool(executor_returning(*HISTORY_ROWS), ForecastToolParams(sku="PENCIL-0213"))
    )

    assert payload["display"] == "forecast_line"
    assert payload["data"] is None
    assert payload["rows"][:3] == [
        {"group": "2025-06", "quantity": 1},
        {"group": "2025-08", "quantity": 5},
        {"group": "2025-09", "quantity": 5},
    ]
    assert payload["rows"][3:] == [
        {"group": "2025-10", "forecast": 4},
        {"group": "2025-11", "forecast": 5},
        {"group": "2025-12", "forecast": 5},
        {"group": "2026-01", "forecast": 5},
    ]


def test_the_explanation_echoes_the_history_query_field_for_field() -> None:
    """The CSV oracle re-derives history from these parameters, so they must be exact."""
    payload = json.loads(
        run_forecast_tool(executor_returning(*HISTORY_ROWS), ForecastToolParams(sku="PENCIL-0213"))
    )

    assert payload["explanation"] == {
        "metrics": ["quantity"],
        "group_by": "month",
        "filters": {"sku": "PENCIL-0213"},
        "order": "group",
        "row_count": 3,
    }


def test_the_typed_forecast_block_carries_all_four_parts() -> None:
    """D1: the recommendation and methodology travel typed, never fished out of prose."""
    payload = json.loads(
        run_forecast_tool(executor_returning(*HISTORY_ROWS), ForecastToolParams(sku="PENCIL-0213"))
    )
    forecast = payload["forecast"]

    assert forecast["sku"] == "PENCIL-0213"
    assert forecast["horizon"] == 4
    assert forecast["window"] == 3
    assert forecast["total"] == 19
    assert forecast["recommended_stock"] == 22
    assert forecast["buffer_pct"] == 15.0
    assert "average" in forecast["methodology"]


def test_the_horizon_defaults_to_four_and_is_bounded() -> None:
    """Horizon 1..12, default 4 — the model cannot ask for a two-year projection."""
    assert ForecastToolParams(sku="PENCIL-0213").horizon == 4
    assert ForecastToolParams(sku="PENCIL-0213", horizon=12).horizon == 12

    with pytest.raises(ValidationError):
        ForecastToolParams(sku="PENCIL-0213", horizon=0)
    with pytest.raises(ValidationError):
        ForecastToolParams(sku="PENCIL-0213", horizon=13)


def test_the_sku_is_required_and_pattern_checked() -> None:
    """No AI-generated string reaches the query builder unvalidated."""
    with pytest.raises(ValidationError):
        ForecastToolParams()  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        ForecastToolParams(sku="../etc/passwd")
    with pytest.raises(ValidationError):
        ForecastToolParams(sku="PENCIL-0213", metric="quantity")  # type: ignore[call-arg]


def test_a_follow_up_may_now_ask_for_the_sku() -> None:
    """A forecast without a product code is genuinely missing one askable thing."""
    assert MissingInfo.SKU.value == "sku"


def test_a_sparse_sku_hands_back_the_refusal_reason_json() -> None:
    """S3.4: the tool reports only *why*, exactly like ``_refuse_unsupported`` does.

    Same single-key JSON, so ``agent/nodes.py`` builds the one ``unsupported`` envelope
    for it — the tool itself never writes a display value.
    """
    payload = json.loads(
        run_forecast_tool(
            executor_returning(FakeRow("2025-10", 2)), ForecastToolParams(sku="PAPER-0197")
        )
    )

    assert set(payload) == {REFUSAL_REASON_KEY}
    assert not any(character.isdigit() for character in payload[REFUSAL_REASON_KEY])


def test_an_unknown_sku_hands_back_the_same_refusal_shape() -> None:
    """Zero months of history is the sparse case, not an error path of its own."""
    payload = json.loads(
        run_forecast_tool(executor_returning(), ForecastToolParams(sku="SKU-9999"))
    )

    assert set(payload) == {REFUSAL_REASON_KEY}


def test_build_agent_tools_hands_the_agent_exactly_four_tools() -> None:
    """The forecast tool is the 4th legal output, appended to the one list."""
    tools = build_agent_tools(executor_returning())

    assert [tool.name for tool in tools] == [
        "query",
        "ask_follow_up",
        "refuse_unsupported",
        "forecast",
    ]


def test_the_stage_event_is_a_no_op_outside_a_graph_runtime() -> None:
    """Bare tool calls (these tests) must not require a running graph to succeed."""
    content: Any = run_forecast_tool(
        executor_returning(*HISTORY_ROWS), ForecastToolParams(sku="PENCIL-0213")
    )

    assert isinstance(content, str)
