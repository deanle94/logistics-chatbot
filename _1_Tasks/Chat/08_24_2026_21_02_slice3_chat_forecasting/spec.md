---
status: draft
created: 08_24_2026
updated: 08_24_2026
---

# Slice3 Chat Forecasting

## Your Role

Senior Full Stack + AI Engineer (Python / LangChain / LangGraph / FastAPI + React / TypeScript), focused on grounded LLM output — every digit traceable to a tool result

## Intent

- **Problem:** Requirement §2.5 (🔴 forecasting via chat) and required tool B are unmet. The agent has exactly 3 legal outputs (query tool call / FollowUp / Refuse — `agent-design.md`), none of which predict; `display: "forecast_line"` (requirement §2.3 display 5) has no producer and no renderer. `business-definition.md` defines **Demand = quantity per SKU per month** but no forecast method and no inventory constants.
- **Approach:** Extend, don't rebuild. All forecast math lives in `calculator/` (new module beside the S1.2 engine) — method: **3-month moving average** (spec review Q1). `tools/` adds a `ForecastParams` tool — the agent's **4th legal output** — with whitelist validation (SKU must exist in the dataset; horizon bounded *[1..12, default 4 — placeholder, confirm at step 3]*). The D25/D26 agent gets the tool handed in; same SSE route and envelope, `display: "forecast_line"`, history + prediction in one `rows` array (architecture "Chat path (forecast)"); the closed stage enum is hand-extended with `forecasting` (Q3; D23 anticipated this). Front-end adds the forecast card per `docs/design/ChatForecast.dc.html`.
- **Idea:** History = the existing S1.2 engine (quantity, group-by month, filtered to the SKU) — the plotted history can never disagree with the same question asked as a query. The forecast function itself is pure Python over that series: unit-testable against a hand-computed oracle, no DB needed.

## Acceptance Criteria

Source: `docs/tasks.md` → Slice 3 table (S3.1–S3.3), plus two spec-level gates added at spec review. Every criterion = a command exits 0. Agent tests call the **real Anthropic API, `claude-haiku-4-5-20251001`** (D24) — assert structure (tool, params, digits ⊆ tool output), never wording — retried ≤2×.

- **S3.1 Forecast calculator** — monthly demand per SKU, horizon N forecast, inventory recommendation, methodology. Pass: hand-computed tiny series matches; history == S1.2 quantity-by-month; forecast length == N; all 4 parts present. *(unit test for the pure forecast math; the history==S1.2 oracle runs under `-m stack` — D18.)*
- **S3.2 Forecast tool + agent routing** — "predict demand for SKU X next 4 months" → forecast tool, horizon 4, correct SKU; **no invented digits**. *(agent test, real LLM)*
- **S3.3 Forecast card** — forecast values, history solid + forecast dashed on one chart, inventory advice, methodology. Pass: 4 sections visible; chart has a dashed line. Layout per `docs/design/ChatForecast.dc.html` + `AnswerTypes.dc.html` display 5. *(Playwright vs live compose stack)* — **Slice gate.**
- **S3.4 Unknown / sparse-history SKU refusal** *[spec-level, decided at review Q4]* — unknown SKU, or history shorter than the 3-month window → the identical `unsupported` envelope with the reason (D23: refusal ≠ fault). Pass: refusal envelope, no digits, reason names the SKU problem. *(agent or API test)*
- **S3.5 Eval set grows** *[spec-level, decided at review Q5]* — the S2.7 eval set gains ~4 forecast questions (routing, horizon variant, "How much inventory should I plan?" → FollowUp missing sku, sparse-SKU refusal); exact wording + expected params defined at step 1. Pass: at most 1 miss per 12 (the existing ratio) across the grown set; 0 invented digits; report written. *(eval test)*

**Oracle rule:** unchanged — expected numbers from an independent read of `infra/data/mock_logistics_data.csv` or `docs/business-definition.md`, never from the code under test. The forecast math oracle is a hand-computed tiny series; the history oracle is the already-verified S1.2 path.

## Decisions taken at spec review (08_24_2026, Lavish session)

Full *chose / why / gave up* entries land in `docs/decision-log.md` (D27+) at step 4.

| # | Decision | Gave up |
|---|---|---|
| Q1 | Forecast method: **3-month moving average** (requirement's own draft decision #3; one-line hand-computable oracle) | trend / seasonality capture |
| Q2 | Inventory recommendation: **buffer only** — recommended stock = Σ forecast × (1 + buffer), buffer a constant in `business-definition.md`, start **15%** — no reorder point | the mock's reorder-point line (its 20-day lead time is an invented constant; avg delivery time 3.8d is transit, not procurement lead time) |
| Q3 | Stage enum hand-extended: `interpreting → querying → forecasting → composing` | zero-churn reuse of `querying` |
| Q4 | Unknown / sparse SKU → **refuse** via the one `unsupported` envelope builder, with reason | friendlier FollowUp; best-effort answers |
| Q5 | Eval set **grows** by ~4 forecast questions; one report covers both tools | lower LLM spend per stack run |
| — | Forecast tool = the agent's **4th legal output**; Classify sees it via tool descriptions; `agent-design.md` amended at step 4 (no objection raised) | — |

## Steps

1. Define the eval functions first — the S3.1 unit test (hand-computed 3-month-MA series), the S3.1 history-vs-S1.2 stack test, the S3.2 agent test, the S3.3 Playwright test, the S3.4 refusal gate, the S3.5 grown eval runner — and the exact new questions with expected tool + params. Write them so they **FAIL** against today's code.
2. Scan: architecture "Chat path (forecast)", `ChatForecast.dc.html` + `AnswerTypes.dc.html` display 5, `agent-design.md` + the D25/D26 implementation, the S1.2 engine, the Slice 2 SSE frame reader + chat components, both rules files.
3. Propose via Lavish what this review left open: exact Pydantic shapes (`ForecastParams`, envelope extension, how history vs forecast rows are marked in the one `rows` array), calculator signatures, horizon bounds, front-end component split, and the amendment text for `agent-design.md` + `business-definition.md`. Wait for approval; go back and forth.
4. Implement when approved. Decisions land in `docs/decision-log.md` (D27+) as chose / why / gave up; amend `agent-design.md` (4th legal output, `forecasting` stage) and `business-definition.md` (forecast method + buffer constant).
5. Cold stack (`docker compose down -v`), run both gate sets (`uv run pytest`, `uv run pytest -m stack`), capture **every artifact in the manifest below** into this spec's `evidence/` folder. Pass → attach proof, done. Fail → fix and re-run.

### Evidence manifest (all seven required)

Naming follows Slices 1–2. A missing file means the slice is not done.

| File | Command / source | What it proves |
|---|---|---|
| `01_red_baseline.txt` | step-1 evals on today's code | the tests can fail |
| `02_green_static.txt` | `uv run pytest` | layers hold; no formula outside `calculator/`; frontend build/type-check/lint |
| `03_green_stack.txt` | `uv run pytest -m stack` | S3.1–S3.5 vs live stack + real LLM; Slice 0–2 regression net still green |
| `04_forecast_sse_capture.txt` | `curl -N` POST `/api/chat` — one forecast question **and** one sparse-SKU refusal | raw frames incl. the `forecasting` stage; reviewer checks every digit against the CSV |
| `05_backend_log.txt` | `docker compose logs backend`, same window, health-noise filtered | served by the real service; no 500s |
| `06_forecast_card_screenshot.png` | Playwright full-page | 4 sections + dashed line, per the design file |
| `07_eval_report.md` | the grown eval runner (S3.5) | per-question verdicts over the full set, both tools; 0 invented digits |

> `04` and `05` are both required and not interchangeable (same reasoning as Slices 1–2): the log proves the request was served, the captured frames prove the numbers were right. Capture them from the same run.

---

> **!!! IMPORTANT RULES !!!**
> - **Evidence of completion is mandatory.** No step or the task is "done" without proof the step-1 eval function actually passed when run. Use the form that demonstrates it: a screenshot or screen recording for UI, full test-run logs (command + pass/fail summary) for backend/test work, query output or sample rows for data, a successful run/pipeline log for infra. "It works" / "tests pass" with no artifact does not count.
> - **For this slice, evidence means all seven files in the manifest above.** Test output alone is not sufficient.
> - **The AI never computes a forecast.** It fills `{sku, horizon}`. Every formula — demand series, 3-month moving average, inventory recommendation — lives in `calculator/`; the no-formula-outside-calculator gate must stay green.
> - **`agent-design.md`'s 7 rules bind unchanged.** Adding the 4th legal output and the `forecasting` stage are documented amendments (step 4), not silent edits.
> - **`tools/` validates SKU + horizon before anything runs** — SKU from the dataset whitelist; horizon bounded *[1..12, default 4 — confirm at step 3]*. No AI-generated string reaches the query builder unvalidated.
> - **New business constants (the 15% buffer) go in `business-definition.md`**, not inline in code — the calculator owns the definitions.
> - **DO NOT break the Slice 0–2 gates.** They are the regression net. **DO NOT touch the S1.2 engine** — the forecast *calls* it for history.
> - Data is **read-only** (`app_ro`). No secrets committed.
> - **DO NOT invent anything outside** `docs/tasks.md` Slice 3, `docs/requirement.md` §2.5, `docs/architecture.md` "Chat path (forecast)", `docs/design/`, and the review decisions above. Simple and correct beats complete. Anything still open goes through step 3, not through code.
> - Write every step-3/4 decision as **chose / why / gave up** in `docs/decision-log.md`. Decisions without reasoning lose points even when the decision is right.
> - Python code MUST follow `rules/python-coding-rules.md`; React code MUST follow `rules/react-coding-rules.md` (CLAUDE.md rules 5 and 6).
> - If anything is unclear → ask. No hidden assumptions.
