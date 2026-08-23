# Task Breakdown — AI Logistics Analytics Dashboard

## Context

Repo has docs + dataset, no code. **Breakdown only** — no implementation choices here; per task we'll pick options + trade-offs later.

Delivery style (user decision): **ship in slices, not big bang.** Skeleton → Dashboard → Chat (query) → Chat (forecast) → Hardening. Each slice ends green.

**Rule for every task:** done = a command exits 0. No eyeball checks.
**Oracle rule:** expected numbers come from an independent read of the CSV or `business-definition.md` constants — never from the code under test.
**Real LLM:** agent tests call real Claude. They assert structure (tool, params, numbers ⊆ tool output), not wording; retried ≤2×.

Dataset verified: `infra/data/mock_logistics_data.csv`, 400 rows, status 304/55/27/11/3 == docs. Extra dimensions: `product_category, region, warehouse`.

**Assumption (flagged):** the generic query engine (metric × group-by × filters) is built in Slice 1 and drives the dashboard charts, so Slice 2 adds zero calculator work. Honours "one shared calculator" (architecture Decision 1/2). Tell me if you want the dashboard hardcoded first instead.

---

## Slice 0 — Skeleton (user AC: whole app runs with docker-compose; structure matches architecture + tech-stack docs)

| ID | Task | Auto-check | Pass when |
|---|---|---|---|
| S0.1 | Back-end skeleton: service boots, health endpoint, DB connection wired, config from env | API test + DB ping test | `GET /health` → 200 and reports DB reachable |
| S0.2 | Layer folders per architecture §3 (`agent / api / tools / calculator / data`) with import boundaries enforced | structure test + import-boundary lint + planted-violation test | all 5 folders exist; lint passes; planted violation fails |
| S0.3 | Database container + dataset loaded, read-only | DB test | 400 rows; status counts 304/55/27/11/3; write rejected; reload twice → still 400 |
| S0.4 | Front-end skeleton: React app, shadcn initialised, HTTP client installed, calls `/health` | build + type-check + lint + browser test | all exit 0; page shows backend status text from `/health` |
| S0.5 | docker-compose runs db + back-end + front-end together | compose smoke script | `docker compose up` → front-end 200, back-end health 200, DB row count 400 |
| S0.6 | Tech-stack conformance | dependency check script | back-end deps include FastAPI, SQLAlchemy, Pydantic, LangChain, LangGraph; front-end deps include React, shadcn, axios |

**Slice gate:** S0.5 + S0.6 green.

## Slice 1 — Dashboard

| ID | Task | Auto-check | Pass when |
|---|---|---|---|
| S1.1 | 5 KPIs in calculator | unit test vs constants | 400 / 304 / 55 / 84.7% (±0.05) / avg delivery time == CSV mean over 370 rows |
| S1.2 | Generic aggregate query (metrics: order count, delivered, delayed, delay rate, avg delivery time, quantity; group-bys: none/week/month/carrier/status/sku/category/region/warehouse; filters: date range + each dimension) | parametrized test vs CSV oracle — runs under `pytest -m stack` (D18: the calculator builds SQL, so the oracle needs the live database) | every combo == oracle; grouped sums == ungrouped; empty filter → empty, no error |
| S1.3 | KPI endpoint | API test | body == S1.1 |
| S1.4 | Three parameterless chart routes under `/api/dashboard/` (order-volume, delivery-performance, carrier-delay-rate), each one fixed call into S1.2 | API test | each route == CSV oracle; volume Σ 400; delivery-performance Σ 359; carrier delay rate sorted desc; each echoes its `params` |
| S1.5 | Dashboard page: 5 KPI cards + 3 charts + data-table toggle under each chart; front-end composes the charts and owns the three fixed display types | browser test | 5 cards, text == KPI endpoint; line + stacked + bar all render; each toggle reveals a table with rows == that route’s rows |

**Slice gate:** S1.5 green. Dashboard feature done
## Slice 2 — Chat: natural-language queries (real Claude)

| ID | Task | Auto-check | Pass when |
|---|---|---|---|
| S2.1 | Parameter validation with whitelists | unit test | unknown metric/group-by rejected; injection-looking strings rejected; valid input round-trips |
| S2.2 | Query tool: result + rows + echoed params + display type | unit test | display rule holds (single→stat, time→line, category→bar, on-time vs delayed→stacked); echo == input |
| S2.3 | Agent: question → tool + params → result → prose; tool call mandatory before text | agent test, 4 canonical questions | expected tool/metric/group-by; tool call precedes text; **no digit in prose absent from tool result** |
| S2.4 | Out-of-scope refusal | agent test | "weather", "poem" → unsupported display, null data, no digits |
| S2.5 | `POST /api/chat` over SSE: `stage`* → one `result` (answer + display + data + rows + explanation) → `done` (D20, D23) | API test + shared frame reader | content-type `text/event-stream`; exactly one `result`, schema valid; "total orders" via chat == KPI endpoint; refusal is a `result`, not an `error`; < 30 s |
| S2.6 | Chat page: input, progress states, answer card (stat/line/bar/stacked), explainability panel, table toggle, suggested chips | browser test (real backend) | ≥1 progress line before the answer; carrier question → bar; panel shows metric + group-by; table rows == API rows; ≥3 chips, click fills input |
| S2.7 | Routing eval set (≥12 questions) | eval test | ≥11/12 correct tool+params; 0 invented digits; report written |

**Slice gate:** S2.7 green.

## Slice 3 — Chat: forecasting

| ID | Task | Auto-check | Pass when |
|---|---|---|---|
| S3.1 | Forecast calculator: monthly demand per SKU, horizon N, inventory recommendation, methodology | unit test | hand-computed tiny series matches; history == S1.2 quantity-by-month; length N; 4 parts present |
| S3.2 | Forecast tool + agent routing | agent test | "predict demand for SKU X next 4 months" → forecast tool, horizon 4, correct SKU; no invented digits |
| S3.3 | Forecast card: values, history solid + forecast dashed, inventory advice, methodology | browser test | 4 sections visible; chart has a dashed line |

**Slice gate:** S3.3 green.

## Slice 4 — Hardening & docs

| ID | Task | Auto-check | Pass when |
|---|---|---|---|
| S4.1 | README + env example + decision log | doc-check script | headings: Setup, Architecture, AI approach, Key decisions, Assumptions, Limitations, Future improvements, AI-usage disclosure; every env var in code is in example file |
| S4.2 | No secrets committed | secret scan | exit 0; env file ignored |
| S4.3 | `verify_all` one-shot gate (all checks above, in order) | run it | exit 0 |

---

## Order

```
S0 (all) → S1.1 → S1.2 → S1.3/1.4 → S1.5
        → S2.1 → S2.2 → S2.3 → S2.4 → S2.5 → S2.6 → S2.7
        → S3.1 → S3.2 → S3.3
        → S4
```

## Out of scope

Bonus items (history, caching, ambiguity prompts) unless all gates green. Chips kept — near-zero cost.

