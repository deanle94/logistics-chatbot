---
status: draft
created: 08_23_2026
updated: 08_23_2026
---

# Slice1 Dashboard

## Your Role

Senior Full Stack Engineer (Python / FastAPI + React / TypeScript), focused on data correctness

## Intent

- **Problem:** Slice 0 shipped a layered skeleton and a seeded read-only PostgreSQL, but `calculator/` is empty, `api/` serves only `/health`, and the front-end renders a status card. The 🔴 core dashboard — 5 KPIs + 3 charts (`docs/requirement.md` §2.1) — does not exist, and nothing in the codebase computes a number from the 400 rows.
- **Approach:** Decided up front this time (not deferred to step 3) — see **Decisions taken before implementation** below. Everything stays inside `docs/architecture.md` (Decision 1: one calculator owns every formula; §3 import rules), `docs/business-definition.md` (the only definitions), `docs/technical-stack.md`, `rules/python-coding-rules.md`, `rules/react-coding-rules.md`, and `docs/design/Main.dc.html` for the page. One deliberate deviation from `architecture.md` §2 is recorded in D9.
- **Idea:** The **generic query engine** (metric × group-by × filters, S1.2) is built here and every dashboard number goes through it, so Slice 2's chat adds zero calculator work. It is built but **not exposed over HTTP** — the dashboard reaches it through three fixed routes, the chat will reach it in-process via *agent → tool → calculator*. Honours architecture Decision 1/2.

## Acceptance Criteria

Source: `docs/tasks.md` → Slice 1 table (S1.1–S1.5). Every criterion = a command exits 0. No eyeball checks.

- **S1.1 Five KPIs in the calculator** — total orders 400; delivered 304; delayed 55; on-time rate 84.7% (±0.05) = delivered ÷ (delivered + delayed); average delivery time = mean(`delivery_date` − `order_date`) over the 370 rows that have both dates, returned already rounded to 1 decimal with a `unit` field (D3). Every formula lives in `calculator/` and nowhere else. *(unit test vs CSV oracle)*
- **S1.2 Generic aggregate query** — metrics {order count, delivered, delayed, delay rate, avg delivery time, quantity} × group-bys {none, week, month, carrier, status, sku, product_category, region, warehouse} × filters {date range, plus each dimension}. Every combination equals the CSV oracle; each grouped result sums back to its ungrouped total; a filter matching nothing returns an empty result, not an error. Weeks are ISO, Monday-start, keyed by the Monday's date (D2). *(parametrized unit test vs CSV oracle)*
- **S1.3 KPI endpoint** — `GET /api/kpis` → 200, body equals the S1.1 calculator output field for field. The route contains no formula. *(API test)*
- **S1.4 Three chart routes** — `GET /api/dashboard/order-volume`, `GET /api/dashboard/delivery-performance`, `GET /api/dashboard/carrier-delay-rate`. Each takes **no parameters**, is one fixed call into the S1.2 engine, and returns `{rows, params}` where `params` echoes the metric and group-by used. Each equals the CSV oracle: volume Σ 400, delivery performance Σ 359, carrier delay rate sorted descending. *(API test)*
- **S1.5 Dashboard page** — 5 KPI cards whose text equals `/api/kpis`; the front-end composes the dashboard from the three routes and owns their three fixed display types (line, stacked bar, bar); a data-table toggle under each chart reveals a table whose row count equals the rows that chart's own route returned. Layout follows `docs/design/Main.dc.html`. *(Playwright against the live compose stack)*

**Slice gate:** S1.5 green.

> `docs/tasks.md` originally read "Slice gate: S1.6 green" and its Order block listed `S1.5 → S1.6`, but the Slice 1 table has no S1.6 row. Confirmed a typo by the tech lead on 08_23_2026, who set the gate to **S1.5** directly in `docs/tasks.md`; the stale `→ S1.6` in the Order block was removed in the same change and the edit logged under *Corrections made to the specs* in `docs/decision-log.md`.

**Oracle rule:** every expected number is derived from an independent read of `infra/data/mock_logistics_data.csv` (the existing `csv_rows` fixture in `tests/conftest.py`) or from `docs/business-definition.md` — never from the code under test.

## Decisions taken before implementation

Each was chosen with its cost stated; full *chose / why / gave up* entries go in `docs/decision-log.md` under Slice 1.

| #   | Decision                                                                                                                                                                                                                                                                                       | Gave up                                                                                                                                                                                               |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D9  | **Three parameterless chart routes under `/api/dashboard/`** (`order-volume`, `delivery-performance`, `carrier-delay-rate`), not a composed `/api/charts` and not a public generic query API. The front-end composes the dashboard and owns the three display types.                           | `architecture.md` §2 draws `/api/kpis · /api/charts`; §2 is updated to match. A fourth chart needs a backend change.                                                                                  |
| D10 | **The generic engine is built but not exposed.** S1.2 lives in `calculator/`; only fixed callers reach it.                                                                                                                                                                                     | Nothing — this is what keeps parameter validation (S2.1) in Slice 2, since no user-supplied string reaches the query builder in Slice 1.                                                              |
| D11 | **shadcn `chart`** (verified: `npx shadcn view chart` → pulls `recharts@3.8.0`, exports `ChartContainer`/`ChartTooltip`/`ChartLegend`, themes off our CSS vars).                                                                                                                               | ~100 KB gzipped of Recharts for three charts.                                                                                                                                                         |
| D12 | **ISO week, Monday start, bucket keyed by the Monday's date.** *UNVERIFIED assumption:* that Postgres `date_trunc('week', …)` matches Python `d − timedelta(days=d.weekday())`. Docker was not running when this spec was written; the step-1 oracle test proves it before any dashboard code. | Week labels are dates, not `2025-W43`.                                                                                                                                                                |
| D13 | **The calculator rounds average delivery time** to 1 decimal and returns a `unit`.                                                                                                                                                                                                             | Textbook separation of computation from presentation. Bought: the dashboard and the Slice 2 chat print the identical number, which S2.3 ("no digit in prose absent from the tool result") depends on. |
| D14 | **Carrier chart = delay rate per carrier, sorted descending**, following `docs/design/Main.dc.html` ("Share arriving late, per carrier"). `requirement.md` §2.1 permitted either.                                                                                                              | This chart does **not** sum to 400, so the Σ cross-check covers only the volume and delivery-performance charts.                                                                                      |
| D15 | **Empty result = HTTP 200, empty rows array, params still echoed.**                                                                                                                                                                                                                            | The caller checks `length === 0` instead of a status code. Bought: the echoed params still render, which is the explainability mechanism Slice 2 reuses.                                              |
| D16 | **Data-table toggle = shadcn `Collapsible` + `Table` inside each chart card** (both verified in the registry, zero new npm dependencies). Required by `requirement.md` §2.3 and S1.5 but drawn nowhere in `docs/design/Main.dc.html` — verified absent across all 268 lines.                   | Expanding pushes the page down.                                                                                                                                                                       |
| D17 | **`/api/kpis` keeps its path** rather than moving under `/api/dashboard/`. *Assumption — say so if you disagree:* the tech lead named the three chart routes explicitly but not this one, and leaving it alone is one fewer deviation from `architecture.md` §2.                               | The API has two shapes side by side — one grouped prefix and one flat route.                                                                                                                          |
| D18 | **The calculator owns the SQL expressions; `data/` only executes them.** `calculator/` builds an *unexecuted* SQLAlchemy `Select`; `data/` opens the session and runs it. Only shape where the database does the aggregation *and* architecture Decision 1 holds — otherwise `count(*) FILTER (WHERE status = 'delayed')`, which **is** the definition of delayed, lands in `data/`. Verified: planting `from sqlalchemy import func` in `calculator/` makes the shipped contract report "Only the data layer touches the database BROKEN". | A Slice 0 import-linter contract had to be **split in two** (replaced, not deleted), and weakening a contract is not the same as passing it. `calculator/` can no longer be unit-tested without PostgreSQL, so the S1.2 oracle test moves into `pytest -m stack` (see the manifest). The calculator now speaks SQL, so a non-SQL source would need the expression map rewritten. |

## Steps

1. Define the eval functions first — one automated check per AC (calculator unit tests, the parametrized oracle test, API tests for the four routes, the Playwright test). Write them so they **FAIL** against today's code.
2. Scan `docs/business-definition.md`, `docs/architecture.md` §3–4, `docs/design/Main.dc.html`, `rules/python-coding-rules.md`, `rules/react-coding-rules.md`, and the existing `data/models.py` + `tests/conftest.py` fixtures.
3. Propose the *implementation* via the Lavish skill — the API-shape decisions are settled (D9–D17), so this step covers what is still open: the calculator's internal shape (one query-spec object vs a function per metric), the response models, and the front-end component split under `rules/react-coding-rules.md`. Wait for approval. Ready to go back and forth.
4. Implement when approved. Write D9–D17 into `docs/decision-log.md` in full *chose / why / gave up* form, and update `docs/architecture.md` §2 so the drawing matches the routes.
5. Run both gate sets (`uv run pytest`, `uv run pytest -m stack`) against a cold stack (`docker compose down -v` first) and capture **every artifact in the manifest below** into this spec's `evidence/` folder. Pass → attach proof, done. Fail → fix and re-run.

### Evidence manifest (all seven required)

Naming follows Slice 0's `evidence/` folder. A missing file means the slice is not done.

| File | Command / source | What it proves |
|---|---|---|
| `01_red_baseline.txt` | step-1 evals on today's code | the tests can fail — a green suite that never went red proves nothing |
| `02_green_static.txt` | `uv run pytest` | ruff, ruff format, mypy, import-linter, the planted violation, structure, deps, health, frontend build/type-check/lint — the code is well-formed and the layers hold. It proves no number: under D18 the calculator emits SQL, so the oracle tests need a database |
| `03_green_stack.txt` | `uv run pytest -m stack` | **the S1.1 and S1.2 calculator + oracle tests**, plus the API and Playwright gates, all against the live compose stack |
| `04_api_responses.txt` | `curl -i` against `/api/kpis` and the three `/api/dashboard/*` routes | **the numbers**. Full status line, headers and JSON body for each of the four routes, so a reviewer can check 400 / 304 / 55 / 84.7% and the chart sums against the CSV by eye |
| `05_api_access_log.txt` | `docker compose logs backend` for the same window | those responses came from the **real running service**, not a mock or a fixture — four 200s, no 500s, no stack traces |
| `06_dashboard_screenshot.png` | Playwright full-page capture | 5 KPI cards and 3 rendered charts, laid out per `docs/design/Main.dc.html` |
| `07_table_toggle_screenshot.png` | Playwright, one toggle expanded | the data-table toggle (S1.5) — invisible in `06` because it is collapsed by default |

> `04` and `05` are both required and are not interchangeable. An access log proves a request was *served*; it says nothing about whether the number was *right*. The response body is what gets checked against the dataset. Capture them from the same run so the timestamps line up.
>
> Two practical notes. `curl` runs on the **host** against the published port (verified present: `curl 8.12.1` in Git Bash) — the backend image is slim and has no curl inside it. And the compose healthcheck polls `/health` every 5 s, so `docker compose logs backend` is mostly health noise: filter it (`grep -v " /health "`) and keep the four request lines plus enough context to show no errors, rather than pasting hundreds of lines.

---

> **!!! IMPORTANT RULES !!!**
> - **Evidence of completion is mandatory.** No step or the task is "done" without proof the step-1 eval function actually passed when run. Use the form that demonstrates it: a screenshot or screen recording for UI, full test-run logs (command + pass/fail summary) for backend/test work, query output or sample rows for data, a successful run/pipeline log for infra. "It works" / "tests pass" with no artifact does not count.
> - **For this slice, evidence means all seven files in the manifest above** — including **screenshots** of the rendered dashboard and **API logs** (both the captured responses and the backend access log). Test output alone is not sufficient.
> - **Python code MUST follow `rules/python-coding-rules.md`**; **React code MUST follow `rules/react-coding-rules.md`** (CLAUDE.md rules 5 and 6). Both are already checked by the existing gates.
> - **DO NOT put a formula anywhere but `calculator/`** — architecture Decision 1. `api/` orchestrates and holds no business definition. The import-linter contracts must stay green.
> - **DO NOT expose the generic query engine over HTTP in this slice** (D10). Only the four fixed routes. A public `{metric, group_by, filters}` surface has no parameter whitelist until S2.1.
> - **DO NOT touch `agent/` or `tools/`** — Slice 1 has no AI. Chat, the query tool and forecasting are Slices 2–3.
> - **DO NOT add a SQL view holding an aggregate.** Decision-log D4a permits one later, but a view defining "delayed" puts the definition in two languages — the drift Decision 1 exists to prevent. If you want one, raise it at step 3 with its own oracle.
> - **DO NOT break Slice 0's 27 static + 6 stack gates.** They are the regression net.
> - Data is **read-only**. The API connects as `app_ro`; no migration, no write path, no edit to `infra/data/`.
> - **DO NOT invent anything outside `docs/architecture.md`, `docs/requirement.md`, `docs/design/`.** Simple and correct beats complete.
> - Write every key decision as **chose / why / gave up**. Decisions without reasoning lose points even when the decision is right.
> - Disclose AI usage while building — one honest paragraph, folded into the README at S4.1.
> - If anything is unclear → ask. No hidden assumptions.
