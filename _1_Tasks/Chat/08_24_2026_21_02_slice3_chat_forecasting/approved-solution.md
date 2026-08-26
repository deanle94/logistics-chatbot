# Approved solution — Slice 3 chat forecasting

Approved by the user in the Lavish review session, 2026-08-25. Picks: **D1=A, D2=A, D3=A, D4=all six as proposed.**
The implementer executes this design; it does not re-decide it. A blocked approach = stop and report (`approach_blocked`), never improvise.

## The chosen approach in one paragraph

Extend, don't rebuild. A new pure-math module `calculator/forecast.py` computes history (via the untouched S1.2 engine), a recursive 3-month moving average, and a buffer-only inventory recommendation. A 4th tool (`forecast`) in `tools/` validates `{sku, horizon}` and emits the complete answer envelope — `display: "forecast_line"`, history + forecast in ONE `rows` array using two value keys, plus a new typed `forecast` block. `agent/` is **not modified** (except one line in `prompts.py`'s `<charts>` block): `enforce` already passes complete envelopes through (`nodes.py:185`) and already converts `{"refusal_reason": …}` into the one `unsupported` envelope (`nodes.py:181`). The `forecasting` SSE stage is emitted from the tool via a langgraph custom stream event. Frontend adds `ForecastAnswer.tsx` per `docs/design/ChatForecast.dc.html`.

## D1 — Envelope: typed `forecast` block (Option A)

`api/chat.py` gains:

```python
class ChatForecast(BaseModel):
    sku: str
    horizon: int          # months ahead
    window: int           # 3
    total: float          # sum of the forecast values
    recommended_stock: int  # ceil(total * (1 + buffer))
    buffer_pct: float     # 15.0
    methodology: str      # prose built in calculator/, all digits from the series
```

`ChatResult` gains `forecast: ChatForecast | None = None` and `"forecast_line"` in the `display` Literal (chat.py:97).
`explanation` keeps its existing meaning: echoes `metrics=["quantity"], group_by="month", filters={"sku": …}, row_count` so the CSV oracle (`conftest.csv_expected_rows`) can verify the history rows unchanged.

Rejected: Option B (no new field — overload `explanation`/`data`/prose). Why lost: muddies the explainability contract the stack oracle re-derives rows from; UI would fish numbers out of prose.

## D2 — Rows: two value keys (Option A)

One `rows` array (architecture "Chat path (forecast)"):

```json
{"group": "2026-05", "quantity": 172}   // history — byte-identical to S1.2 shape
{"group": "2026-09", "forecast": 174}   // forecast — exactly N rows
```

- History rows must compare equal to a plain S1.2 `quantity`-by-`month` query for the same SKU (the S3.1 stack oracle).
- The bridge point (dashed line starts at the last solid point, per the design SVG) is derived **in the frontend component**, not on the wire.
- Forecast month labels continue "YYYY-MM" from the last history month; that date arithmetic lives in `calculator/`.

Rejected: segment marker column. Why lost: frontend must pivot before charting; oracle must strip the marker.

## D3 — `forecasting` stage: custom stream event (Option A)

- Tool side: `from langgraph.config import get_stream_writer`; wrap in a small helper that no-ops when no graph runtime is active (unit tests call the tool bare). Emit `{"stage": "forecasting"}` **before** calling the calculator.
- `api/chat.py`: `astream(..., stream_mode=["updates", "custom"])` — items become `(mode, chunk)` tuples; `custom` chunks with a `stage` key become stage frames; `updates` handling unchanged otherwise.
- Stage sequence on a forecast turn: `interpreting → querying → forecasting → composing`. The stage enum is extended in exactly 4 places: `api/chat.py:34`, `frontend/src/lib/chatApi.ts:13`, `frontend/src/components/chat/ProgressList.tsx:16` (label e.g. "Forecasting demand"), `backend/tests/sse_reader.py:32`.

Rejected: `subgraphs=True` node sniffing. Why lost: couples `api/` to `create_agent`'s internal node names (D23(b) rejected that) and fires only after the tool finishes. **Known risk:** if contextvars do not propagate into the sync tool's executor thread and the custom event never arrives, falling back to Option B is a *recorded deviation*, not a blocker.

## D4 — Six confirmations (all accepted)

1. **Horizon** `1..12`, default `4` (`ge=1, le=12` on the Pydantic field).
2. **Recommended stock** = `ceil(total * 1.15)` whole units (design's 802 = ceil(697×1.15)); D19c one-decimal applies to metrics, not stock units.
3. **Eval**: `MAX_MISSES = 1` stays over the grown ~18-case set.
4. **`REPORT_PATH`** → `_1_Tasks/Chat/08_24_2026_21_02_slice3_chat_forecasting/evidence/07_eval_report.md`. Slice 2's recorded report file is left as recorded.
5. **Gate repair in scope**: `tests/test_planted_violation.py` `_run_lint` gains `encoding="utf-8"` (cp1252 reader-thread crash → `stdout=None` → TypeError at :101). One line; pre-existing env failure; without it `02_green_static.txt` cannot go green.
6. **Design-vs-Q2 deviation**: the mock's reorder-point sentence and "lead time 20 days" chip are dropped (review Q2: buffer only). Card shows buffer-only recommendation + "safety buffer 15% — our assumption" chip. Record in decision log.

## Fixed points (gate-mandated — implement exactly)

- **`calculator/forecast.py`** (new): `WINDOW_MONTHS = 3`, `SAFETY_BUFFER_PCT = 15.0` (constants mirrored in `business-definition.md`); pure `moving_average(series, horizon, window)` — recursive (forecasts feed later windows), unit-tested vs a hand-computed oracle; `run_forecast(execute, sku, horizon)` calls S1.2 `run_query(execute, QuerySpec(metrics=(Metric.QUANTITY,), group_by=GroupBy.MONTH, filters=Filters(sku=sku)))`, raises `InsufficientHistoryError(reason)` when months-with-data < 3 (unknown SKU ⇒ 0 months ⇒ same path). Returns history + forecast + total + recommended_stock + methodology text. **Do not touch the S1.2 engine.**
- **`tools/schemas.py`**: `ForecastToolParams(BaseModel)` — `model_config = ConfigDict(frozen=True, extra="forbid")`, `sku: FilterValue` (required), `horizon: int = Field(default=4, ge=1, le=12)`; `MissingInfo` gains `SKU = "sku"`.
- **`tools/forecast_tool.py`** (new): validate → stage event → `run_forecast` → full envelope JSON string (same pattern as `_ask_follow_up`); on `InsufficientHistoryError` → `json.dumps({REFUSAL_REASON_KEY: reason})` where the reason names the SKU problem. The tool computes nothing.
- **`tools/query_tool.py`**: append the 4th `StructuredTool.from_function(name="forecast", args_schema=ForecastToolParams, description=…)` in `build_agent_tools` (or merge from `forecast_tool.py`'s builder — keep `build_agent_tools` the single list handed to `main.py`).
- **`agent/prompts.py`**: extend the `<charts>` block (lines ~122-131) with the `forecast_line` outcome. **No other `agent/` edits.**
- **Frontend**: `components/chat/answers/ForecastAnswer.tsx` — 4 sections per `docs/design/ChatForecast.dc.html`: (1) forecast value tiles + total, (2) chart with history solid + forecast dashed (`strokeDasharray`, second `<Line>`; bridge point derived locally), (3) inventory recommendation (buffer-only, per D4.6), (4) methodology. Register in `AnswerCard.tsx` switch + `DISPLAY_LABEL` (`forecast_line: 'Forecast'`); add `'forecast_line'` to `ChatDisplay` in `chatApi.ts` and to the e2e spec's local type; `ForecastAnswer` reads the typed `forecast` block. Follow `rules/react-coding-rules.md`; reuse `ChartContainer`/`chartPalette`.
- **Tests** (written FIRST, must fail red against today's code — capture `01_red_baseline.txt`):
  - S3.1 unit: hand-computed 3-month-MA tiny series oracle (in static set).
  - S3.1 stack: history rows == S1.2 query oracle via `csv_expected_rows`.
  - S3.2 agent test (real Haiku, structure only, retry ≤2): forecast question → tool `forecast`, horizon 4, correct SKU, no invented digits.
  - S3.3 Playwright `e2e/chat-forecast.spec.ts`: 4 sections visible + dashed line present; screenshot → `evidence/06_forecast_card_screenshot.png`.
  - S3.4: unknown + sparse SKU → `unsupported` envelope, no digits, reason names the SKU.
  - S3.5: `EVAL_CASES` +4 (forecast routing; horizon variant; "How much inventory should I plan?" → follow_up missing sku; sparse-SKU refusal) + `forecast_line` branch in `_check`.
- **Docs**: `agent-design.md` (4th legal output row + `forecasting` stage — documented amendment, 7 rules unchanged); `business-definition.md` (forecast method row + safety buffer 15% row); `docs/decision-log.md` D27+ as chose/why/gave up (concise — CLAUDE.md rule 10).

## Scope fences (from the spec — bind every agent)

- AI never computes; no formula outside `calculator/`; the no-formula gate stays green.
- Data read-only; no secrets; do not touch `infra/data/` or the S1.2 engine; do not break Slice 0–2 gates.
- Refusal must reuse `REFUSAL_REASON_KEY` — only `agent/nodes.py` may write the `unsupported` display (`test_agent_rules.py:204`).
- Python per `rules/python-coding-rules.md`; React per `rules/react-coding-rules.md`.
- Evidence manifest: all seven files in the spec are required.

---

## Actual deviations (appended post-execution, 2026-08-26)

Execution followed this design; eight small detail deviations were made and recorded
(full rationale in `evidence/gates.md` and `docs/decision-log.md` D29–D31):

1. `subgraphs=True` on the astream call — the pre-approved fallback (langgraph 1.2.11 swallows the custom event without it; no node names inspected).
2. `REFUSAL_REASON_KEY` lives in `tools/schemas.py`, not `query_tool.py` (circular import).
3. `sse_reader.invented_digits()` also credits the `forecast` block.
4. `test_tool_validation.py` enum assertion updated for `MissingInfo.SKU`.
5. Refusal reason names the history problem without quoting the SKU code (digit-free rule).
6. Test/eval SKUs are real dataset SKUs (PENCIL-0213, CRAYON-0017, PAPER-0197) — the mock's SKU-1042 doesn't exist in the CSV.
7. Envelope key-set test gained `"forecast"`.
8. `forecast`/`ask_follow_up` tool descriptions reworded so sku-less planning questions draw a follow-up (D31).

Status: **verified** (2026-08-26) — the API key's spend cap lifted early and the cold-start
`-m stack` run went green: 149 passed, 0 failed, eval 18/18; see `evidence/gates.md`.
