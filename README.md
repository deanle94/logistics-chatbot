# logistics-chatbot

AI-powered logistics analytics: a KPI dashboard plus a chat agent over one dataset of
400 orders. Core rule everywhere: **the AI never computes an answer** — it picks a tool
and fills in structured parameters; PostgreSQL does the arithmetic.

## Setup

Prerequisites: Docker (compose v2), [uv](https://docs.astral.sh/uv/), an Anthropic API key.

```bash
cp .env.example .env    # put your Anthropic key in .env — it is git-ignored, never committed
docker compose up       # db + one-shot seeder + API :8000 + frontend :5173
```

Every acceptance criterion is a pytest that asserts an exit code. From `src/backend/`:

```bash
uv run pytest           # static set: lint, types, layer contracts, docs, secrets, frontend build
uv run pytest -m stack  # live set: brings the stack up, checks the numbers (billable LLM calls)
```

`verify_all` — everything green in one exit code — is, verbatim:

```bash
docker compose down -v  # cold start: role provisioning only runs on an empty volume
uv run pytest -m ""
```

The cold start matters: a warm volume skips `infra/db/init/`, so a warm pass proves less.

### Live deployment

- Frontend: <https://main.d3pn3cxdlrbarv.amplifyapp.com> (AWS Amplify)
- API: <https://logistics-svc.5zz1a2nkpxpzc.ap-southeast-1.cs.amazonlightsail.com>
  (Lightsail container service; the DB is ephemeral and reseeded from `infra/data/` on boot)

Deploy tooling is local-only by design — decision-log **D32** is the record of how it runs.

## Architecture

Five layers, each a package whose boundaries are machine-enforced by import-linter
contracts: `agent/` interprets the question, `tools/` validates parameters,
`calculator/` owns every formula as an unexecuted SQL statement, `data/` executes it,
`api/` serves the results. AI interpretation and data computation can never import each
other — checked on every test run, not promised. Full design, with diagrams:
[docs/architecture.md](docs/architecture.md).

## AI approach

A tool-calling agent: the LLM emits structured parameters (metric, filters, group-by —
or SKU + horizon for forecasts), our code builds a validated SQL query. No AI-generated
SQL is ever executed. Structure is enforced by the provider — real structured output on
classification, forced tool choice on answers (decision D24) — not by prompting and hoping.
Graph and prompts: [docs/agent-design.md](docs/agent-design.md).

Try:

- "What was the delay rate per carrier last month?"
- "Forecast demand for PENCIL-0213 over the next 3 months"
- "How much stock should I plan for CRAYON-0017?"

(Both SKUs have ≥ 3 months of order history in the dataset.)

## Key decisions

The three decisions from [docs/architecture.md](docs/architecture.md) §4, where each
trade-off is recorded in full; the running record of every later decision is
[docs/decision-log.md](docs/decision-log.md).

| Decision | In short |
|---|---|
| 1 — One calculator module owns every formula | Routes and tools only call it — one home per business definition. |
| 2 — One service for dashboard and chat | The agent must be Python, so the whole stack is Python and the calculator is a plain in-process call. |
| 3 — AI never computes | The agent only outputs a tool choice and structured parameters; every number traces back to a tool run over the real dataset. |

## Assumptions

- Rates count only finished orders (delivered + delayed) — spec didn't specify a denominator.
- Orders missing a delivery date are excluded from delivery-time averages — spec didn't specify.
- Forecast = 3-month moving average; stock advice adds a 15% safety buffer — spec didn't
  specify a method or buffer.
- Dataset is the single, read-only source of truth — spec didn't name another source.

## Limitations

- The chat answers only questions about the seven order metrics (counts, delivered/delayed
  orders, delay/on-time rate, average delivery time, quantity — filtered or grouped) and
  per-SKU demand forecasts.
- Anything outside that subset gets an explicit "unsupported" reply — never a guessed answer.
- Each question stands alone — the chat keeps no conversation history.
- English questions only — other languages are untested.

## Future improvements

- Suggestion chips after each answer.
- Token-limit usage tracking.
- A critique node validating the answer is built from the computation.
- RAG: user uploads + retrieval.
- An agent eval framework.
- LLM-generated conversation titles.
- `conversation_histories` with Postgres as the pointer DB for the agent.

## AI-usage disclosure

Built with heavy use of an AI coding assistant (Claude, via Claude Code) under a
spec-and-gate workflow: it proposed options with trade-offs, and wrote the code and tests
after a human picked between them. Every non-trivial decision was reviewed — and in some
cases overruled — by the human tech lead, and is recorded in
[docs/decision-log.md](docs/decision-log.md). Claims about third-party behaviour were
verified by running them, not recalled; all acceptance criteria run as the gates above.
