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

Architecture decisions only; every entry in [docs/decision-log.md](docs/decision-log.md)
records what we chose, why, and what we gave up.

| Decision | In short |
|---|---|
| Layer boundaries as import contracts | The architecture's rules are `import-linter` config checked by exit code; indirect leaks fail too. |
| D9 — three fixed dashboard routes | Parameterless routes; chart composition stays in the frontend, each chart gets its own oracle. |
| D18 — the calculator owns the SQL | `calculator/` builds an unexecuted statement, `data/` runs it: one home per formula while PostgreSQL aggregates. |
| D24 — provider-enforced structure | One model everywhere; the model must emit a tool call before it can reply — a guarantee, not a prompt. |
| agent-design D6 — prebuilt agent as one node | LangChain's `create_agent` owns the tool loop inside our three-node graph, instead of a hand-built loop. |

## Assumptions

- `infra/data/mock_logistics_data.csv` is the single, read-only source of truth. Tests
  re-derive every expected number from it independently of the code under test.
- The default credentials in `docker-compose.yml` are deliberate: S0.5 requires
  `docker compose up` to work on a fresh clone. They only ever reach a local container;
  any non-local deployment overrides all of them.
- The stack gate assumes a funded Anthropic key in `.env`.

## Limitations

- The provider must honour forced tool choice. One that does not would pass startup and
  fail at the first question (D24 caveat); the S2.x gates are what qualify a provider.
- The hosted DB is ephemeral — reseeded on every boot, nothing persists between deploys.
- `uv run pytest -m stack` is online and billable (~70 model calls per run).
- No authentication: every endpoint, local and hosted, is public.

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
