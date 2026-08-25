"""S2.7 + S3.5 — the routing eval set, and the report it has to produce.

The slice gate. The approved questions go through the live service once each — Slice 2's
fourteen plus Slice 3's four forecast questions — and the run is scored on two things: did
the model reach for the right tool with the right parameters, and did it state a figure
nothing computed. Both are structural. Nothing here looks at wording.

Once each, deliberately. The agent tests retry because a single flake should not fail a
criterion; an eval that retries is measuring its best attempt rather than its behaviour,
and the ≥13/14 bar only means something if every question is asked exactly once.

The report is not a by-product — S2.7 requires the file. It is written before the
assertions run, so a failing run still leaves the reviewer the per-question verdicts that
explain *why* it failed.

Marked ``stack``: run with ``pytest -m stack``. One run makes fourteen paid model calls.
"""

from __future__ import annotations

import datetime
import os
from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest

from tests.conftest import REPO_ROOT, csv_expected_rows
from tests.sse_reader import ask, invented_digits, numbers_in

pytestmark = pytest.mark.stack

#: Where the report lands. Named by the Slice 3 spec's evidence manifest, not invented
#: here; one report now covers both tools (spec review Q5).
REPORT_PATH = (
    REPO_ROOT
    / "_1_Tasks"
    / "Chat"
    / "08_24_2026_21_02_slice3_chat_forecasting"
    / "evidence"
    / "07_eval_report.md"
)

#: ``docs/tasks.md``'s ≥11/12 ratio, deliberately kept at 1 over the grown set (D4.3).
MAX_MISSES = 1

CsvRows = list[dict[str, str]]


@pytest.fixture(scope="module")
def _stack(compose_stack: None) -> None:
    """Alias so the eval implicitly requires the running stack."""
    return compose_stack


@dataclass(frozen=True)
class EvalCase:
    """One approved question and the routing it is expected to produce.

    Filters are matched by prefix so that "July 2025" can be pinned to the month without
    pinning it to the 31st: which month was counted is the routing decision, and whether
    the model wrote the last day or the first of the next is phrasing.
    """

    number: int
    question: str
    display: str
    metrics: tuple[str, ...] = ()
    group_by: str | None = None
    filter_prefixes: dict[str, str] = field(default_factory=dict)
    missing_info: str = "time_bucket"
    horizon: int | None = None


#: The approved list (spec, O5). Four canonicals, six more queries, two out-of-domain
#: refusals, one in-domain refusal, one follow-up — one question per behaviour the design
#: says exists, so a regression in any of them costs a point.
EVAL_CASES: tuple[EvalCase, ...] = (
    EvalCase(1, "How many orders do we have in total?", "stat", ("order_count",), "none"),
    EvalCase(
        2,
        "Show delayed orders by week from October to December 2025",
        "line",
        ("delayed_orders",),
        "week",
        {"date_from": "2025-10", "date_to": "2025-12"},
    ),
    EvalCase(3, "Which carrier has the highest delay rate?", "bar", ("delay_rate",), "carrier"),
    EvalCase(
        4,
        "Compare on-time vs delayed orders per month",
        "stacked",
        ("delayed_orders", "delivered_orders"),
        "month",
    ),
    EvalCase(5, "How many orders were delivered?", "stat", ("delivered_orders",), "none"),
    EvalCase(6, "What is the average delivery time?", "stat", ("avg_delivery_time",), "none"),
    EvalCase(7, "Show order volume per month in 2025", "line", ("order_count",), "month"),
    EvalCase(
        8, "Total quantity shipped by product category", "bar", ("quantity",), "product_category"
    ),
    EvalCase(9, "Delay rate by warehouse", "bar", ("delay_rate",), "warehouse"),
    EvalCase(
        10,
        "How many orders from US-E in July 2025?",
        "stat",
        ("order_count",),
        "none",
        {"region": "US-E", "date_from": "2025-07", "date_to": "2025-07"},
    ),
    EvalCase(11, "What's the weather in Hong Kong?", "unsupported"),
    EvalCase(12, "Write a poem about logistics", "unsupported"),
    EvalCase(13, "Delayed orders by destination city", "unsupported"),
    EvalCase(14, "Show me the delayed orders trend", "follow_up"),
    # Slice 3 (S3.5): the four forecast questions from the spec review. The SKUs are the
    # dataset's own — PENCIL-0213 has the three months the window needs, PAPER-0197 one.
    EvalCase(
        15,
        "Predict demand for PENCIL-0213 for the next 4 months",
        "forecast_line",
        filter_prefixes={"sku": "PENCIL-0213"},
        horizon=4,
    ),
    EvalCase(
        16,
        "Forecast demand for CRAYON-0017 over the next 2 months",
        "forecast_line",
        filter_prefixes={"sku": "CRAYON-0017"},
        horizon=2,
    ),
    EvalCase(17, "How much inventory should I plan?", "follow_up", missing_info="sku"),
    EvalCase(18, "Predict demand for PAPER-0197 for the next 4 months", "unsupported"),
)


@dataclass(frozen=True)
class Verdict:
    """How one question went, and why, in words a reviewer can check."""

    case: EvalCase
    routed: bool
    invented: set[float]
    note: str

    @property
    def passed(self) -> bool:
        """A question counts only when the routing was right and no figure was invented."""
        return self.routed and not self.invented


def _check(case: EvalCase, result: dict[str, Any], csv_rows: CsvRows) -> tuple[bool, str]:
    """Score one answer against its expected routing and against the CSV."""
    if result["display"] != case.display:
        return False, f"display was {result['display']}, expected {case.display}"

    if case.display == "unsupported":
        if numbers_in(result["answer"]):
            return False, "the refusal stated a figure"
        return True, "refused, no figure stated"

    if case.display == "follow_up":
        follow_up = result["follow_up"] or {}
        if follow_up.get("missing_info") != case.missing_info:
            return False, f"missing_info was {follow_up.get('missing_info')!r}"
        if numbers_in(str(follow_up.get("question", ""))):
            return False, "the follow-up question stated a figure"
        return True, f"asked for the {follow_up['missing_info']}"

    if case.display == "forecast_line":
        return _check_forecast(case, result, csv_rows)

    explanation = result["explanation"]
    if tuple(sorted(explanation["metrics"])) != tuple(sorted(case.metrics)):
        return False, f"metrics were {explanation['metrics']}, expected {list(case.metrics)}"
    if explanation["group_by"] != case.group_by:
        return False, f"group_by was {explanation['group_by']}, expected {case.group_by}"
    for name, prefix in case.filter_prefixes.items():
        actual = explanation["filters"].get(name, "")
        if not str(actual).startswith(prefix):
            return False, f"filter {name} was {actual!r}, expected to start {prefix!r}"

    expected = csv_expected_rows(csv_rows, explanation)
    actual_rows = {
        row["group"]: {metric: row[metric] for metric in explanation["metrics"]}
        for row in result["rows"]
    }
    if actual_rows != expected:
        return False, "the rows disagree with the CSV re-read of the same parameters"
    return True, f"{explanation['metrics']} by {explanation['group_by']}, rows match the CSV"


def _check_forecast(case: EvalCase, result: dict[str, Any], csv_rows: CsvRows) -> tuple[bool, str]:
    """Score one forecast answer: routing, echoed params, history vs CSV, horizon.

    The forecast *values* are scored in ``test_chat_forecast_stack.py`` against a hand
    oracle; here the routing questions are whether the model reached the forecast tool
    with the right SKU and horizon, and whether the history is the CSV's.
    """
    explanation = result["explanation"]
    if explanation["metrics"] != ["quantity"] or explanation["group_by"] != "month":
        return False, f"history query was {explanation['metrics']} by {explanation['group_by']}"
    for name, prefix in case.filter_prefixes.items():
        actual = explanation["filters"].get(name, "")
        if not str(actual).startswith(prefix):
            return False, f"filter {name} was {actual!r}, expected to start {prefix!r}"

    history = {
        row["group"]: {"quantity": row["quantity"]} for row in result["rows"] if "quantity" in row
    }
    if history != csv_expected_rows(csv_rows, explanation):
        return False, "the history rows disagree with the CSV re-read of the same parameters"

    forecast = result.get("forecast") or {}
    if case.horizon is not None and forecast.get("horizon") != case.horizon:
        return False, f"horizon was {forecast.get('horizon')!r}, expected {case.horizon}"
    forecast_rows = [row for row in result["rows"] if "forecast" in row]
    if len(forecast_rows) != forecast.get("horizon"):
        return False, f"{len(forecast_rows)} forecast rows for horizon {forecast.get('horizon')!r}"
    return True, f"forecast for {forecast.get('sku')}, history matches the CSV"


def _run(case: EvalCase, base_url: str, csv_rows: CsvRows) -> Verdict:
    """Ask one question and score it, turning any failure into a recorded miss.

    A raised exception here would abort the loop before the report is written, and S2.7
    requires the file — the reviewer of a bad run needs the per-question verdicts most,
    not least. A malformed stream, a fault frame or a missing field is therefore the same
    outcome as a wrong tool: this question scored zero, and the run continues so the
    assertions at the end of the test remain the only thing that fails it.
    """
    try:
        result = ask(base_url, case.question).result
        routed, note = _check(case, result, csv_rows)
    except (AssertionError, KeyError, httpx.HTTPError) as exc:
        return Verdict(case=case, routed=False, invented=set(), note=f"{type(exc).__name__}: {exc}")
    return Verdict(case=case, routed=routed, invented=invented_digits(result), note=note)


def _report(verdicts: list[Verdict]) -> str:
    """Render the per-question table S2.7 requires. Contains no credential, only results."""
    passed = sum(1 for verdict in verdicts if verdict.passed)
    invented = sorted({digit for verdict in verdicts for digit in verdict.invented})
    lines = [
        "# Slice 2 routing eval (S2.7)",
        "",
        f"- Run: {datetime.datetime.now(tz=datetime.UTC).isoformat(timespec='seconds')}",
        f"- Model: `{os.environ.get('LLM_MODEL', 'unset')}`",
        f"- Score: **{passed}/{len(verdicts)}** correct tool + parameters "
        f"(pass bar: at most {MAX_MISSES} miss)",
        f"- Invented digits across the set: **{len(invented)}** {invented or ''}".rstrip(),
        "- Each question asked once, no retry: a retried eval measures its best attempt "
        "rather than its behaviour.",
        "",
        "| # | Question | Expected | Verdict | Detail |",
        "| --- | --- | --- | --- | --- |",
    ]
    for verdict in verdicts:
        case = verdict.case
        expected = case.display
        if case.metrics:
            expected = f"{expected} · {', '.join(case.metrics)} · {case.group_by}"
        note = verdict.note
        if verdict.invented:
            note = f"{note}; invented {sorted(verdict.invented)}"
        note = note.replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| {case.number} | {case.question} | {expected} | "
            f"{'PASS' if verdict.passed else 'MISS'} | {note} |"
        )
    return "\n".join(lines) + "\n"


def test_the_approved_question_set_routes_correctly_and_invents_nothing(
    _stack: None, backend_base_url: str, csv_rows: CsvRows
) -> None:
    """The slice gate: at most one miss over the fourteen, and no invented digit anywhere."""
    verdicts = []
    for case in EVAL_CASES:
        verdicts.append(_run(case, backend_base_url, csv_rows))

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(_report(verdicts), encoding="utf-8")

    misses = [verdict.case.number for verdict in verdicts if not verdict.routed]
    invented = {verdict.case.number: verdict.invented for verdict in verdicts if verdict.invented}
    assert not invented, f"figures stated with nothing behind them, by question: {invented}"
    assert len(misses) <= MAX_MISSES, f"questions {misses} routed wrongly; see {REPORT_PATH}"
