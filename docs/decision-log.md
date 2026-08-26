# Decision Log

Every key decision as **chose / why / gave up**. Slice 4 (S4.1) folds this into the README.

`docs/architecture.md` §4 owns the *architectural* decisions (one calculator, one service, AI
never computes). This file records the *implementation* decisions per slice, and any
deliberate deviation from that document.

---

## Slice 0 — Skeleton

### D1 — uv + `pyproject.toml` + `uv.lock`

|  |  |
| --- | --- |
| **Chose** | `uv` for dependency management and the Docker base image. |
| **Why** | PEP-621 native, so coding rule 14 (`src/` layout + `pyproject.toml`) comes free. `uv sync --frozen` fails loudly on a stale lock instead of quietly resolving something untested. |
| **Gave up** | A tool a reviewer may not know; `pip install -r requirements.txt` is more universally readable. |

### D2 — `import-linter` for the layer boundaries

|  |  |
| --- | --- |
| **Chose** | Declarative `forbidden` contracts in `[tool.importlinter]`, run as `lint-imports`. |
| **Why** | The architecture's import rules become configuration checked by one exit code. It follows the whole import graph, so an *indirect* leak (`agent → helper → data`) is caught — the leak most likely to happen. |
| **Gave up** | An extra dev dependency and a second lint command. Rejected: nested `.ruff.toml` + `banned-api` (config scatters across five files, misses indirect leaks) and a hand-written `ast` walker (~50 lines we would own). |
| **Note** | `main.py` is deliberately outside the contracts — a composition root that could not reach across layers could not compose them. |
| **Note** | The "only `data/` touches the database" contract sets `allow_indirect_imports = true` on purpose: `api/` may call `data/`, it just may not import SQLAlchemy itself. |

### D3 — One-shot seeder container, idempotent by replace

|  |  |
| --- | --- |
| **Chose** | A `seeder` service running `python -m logistics_analytics.data.seed` that exits 0; the API waits on `service_completed_successfully`. Deletes and reloads rather than inserting-if-missing. |
| **Why** | S0.3 ("seed twice → still 400") needs the seed to be a runnable command, not a first-boot side effect. Schema is built from the app's own SQLAlchemy models, so the two cannot drift. Replace-not-append means a changed CSV leaves no stale rows. |
| **Gave up** | A third container and a slower cold start. Rejected: `docker-entrypoint-initdb.d` (only runs on an empty volume, so "seed twice" is unassertable) and seeding in the API's lifespan (the API would need write privileges). |

### D4 — Two roles, `SELECT`-only grants, no view

|  |  |
| --- | --- |
| **Chose** | `app_owner` owns the tables, used only by the seeder. `app_ro` holds `CONNECT + USAGE + SELECT` and is what the API connects as. No view. |
| **Why** | Read-only becomes a *privilege*, not a convention, so no code path can opt out. Measured on a live `postgres:17-alpine`: `INSERT` fails with `permission denied for table orders`; `ALTER DEFAULT PRIVILEGES` covers Slice 1 tables automatically. |
| **Gave up** | Two connection strings in `.env.example`; no object-level second lock. |
| **Rejected** | **Materialized view.** It does block writes (`cannot change materialized view`) but does not protect the base table, `REFRESH` still succeeds, and it went stale in the probe (base 4 rows, view 2). S0.3 asserts "exactly 400 rows" — a matview creates two answers to that question. |
| **Rejected** | **`default_transaction_read_only = on`.** One line, but a session default any code can turn off — passes the test while being security theatre. |

### D4a — Aggregation views: allowed later *(deliberate deviation)*

|  |  |
| --- | --- |
| **Chose** | SQL views containing aggregates may be introduced in a later slice if they earn their place. |
| **Why** | Explicit tech-lead decision, taken with the trade-off stated. |
| **Gave up** | Single ownership of formulas. A view holding "delay rate" would define `delayed` in two languages — the drift `architecture.md` Decision 1 exists to prevent. At 400 rows there is no performance argument on the other side. |
| **Status** | No Slice 0 impact. It first matters when Slice 1 formulas land: a view-based metric would need its own oracle. |

### D5 — Multi-stage build served by nginx, `/api` proxied

|  |  |
| --- | --- |
| **Chose** | `node` builds the bundle, `nginx` serves it, `/api/` proxies to `backend:8000`. |
| **Why** | S0.5 needs the front-end to answer 200 from `docker compose up`. One origin means **CORS never exists** in any slice. The `vite build` S0.4 gates is the artifact that ships, so a broken build cannot pass. Same shape S1.6's public deploy needs. |
| **Gave up** | No hot reload inside compose — a UI change needs `--build frontend`, or `npm run dev` outside compose. A `docker-compose.override.yml` swapping in the dev server would fix it in one file. |

### D6 — Playwright against the real stack

|  |  |
| --- | --- |
| **Chose** | A real browser driving the nginx-served page, not a jsdom component test. |
| **Why** | Asserting on text sourced from `/health` proves the whole chain in one check: page served, React rendered, proxy works, FastAPI answers, PostgreSQL reachable. It also replaces S0.5's bare HTTP 200, which would prove only the first link. Reused by S1.5, S2.6, S3.3. |
| **Gave up** | ~200 MB of browser binaries and a slower test that needs the stack up. |

### D7 — No runner script: every gate is a `pytest` test

|  |  |
| --- | --- |
| **Chose** | `ruff`, `mypy`, `lint-imports`, `npm run type-check/lint/build` and the compose smoke are each a test that shells out and asserts exit 0. Stack-dependent tests sit behind `-m stack`. |
| **Why** | `pytest` is already a runner; a bespoke `verify_slice0.py` would be ~60 lines whose only job is running other code. Two commands cover the slice, and S4.3's `verify_all` becomes `pytest -m ""`. Failures print the tool's own message. |
| **Gave up** | A lint failure is reported as a test failure, so the diagnosis is one level down in captured stdout. Rejected: `Makefile` (`make` not installed on the target machine) and "just document the commands" (no single exit code, so "green" becomes a human claim). |

### Local development credentials live in `docker-compose.yml`

|  |  |
| --- | --- |
| **Chose** | Every credential is `${VAR:-local_dev_default}`; `.env.example` documents them; `.env` is git-ignored. |
| **Why** | S0.5 requires `docker compose up` to work as one command — requiring a hand-made `.env` first would fail that for a fresh clone. |
| **Gave up** | Default passwords sit in a committed file. Local-container-only; any non-local deployment must override all of them. No real secret is committed. |

### D8 — Repo layout: code under `src/`, stack inputs under `infra/`, documents at the root

|  |  |
| --- | --- |
| **Chose** | Three root categories: `src/` (application code), `infra/` (what the stack needs but nobody writes as app code — `db/init/`, `data/`), and documents/governance (`docs/`, `rules/`, `_1_Tasks/`, `CLAUDE.md`). `docker-compose.yml` stays at the root as the entry point. |
| **Why** | A reviewer sees three categories at once — what we wrote, what it runs on, what governs it — instead of eight unranked siblings. Requested by the tech lead. |
| **Gave up** | The package sits at `src/backend/src/logistics_analytics/` — `src` twice. Deliberate: coding rule 14 requires `pyproject.toml` beside `src/<package>/`, and `test_structure.py` asserts it. |
| **Gave up** | `docker-compose.yml` was not moved, so infra is split across two places. S0.5 requires the command to work from the repo root, and `-f infra/…` would re-base every relative path in the file. |
| **Gave up** | `infra/data/` understates the CSV's second role: it is the seeder's input *and* the test oracle (`conftest.py` re-reads it host-side, in no container). Overruled by the tech lead in favour of a smaller root; only the path moved, so the oracle still works. |
| **Gave up** | Three governing documents were edited to match a folder rename. Editing an acceptance criterion to match the filesystem is the wrong direction of travel — logged under *Corrections* so it is traceable. |
| **Blast radius** | `docker-compose.yml`: three build contexts + two bind mounts (container-side `DATASET_PATH` unchanged). `conftest.py`: new `SRC_ROOT`, new `CSV_PATH`. Three markdown citations. The `.venv` had to be rebuilt — `uv` bakes absolute paths into console-script trampolines (`uv trampoline failed to canonicalize script path`); `node_modules` survived, npm's shims resolve relatively. |
| **Evidence** | 27 static + 6 stack gates green from a cold `docker compose down -v`, re-run after each move. The cold start is what proves the `infra/` moves: `01_roles.sh` runs only on an empty volume, and the seeder re-reads the CSV through the dataset mount. |

---

## Slice 1 — Dashboard

D9–D17 were taken at spec review, before any code (one line each in
`_1_Tasks/Dashboard/08_23_2026_slice1_dashboard/spec.md`) and are expanded here. D18–D19 were
taken during implementation review.

### D9 — Three parameterless chart routes under `/api/dashboard/` *(deliberate deviation)*

|  |  |
| --- | --- |
| **Chose** | `GET /api/dashboard/order-volume`, `/delivery-performance`, `/carrier-delay-rate` — no parameters, one fixed call each into the S1.2 engine. `/api/kpis` stays alongside (D17). Not one composed `/api/charts`, not a public generic query API. |
| **Why** | Which charts show, in what order and display type, is a presentation decision; `/api/charts` puts it behind an HTTP boundary, making a layout change a backend change. Three named routes keep composition in the front-end and give each chart its own oracle — volume Σ 400, delivery performance Σ 359 (304 + 55), carrier delay rate descending from GLS 0.2857. |
| **Gave up** | `architecture.md` §2 drew `/api/kpis · /api/charts`; that node was edited with a note pointing back here. A fourth chart now needs a backend route — the price of not exposing the engine (D10). |

### D10 — The generic engine is built but not exposed over HTTP

|  |  |
| --- | --- |
| **Chose** | The S1.2 metric × group-by × filters engine lives in `calculator/`; only fixed in-process callers reach it (the three chart routes now, `tools/` in Slice 2). No `{metric, group_by, filters}` HTTP surface. |
| **Why** | Building it here is what makes Slice 2 add zero calculator work, so chat and dashboard physically cannot disagree — architecture Decision 1 made structural rather than promised. Off HTTP, no user string reaches the query builder yet, so the parameter whitelist stays where it belongs (S2.1). |
| **Gave up** | Nothing in Slice 1 — the cost is deferred: S2.1's whitelist becomes load-bearing on its first day. |

### D11 — shadcn `chart` (Recharts) for all three charts

|  |  |
| --- | --- |
| **Chose** | The shadcn `chart` block. Verified: `npx shadcn view chart` pulls `recharts@3.8.0`, exports `ChartContainer` / `ChartTooltip` / `ChartLegend`, themed off our existing CSS variables. |
| **Why** | Line, stacked bar and bar are three of the six displays `requirement.md` §2.3 requires; Slices 2–3 need the same three plus the forecast line. One dependency covers all of them and inherits our theme — hand-rolled SVG would need re-theming for each. |
| **Gave up** | **109 kB gzipped** (370.72 kB raw) for three charts, amortised across three slices — 54 % of the 202.92 kB gzipped bundle. Measured, not estimated: one build with `recharts`, `victory-vendor`, `d3-*` and `decimal.js` forced into their own rolldown chunk, which isolates exactly what this decision costs. |

### D12 — ISO week, Monday start, bucket keyed by the Monday's date

|  |  |
| --- | --- |
| **Chose** | Week group-by uses ISO weeks from Monday, each bucket keyed by that Monday's `date`, not a `2025-W43` label. |
| **Why** | A date key sorts correctly as a string, renders on a time axis without parsing, and matches the month key's type, so the front-end has one code path. `date_trunc('week', …)` is Monday-start by definition, so the SQL side is free. |
| **Gave up** | Labels read as dates, not the week numbers a logistics manager would say. 53 buckets, `2024-12-30` → `2025-12-29`; the first is a 2024 Monday holding January 2025 orders, which looks wrong until you know the rule. |
| **Status** | Postgres-vs-Python equivalence is **no longer an assumption** — `tests/test_query_oracle.py` asserts it against a live database with buckets derived from the CSV host-side. |

### D13 — The calculator rounds average delivery time and returns a `unit`

|  |  |
| --- | --- |
| **Chose** | `calculator/` returns `{"value": 3.8, "unit": "days"}` already rounded, not `3.82973`; every KPI carries a `unit` (`null` for counts, `"%"` for on-time rate). |
| **Why** | S2.3 forbids any digit in the agent's prose absent from the tool result. Rounding in the UI would make the dashboard print `3.8` while the tool result said `3.82973`, so "about 3.8 days" would be an invented digit by that rule. Rounding once, in the formula's single owner, makes both print the identical string. |
| **Gave up** | A display concern now lives in the calculator. Bought back: one number, one place, S2.3 stays mechanically checkable. |

### D14 — The carrier chart shows delay **rate**, sorted descending

|  |  |
| --- | --- |
| **Chose** | `carrier-delay-rate` returns `delay_rate` per carrier, `value_desc` — nine rows, first GLS 0.2857. Not order counts. |
| **Why** | `requirement.md` §2.1 permits either; `docs/design/Main.dc.html` settles it — the card reads "Share arriving late, per carrier". A rate also answers the real question: 84 orders with 11 delays is not worse than 7 with 2. |
| **Gave up** | This chart does not sum to 400, so the "grouped sums back to ungrouped total" cross-check covers only order-volume (Σ 400) and delivery-performance (Σ 359). Its oracle is a per-carrier comparison plus a non-increasing check. |

### D15 — Empty result = HTTP 200, empty `rows`, `params` still echoed

|  |  |
| --- | --- |
| **Chose** | A filter matching no rows returns `200` with `"rows": []` and the full `params`. Never 404, never an error. |
| **Why** | "No orders matched" is a valid answer — the query ran. Echoing `params` is what lets the UI say *which* question returned nothing: the explainability mechanism (`requirement.md` §2.4) that Slice 2 reuses unchanged. |
| **Gave up** | Callers must check `rows.length === 0` rather than a status code, so an empty state is easier to forget. Every consumer is ours, and the Playwright gate renders the real ones. |

### D16 — Data-table toggle = shadcn `Collapsible` + `Table` inside each chart card

|  |  |
| --- | --- |
| **Chose** | Each chart card holds a collapsed `Collapsible` containing a `Table` of that chart's rows. Both verified in the shadcn registry; zero new npm dependencies. |
| **Why** | §2.3 lists the toggle as a required display, §2.4 counts it as explainability, S1.5 gates it. It is drawn nowhere in `docs/design/Main.dc.html` (verified across all 268 lines), so reusing two registry components keeps the deviation minimal. |
| **Gave up** | Expanding pushes the page down instead of overlaying. Rejected modal and side sheet: both hide the numbers from the same screenshot as the chart, and `07_table_toggle_screenshot.png` is evidence the two agree. |

### D17 — `/api/kpis` keeps its top-level path

|  |  |
| --- | --- |
| **Chose** | The KPI route stays at `/api/kpis`, not `/api/dashboard/kpis`. |
| **Why** | The tech lead named the three chart routes and not this one; `architecture.md` §2 already drew `/api/kpis`, so leaving it is one fewer deviation to defend — D9 stays the slice's only route-shape deviation. |
| **Gave up** | Two API shapes side by side: one grouped prefix, one flat route. Cosmetic, reversible in one line. *An implementer-side assumption, stated as such in the spec.* |

### D18 — The calculator owns the SQL expressions; `data/` only executes them *(deliberate deviation)*

|  |  |
| --- | --- |
| **Chose** | `calculator/` builds an **unexecuted** SQLAlchemy `Select`; `data/` opens the session and runs it. So `calculator/` may import `sqlalchemy`, but not `psycopg` or `data.engine` / `data.repository`. The Slice 0 contract *"Only the data layer touches the database"* is **split into two** contracts saying exactly this — replaced, not deleted. |
| **Why** | The only shape where the database does the aggregation *and* architecture Decision 1 holds. Otherwise `count(*) FILTER (WHERE status = 'delayed')` — which **is** the definition of delayed — would live in `data/`, giving a business definition a second home. Verified, not assumed: planting `from sqlalchemy import func` in `calculator/` made the shipped contract report *"…calculator is not allowed to import sqlalchemy"*, which is why it had to be split. |
| **Gave up** | (a) A Slice 0 contract was edited — weakening a contract until it passes is not passing it. Mitigated: the replacement forbids opening a connection, the thing that actually matters. (b) `calculator/` can no longer be unit-tested without PostgreSQL, so the S1.2 oracle moved behind `-m stack` (D19). (c) A future non-SQL source would need the whole expression map rewritten. |
| **Rejected** | **Pure-Python calculator** reading all 400 rows into memory. Simplest, and needs no database for the oracle — rejected because the tech lead wants aggregation pushed into the database. |
| **Rejected** | **Formulas in `data/`, `calculator/` as pass-through.** Violates architecture Decision 1 and leaves `calculator/` as dead weight owning nothing. |

### D19 — Evidence manifest: the oracle tests are reported in `03_green_stack.txt`

|  |  |
| --- | --- |
| **Chose** | `02_green_static.txt` (`uv run pytest`) proves ruff, ruff format, mypy, import-linter, the planted violation, structure, deps, health, frontend build/type-check/lint. The S1.1/S1.2 oracle tests are reported in `03_green_stack.txt` (`uv run pytest -m stack`). Both files are required. |
| **Why** | A direct consequence of D18: a calculator that emits SQL can only be compared against the CSV by executing it. Leaving those tests in the fast gate would mean either a skipped test that reads as green, or a second in-memory implementation of the same formulas — the second home D18 exists to prevent. |
| **Gave up** | The fast gate no longer proves a single number: it says "the code is well-formed and the layers hold", not "the numbers are right". A reviewer must run both commands, and the correctness gate needs Docker up. |

### D19a — No header badges *(deliberate deviation from `docs/design/Main.dc.html`)*

|  |  |
| --- | --- |
| **Chose** | Removed both header badges: the design's "Counted straight from your orders" and Slice 0's live backend-health indicator. The header is the breadcrumb only. |
| **Why** | Tech lead's call. The badge asserted in words what the five KPI cards already demonstrate, and backend health is operator telemetry, not a logistics manager's concern. |
| **Gave up** | Slice 0's browser gate read `/health` out of that badge. It now asserts a KPI value fetched from the live API instead — the same chain proven more strongly, since a correct KPI needs the rows seeded, queried and aggregated, not just `SELECT 1`. `fetchHealth`, `useHealth` and `BackendStatusBadge` were deleted as dead code; `GET /health` itself stays, used by the compose healthcheck and the second browser test. |

### D19b — The delay rate is a percentage, computed in the calculator

|  |  |
| --- | --- |
| **Chose** | `delay_rate` returns `28.6`, the same kind of number `on_time_rate` already returned, not the `0.2857` ratio it returned before. The front-end appends `%` and changes nothing else. |
| **Why** | Tech lead's call on the display. Doing the ×100 in React would break D13 — the Slice 2 chat would quote `0.2857` while the dashboard showed `28.6%` — and two scales for one ratio is the drift architecture Decision 1 exists to prevent. `on_time_rate` was already a percentage, so this removes an inconsistency rather than adding one. |
| **Gave up** | `src/lib/metricFormat.ts` has to know which metrics carry a `%`. That is the presentation fact D22 already flagged as living outside `calculator/`; it adds a symbol and never touches a digit. |

### D19c — One decimal for every rounded metric

|  |  |
| --- | --- |
| **Chose** | `delay_rate`, `on_time_rate` and `avg_delivery_time` all round to one decimal. |
| **Why** | Tech lead's call. The on-time and delay rates are one ratio read from both ends, so at one decimal they add to exactly `100.0` (84.7 + 15.3); at two they came to `100.02`, which a reviewer checks with a calculator and does not forget. `tests/test_query_oracle.py` asserts the sum over the whole dataset — per group the two halves can each land on a `.x5` boundary and round apart, so the claim is scoped to ungrouped. |
| **Gave up** | Two carriers whose true delay rates differ by under 0.05 points now tie, and `ORDER BY` sorts the rounded value, so their order becomes arbitrary. No two tie on this dataset (28.6 / 23.9 / 22.4 / 20.8 / 16.0 / 13.1 / 8.3 / 5.3 / 0.0) and the oracle asserts the ordering against the CSV, so a dataset that ties fails the test rather than silently reordering the chart. |

---

## Slice 2 — Chat: natural-language queries

Taken at design review, before any Slice 2 code. The first transport decision in the project.

### D20 — The chat endpoint streams over SSE *(deliberate deviation)*

|  |  |
| --- | --- |
| **Chose** | `POST /api/chat` returns `text/event-stream`: `stage`* (advisory) → one `result` (the whole answer) → `done`. Faults emit `error` then `done`. |
| **Why** | `docs/design/States.dc.html` state 2 already specifies a progress list, annotated *"Shows progress in the user's words, not the system's."* Plain JSON can only fake that on a timer, and S2.5 allows 30 s. LangGraph emits the milestones already — verified: `langgraph 1.2.11`, `types.py:122`. |
| **Gave up** | Scope not in `requirement.md`. Every Slice 2 gate must read frames — bounded by one shared test helper. `architecture.md` §2 and §5 edited. Proxy buffering must stay off or frames clump. |
| **Rejected** | **Token streaming** (`stream_mode="messages"`). Prose is the last step here, so it saves ~1 s of a 3–30 s call while painting model text before S2.3's no-invented-digit check can run. |
| **Rejected** | **Plain JSON.** Cheapest, and what the gates assume. Overruled: the progress states are shipped design, and SSE wraps the same object, so correctness is untouched. |

### D21 — One answer is one envelope, not one frame per part

|  |  |
| --- | --- |
| **Chose** | The `result` frame carries the five fields S2.5 names. One `rows` array feeds the chart, the table toggle and the explainability panel. Rejected shape: a `{type: text \| chart \| table, message}` union. |
| **Why** | §2.3 display 6 puts the table *under* every chart, so an answer is prose **and** chart **and** table, never one-of-three — and the union has no slot for the §2.4 interpretation required on every answer. Under Recharts (D11) chart rows and table rows are the same array. |
| **Gave up** | One display per answer — no two-chart answer. §2.3 asks for no more. |

### D22 — No `columns` metadata; the front-end formats numbers

|  |  |
| --- | --- |
| **Chose** | Five fields. No `columns` array of label + number format. |
| **Why** | S2.5 does not name one and there are ~5 metrics. Growing a contract three gates depend on, for cosmetics, is over-engineering. |
| **Gave up** | The UI must know `delay_rate` is a percent — a presentation fact outside `calculator/`, a small crack in architecture Decision 1. Additive to close later. |

### D23 — One route; closed stage enum; a refusal is not a fault

|  |  |
| --- | --- |
| **Chose** | (a) One route — no plain-JSON sibling. (b) Stages are the enum `interpreting` → `querying` → `composing`, not graph node names. (c) S2.4 refusals are a normal `result` with `display: "unsupported"`, `data: null`, no digits; only faults emit `error`. |
| **Why** | (a) Two surfaces drift; a test frame-reader is cheaper. (b) Backend owns the milestone, UI owns the wording — what the design note asks for — and a graph rename cannot change user-visible text. (c) S2.4 asserts on refusals; the error path would make it assert on an exception. |
| **Gave up** | No plain-JSON `curl` shortcut; the enum is extended by hand; two response paths to test. **Deviation from the design copy:** its *"Counting across 359 orders…"* loses the figure, since a `stage` frame would have to send a number before the tool produced one. Reversible by giving `querying` a payload. |


### D24 — One provider everywhere: the Anthropic API on Haiku, reached through `init_chat_model`

|  |  |
| --- | --- |
| **Chose** | `claude-haiku-4-5-20251001` for dev, the recorded gates and PROD alike, constructed by `init_chat_model(LLM_MODEL, ...)` in the composition root so the provider is one `.env` value. Dep `langchain-anthropic` (1.6.1). Structure is enforced **by the provider** — real structured output on Classify, forced `tool_choice` on the Answer node's first call — not by validate-and-retry. |
| **Why** | Measured, not assumed. The local profile broke both LangChain structured-output paths (`parsed = None`, then `400 Invalid tool_choice type: 'object'`), which meant `architecture.md` Decision 3's *"the model must emit a tool call before it can reply"* was a prompt instruction rather than a guarantee. On Haiku it is a guarantee again. Routing measured at **14/14** on the S2.7 question list, twice, median 2.2 s per call — against 30 s allowed by S2.5. One provider also means the evidence files show the model the product actually ships on, which is what `tasks.md` asked for originally. |
| **Gave up** | Cost, which is what the local profile was for: `uv run pytest -m stack` now makes roughly 70 model calls and needs a funded key, so the correctness gate is no longer free or offline. A hosted model can also be updated between our run and a reviewer's, so the dated model id is pinned rather than an alias and every assertion is on structure, never wording. The static gate (`uv run pytest`) stays keyless, offline and free. |
| **Rejected** | **Keeping local for gates, Anthropic for PROD.** Two profiles means the recorded evidence is not the shipped behaviour, and the two disagree on the one capability the whole design leans on. |
| **Rejected** | **Our own provider wrapper.** `agent/` is already typed against `BaseChatModel` and LangChain already ships the factory; a third layer would own nothing. The real gap was that the composition root *named* `ChatAnthropic`, which `init_chat_model` closes. |
| **Caveat** | The abstraction hides the interface, not the capability. A provider that does not honour forced tool choice would pass startup and fail at the first question — so `create_llm` states the requirement in its docstring, S4.1's README lists it under Limitations, and the S2.x gates are what qualify a provider. Swapping is one line; trusting the swap costs a gate run. |

### D25 — A three-node StateGraph of our own, with `create_agent` as one node

|  |  |
| --- | --- |
| **Chose** | An outer `StateGraph` — `classify` → (conditional) → `answer` → `enforce` — where `answer` is the compiled `create_agent` of D6, added as a subgraph node. One `InMemorySaver` on the outer compile; `thread_id` = the request's `conversation_id`. State is exactly `agent-design.md`'s three fields. The refusal sentinel in `tools/` returns only its *reason*, so `enforce` is the single builder of the `unsupported` envelope. |
| **Why** | Fewer moving parts than the hand-written pipeline it replaced, and it converts two rules from "checked by a gate" to "cannot happen": the Classify gate becomes the conditional edge, and both refusal layers physically converge on `enforce`, which is what makes "both emit the identical envelope" (rule 4) structural. Verified by compiling and running it: node keys `['classify','answer','enforce']` under `stream_mode="updates"`, and the subgraph inherits the checkpointer. |
| **Gave up** | Two graph frameworks in one call path, so a stack trace crosses both. D6 is not reversed — `create_agent` still owns the tool loop. |
| **Deviation** | `agent-design.md`'s "no tool called → retry once, then unsupported" is not implemented as a retry. Forced `tool_choice` on the first model call makes bare prose illegal at the provider, so `enforce` refuses instead of retrying something that cannot happen. |

### D26 — `agent/` is handed its tools; the envelope rides the final message

|  |  |
| --- | --- |
| **Chose** | `agent/` imports LangChain and nothing from this package. Tools arrive as `Sequence[BaseTool]` and the dataset's column names as `Sequence[str]`, both from `main.py`. `enforce` returns the answer as an `AIMessage` whose `additional_kwargs["envelope"]` carries the result; `api/chat.py` reads it off the node update. |
| **Why** | Import-linter contract 1 forbids *chains*, not just direct edges — proven by planting `agent → tools → calculator`, which turned it BROKEN; injection leaves no edge at all. The envelope rides the message because the state is fixed at three fields, and because an answer and the explanation of it should not be able to drift apart in the checkpoint. |
| **Gave up** | `agent/` cannot name the tool it expects, so a missing tool is a runtime failure rather than an import error — bought back by S2.3/S2.7, which fail loudly on exactly that. `additional_kwargs` is a LangChain extension point, not a field of ours. |

### D27 — Forecast answers carry a typed `forecast` block

|  |  |
| --- | --- |
| **Chose** | `ChatResult` gains `forecast: {sku, horizon, window, total, recommended_stock, buffer_pct, methodology} \| null`; `explanation` keeps its exact S2 meaning (the history query, so the CSV oracle re-derives the history rows unchanged). All maths in the new `calculator/forecast.py`; the tool fills `{sku, horizon}` only. |
| **Why** | The card and the digit checks read the recommendation and methodology from fields; overloading `explanation` or prose would muddy the explainability contract the stack oracle re-derives rows from. |
| **Gave up** | One more wire field every other display carries as `null`. |

### D28 — History and prediction share one `rows` array under two value keys

|  |  |
| --- | --- |
| **Chose** | History rows stay byte-identical to the S1.2 shape (`{group, quantity}`); the N forecast rows use `{group, forecast}`. The dashed line's bridge point is derived in the frontend component, not sent. |
| **Why** | Which points are measured and which are projected is data, not inference; recharts draws both series from the same array with zero pivoting, and the history oracle needs no marker stripped. |
| **Gave up** | A segment-marker column; forecast rows show "—" in the reused data table's quantity column. |

### D29 — The `forecasting` stage is a LangGraph custom stream event

|  |  |
| --- | --- |
| **Chose** | The tool emits `{"stage": "forecasting"}` via `get_stream_writer` (no-op without a graph runtime); `api/chat.py` streams `stream_mode=["updates", "custom"]` **with `subgraphs=True`** and turns custom chunks into stage frames; subgraph *updates* are skipped whole, so no node name is ever inspected. Enum extended by hand in its four spelt-out places. |
| **Why** | The tool runs *inside* the answer node, so no node update can announce it; node sniffing would couple `api/` to `create_agent`'s internals (rejected once already, D23b). `subgraphs=True` is a measured necessity, not a choice: without it langgraph 1.2.11 swallows a custom chunk emitted inside `create_agent`'s inner graph (proven with a scripted fake model) — the approved fallback, recorded as a deviation. |
| **Gave up** | The stage's origin is the tool rather than the graph topology; every stream item now carries a namespace the route ignores. |

### D30 — Insufficient history refuses; the recommendation is buffer-only

|  |  |
| --- | --- |
| **Chose** | Fewer than 3 months with data (unknown SKU = 0) → the tool hands back the same single-key refusal-reason JSON as the refusal sentinel; the reason is digit-free, so it names the history problem without quoting the SKU code (codes carry digits). Recommendation = ⌈total × 1.15⌉, buffer only — the design mock's reorder-point line and "lead time 20 days" chip are dropped (spec review Q2). `REFUSAL_REASON_KEY` moved from `query_tool.py` to `schemas.py` so both refusing tools import one constant without a cycle. |
| **Why** | A 3-month average over fewer than 3 months is an invented figure; the mock's 20-day lead time is a constant the orders do not state (avg delivery time is transit, not procurement). |
| **Gave up** | Best-effort forecasts for 353 of the 355 SKUs the sparse dataset holds; the mock's reorder-point feature. |

### D31 — "A sku-missing forecast question is in scope" lives in the tool descriptions

|  |  |
| --- | --- |
| **Chose** | When the eval's "How much inventory should I plan?" was refused by the scope gate instead of drawing a `sku` follow-up, the fix went into the `forecast` and `ask_follow_up` tool descriptions (planning questions are in scope with or without a product code; a missing code is a follow-up, never a refusal). No prompt was edited. |
| **Why** | The classifier's prompt is rendered from the tools' own descriptions (D26), so a routing fact about a tool belongs on the tool — the same "fixes go into schemas, not prompts" rule Slice 2 measured. Verified 5/5 on the live model, with Q13/Q14 routing unchanged. |
| **Gave up** | Two slightly longer descriptions every turn pays tokens for. |

### D32 — Deployed as Amplify (static frontend) + one Lightsail container service (backend + ephemeral Postgres)

|  |  |
| --- | --- |
| **Chose** | Frontend built locally and pushed to Amplify by manual CLI deploy. Backend and Postgres run as two containers in one Lightsail container service (`small`, scale 1); the DB is ephemeral and a deploy-only backend entrypoint reruns the idempotent seeder on every boot, then starts uvicorn. Browser calls the Lightsail URL directly: `VITE_API_BASE_URL` at build time plus opt-in `CORS_ALLOW_ORIGINS` on the backend (empty = no CORS, so local one-origin behaviour is unchanged). Deploy tooling lives in gitignored `infra/deploy/`, local-only. |
| **Why** | Cheapest managed pair with public HTTPS on both ends (~$16/mo) and no domain to buy. The SSE chat stream stays unproxied — an Amplify rewrite would put CloudFront in front of a 30 s event stream. Ephemeral DB is safe because the dataset is 400 read-only rows the seeder rebuilds in seconds, and chat memory was already in-RAM (D25). |
| **Gave up** | DB persistence and the one-origin premise of D5 (two origins now, CORS opt-in). Owner-role credentials sit in the backend container's *env* for the boot-time seed — the API process still connects read-only, grants remain the enforcement (D4 intact). Secrets are plaintext in the Lightsail deployment (no secret store there); scale is pinned to 1. Reviewers cloning the repo don't get the deploy scripts — the live URLs and this entry are the record. |


---

## Slice 4 — Hardening & docs

### D33 — Secret scan (S4.2): zero-dep pattern test in the static set

|  |  |
| --- | --- |
| **Chose** | `tests/test_secret_scan.py`: walk `git ls-files`, grep tracked content for high-signal token shapes (`sk-ant-…`, `AKIA…`, `ghp_`/`github_pat_…`, private-key blocks, `lsv2_…`) and non-empty known-key assignments; assert `.env` is git-ignored. |
| **Why** | Same gate shape as D7 (exit-code verdict), zero new dependency, no false-positive baseline to maintain. |
| **Gave up** | Entropy-based detection of unknown token shapes. Rejected `detect-secrets` (its curated baseline can itself mask a secret) and `gitleaks` (per-machine binary — a reviewer's clone couldn't run the gate). |

### D34 — Env parity (S4.1): derived list, commented mentions count

|  |  |
| --- | --- |
| **Chose** | The doc-check derives the expected vars from the code at test time — `config.py`'s three Settings classes via `model_fields` plus a grep for `import.meta.env.<NAME>` — and asserts each appears in `.env.example`. Compose-derived vars land there as **commented** entries. |
| **Why** | Matches S4.1 literally ("every env var in code is in example file") and the list can never go stale, because it is derived rather than hardcoded. |
| **Gave up** | A smaller `.env.example` (~8 commented lines). Rejected: parity against `.env.example` ∪ compose defaults — reinterprets the pass-when and needs YAML parsing in the test. |

### D35 — README strictness: exactly 8 H2s, body ≤ 150 lines

|  |  |
| --- | --- |
| **Chose** | `tests/test_docs_gate.py` asserts the H2 set **equals** the 8 required headings in `docs/tasks.md` order (`###` subsections free), body ≤ 150 lines, each section ≤ 40. Deployment folds into Setup as an H3. |
| **Why** | Strictest reading of "contains exactly these headings" — the check cannot rot into "8 among 20", and "concise" becomes a gate instead of an opinion. |
| **Gave up** | Deployment as a top-level section; future README growth must consciously raise the cap (one-line test change + a log entry here). |

---

## Corrections made to the specs

All dated 08_23_2026. No acceptance criterion was loosened and no expected number changed.

- **Dataset path.** `data/mock_logistics_data.csv` → `infra/data/mock_logistics_data.csv` in `docs/tasks.md` and `spec.md`, following **D8**. Only the location moved.
- **Slice gates cited non-existent rows.** Three of the same typo in `docs/tasks.md`: `S1.6` (Slice 1 has S1.1–S1.5), `S2.7 + S2.8` (Slice 2 has S2.1–S2.7) and `S3.4` (Slice 3 has S3.1–S3.3). Confirmed typos; the gates now read **S1.5**, **S2.7** and **S3.3**, and the stale `→ S1.6`, `→ S2.8` and `→ S3.4` were dropped from the Order block so it agrees with the gate lines. No task text and no expected number changed — only the row a gate points at.
- **Slice 1 S1.4/S1.5.** Rewritten for **D9**: `/api/charts` → three parameterless `/api/dashboard/` routes, `/api/kpis` left top-level, and S1.5 now states the front-end composes the dashboard. A deliberate deviation from `architecture.md` §2, updated when the slice is implemented.
- **Import-linter contract split + evidence manifest.** Both consequences of **D18**/**D19**: the Slice 0 database contract in `pyproject.toml` was replaced by two contracts (details in D18), `architecture.md` §3 restated the rule in words (§3's Components table also moved "safe query building" off `data/`, since under D18 the calculator builds the statement), `tasks.md` S1.2's auto-check moved from `parametrized unit test` to `parametrized test … runs under pytest -m stack` — its pass-when is unchanged — and the S1.1/S1.2 oracle tests moved from `02_green_static.txt` to `03_green_stack.txt` in the spec's manifest. Recorded here because editing a passing contract should not be silent.
- **Chat transport and payload.** Four documents edited for **D20–D23**: `architecture.md` §2/§3/§5, `tasks.md` S2.5/S2.6, `requirement.md` decision table rows 5–6. S2.5 asserts the same schema and the same "chat total == KPI endpoint" equality, read out of the final `result` frame.
- **LLM provider switched to local for dev + gates — then reversed the same day** *(both dated 08_24_2026)*. The local profile (`qwen/qwen3.5-9b` via LM Studio, dep `langchain-openai`) was chosen at design review to save cost, with PROD on the Anthropic API. The tech lead reversed it hours later, before any agent code existed: one provider everywhere, the Anthropic API on Haiku. Recorded rather than deleted because the reversal is *why* **D24** above can claim provider-side enforcement — the local model's inability to honour forced tool choice is the measurement that makes the case. `tasks.md`, `agent-design.md` D6 and the Slice 2 spec were edited twice; no acceptance criterion or expected number changed on either pass.
- **`agent-design.md` gained D6** *(dated 08_24_2026)*. Tech lead chose the prebuilt `langchain.agents.create_agent` with prompt-controlled flow over the hand-built two-node StateGraph; the document's graph is now the behavioral contract enforced by a post-hoc wrapper + the S2.x gates, with the escalation path (middleware → custom graph) recorded in D6.
- **Suggested question chips removed** *(dated 08_24_2026)*. Tech-lead scope cut: `tasks.md` S2.6 dropped "suggested chips" and its "≥3 chips, click fills input" pass-when; the Out-of-scope note now lists chips as bonus. Slice 2 spec updated to match. FollowUp `options[]` (agent-design.md) are unaffected. No number changed.
- **`spec.md` S0.3 status labels.** The spec's `304/55/27/11/3` had the right numbers with swapped labels; the CSV gives `delivered 304, delayed 55, in_transit 27, exception 11, canceled 3`. Text corrected; the test derives the mapping from the CSV at runtime, so it cannot drift again.
- **LangSmith tracing, env vars only** *(dated 08_24_2026)*. Dev-tool observability for the chat agent: `LANGSMITH_TRACING/_API_KEY/_PROJECT` (project `dean-demo`) added to compose with `:-` defaults so the keyless one-command start (S0.5) holds. Zero code: `langsmith` already ships with `langchain-core` and LangChain auto-traces when the vars are set. Rejected typed `LlmSettings` fields as over-engineering.

---

## AI usage disclosure

Built with heavy use of an AI coding assistant (Claude, via Claude Code). It read the
specifications, proposed the options above with their trade-offs, and wrote the code, tests
and container configuration after a human picked between them. Every non-trivial decision
here was reviewed by the human tech lead and in two cases (D4a, and the initial D4 choice)
overruled or changed. Factual claims about third-party behaviour were verified by running
them, not recalled — the PostgreSQL findings in D4 come from a probe against a live
`postgres:17-alpine`, and the dataset numbers from an independent read of the CSV. All
acceptance criteria were executed; run logs are held with the task in our internal tracker,
and anyone can reproduce them with the two commands below.

---

## Verifying this repo

Every acceptance criterion is a test that shells out and asserts exit 0, so "green" is a
command's verdict rather than a human claim. From `src/backend/`:

```bash
uv run pytest             # 27 static gates
uv run pytest -m stack    # 6 gates against the live compose stack
```

The second set brings the stack up itself. Run `docker compose down -v` first for a cold
start — `infra/db/init/01_roles.sh` executes only on an empty volume, so a warm run proves
less than it appears to.

The expected numbers (400 rows; `delivered 304, delayed 55, in_transit 27, exception 11,
canceled 3`) are derived in `tests/conftest.py` by re-reading
`infra/data/mock_logistics_data.csv` with the standard library, never from the seeder. If the
seeder and the oracle ever disagree, the tests fail.

- **Planted-violation gate on Windows** *(dated 08_25_2026, approved at the Slice 3 review)*. `tests/test_planted_violation.py::_run_lint` gained `encoding="utf-8"`: the default cp1252 pipe decoding crashed the reader thread on import-linter's non-ASCII output, leaving `stdout=None` and a TypeError. One line; a pre-existing environment failure, no criterion changed.
