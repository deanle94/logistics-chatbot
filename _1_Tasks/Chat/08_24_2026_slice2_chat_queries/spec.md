---
status: planned
created: 08_24_2026
updated: 08_24_2026
---

# Slice2 Chat Queries

## Your Role

Senior Full Stack + AI Engineer (Python / LangChain / LangGraph / FastAPI + React / TypeScript), focused on grounded LLM output — every digit traceable to a tool result

## Intent

- **Problem:** The dashboard serves fixed queries only. Nothing interprets natural language: `agent/` and `tools/` are empty folders, `POST /api/chat` does not exist, and the front-end has no chat page. Requirement §2.2 (🔴 natural-language queries), §2.3 (dynamic display selection) and §2.4 (🟡 explainability) are unmet.
- **Approach:** Follow `docs/agent-design.md` — **finalized, not up for debate**: two LLM nodes (Classify gate → Answer node), all LLM output structured, the Answer node's only 3 legal outputs are a whitelisted tool call, a `FollowUp`, or the `unsupported` refusal envelope. Transport and payload are already decided (decision-log **D20–D23**: SSE `stage`* → one `result` → `done`; one envelope; closed stage enum; refusal ≠ fault). What those documents left open was decided **at spec review** (Lavish session, 08_24_2026) — see the resolved Open items below. Implementation shape amended by `agent-design.md` **D6**: the Answer side runs on `langchain.agents.create_agent`, prompt-controlled; the two-node graph stays the behavioral contract, enforced by a post-hoc wrapper + the gates, with a pre-decided escalation path (middleware → custom graph).
- **Idea:** Slice 2 adds **zero calculator work** (D10 planned exactly this): `tools/` wraps the existing S1.2 engine and owns validation + display-type selection; `agent/` holds the two-node LangGraph; `api/` adds the SSE route; the front-end adds the chat page per `docs/design/Chat.dc.html`, `States.dc.html`, `AnswerTypes.dc.html`, `Explainability.dc.html`.

## Acceptance Criteria

Source: `docs/tasks.md` → Slice 2 table (S2.1–S2.7) + `docs/agent-design.md`. Every criterion = a command exits 0. Agent tests call a **real LLM — the Anthropic API, `claude-haiku-4-5-20251001`** (tech-lead decision O3a, revised 08_24_2026; the intermediate "local qwen via LM Studio" profile was reversed the same day, correction logged) — assert structure (tool, params, digits ⊆ tool output) — never wording — and are retried ≤2×.

- **S2.1 Parameter validation with whitelists** — unknown metric or group-by rejected; injection-looking strings rejected; valid input round-trips unchanged. This whitelist is load-bearing from day one: it is the first time a user-influenced string approaches the query builder (D10). *(unit test)*
- **S2.2 Query tool** — returns result + rows + echoed params + display type. Display rule holds: single number → `stat`, time series → `line`, category comparison → `bar`, on-time vs delayed → `stacked`. Echoed params == input, field for field. *(unit test)*
- **S2.3 Agent answers from the tool, never from memory** — 4 canonical questions each produce: expected tool + metric + group-by; a tool call **before** any text; **no digit in the prose that is absent from the tool result**. *(agent test, real LLM)*
- **S2.4 Out-of-scope refusal** — "weather", "write a poem" → `display: "unsupported"`, `data: null`, no digits. Both refusal layers (Classify: out-of-domain; Answer: in-domain but unsupported params) emit the identical envelope (D23). *(agent test, real LLM)*
- **S2.5 `POST /api/chat` over SSE** — content-type `text/event-stream`; `stage`* frames from the closed enum, then exactly **one** `result` frame (answer + display + data + rows + explanation) validating against its schema, then `done` (D20, D23). "Total orders" asked via chat == `GET /api/kpis`, digit for digit. A refusal arrives as a `result`, not an `error`. Completes < 30 s. *(API test + the shared frame reader all Slice 2 gates use)*
- **S2.6 Chat page** — input, progress states, answer card (stat / line / bar / stacked), explainability panel, data-table toggle. Gates: ≥1 progress line rendered before the answer; a carrier question renders a bar chart; the panel shows metric + group-by; table row count == the rows the API returned. Layout follows `docs/design/` (files above). *Suggested question chips cut by the tech lead 08_24_2026 (were in tasks.md S2.6; correction logged). FollowUp `options[]` still render — that is `agent-design.md`, not the chips feature.* *(Playwright against the live compose stack)*
- **S2.7 Routing eval set** — ≥12 questions; ≥11/12 correct tool + params; 0 invented digits across the set; a report file is written. *(eval test — this is the slice gate)*
- **S2.8 FollowUp** — an ambiguous in-domain question (e.g. no time range) yields a structured `FollowUp {missing_info, question, options[]}`; the validator rejects any digit in `question`; the user's reply re-enters the graph at Classify and resolves against conversation context (agent-design rule 7). *[Added at spec review, confirmed by the tech lead 08_24_2026 — not a `docs/tasks.md` row. `agent-design.md` makes FollowUp one of only 3 legal outputs and its no-digit validator load-bearing; a legal output with no gate is unverified.]* *(agent test, real LLM)*

**Slice gate:** S2.7 green (`docs/tasks.md`, corrected 08_23_2026 — Slice 2 has no S2.8 row there; S2.8 above is spec-level).

**Oracle rule:** unchanged — expected numbers come from an independent read of `infra/data/mock_logistics_data.csv` or `docs/business-definition.md`, never from the code under test. The chat gains one extra oracle for free: the already-verified dashboard endpoints (S2.5's "chat == KPI endpoint").

## Decisions already taken (not revisited here)

D20–D23 in `docs/decision-log.md`, taken at design review: SSE transport with advisory stages; one envelope per answer; no `columns` metadata; one route, closed stage enum, refusal-is-not-a-fault. `docs/agent-design.md` — the graph, the state, the 3 legal outputs, the two refusal layers, the 7 strict rules — is finalized input to this spec.

## Open items — all resolved at spec review, 08_24_2026

| #   | Open item                                                                                                                                                                                                                                                                                                                                     | Why it is genuinely open                                                                                                                                         |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| O1  | **FollowUp on the wire.** Which frame carries it — a `result` with its own `display`, or a new frame type?                                                                                                                                                                                                                                    | `agent-design.md` defines the object; D20–D23 define the stream; neither says how the two meet. S2.6's chips ("options rendered as chips") depend on the answer. |
| O2  | **Conversation memory transport.** `AgentState.messages` is "loaded from checkpointer" and Classify reads the last 10 messages — so `POST /api/chat` needs a conversation identifier S2.5's schema never names. Also *which* checkpointer: the app's DB role is `SELECT`-only (D4), so a Postgres checkpointer cannot write through `app_ro`. | Design implies state; API contract is stateless as written. The read-only constraint rules options in or out.                                                    |
| O3  | **Claude wiring.** Model id, structured-output mechanism (LangChain tool-binding vs structured output), prompt shape, where the ≤2× retry lives.                                                                                                                                                                                              | `technical-stack.md` names LangChain + LangGraph but no model id; must be verified against installed versions (context7 / local probe), not memory.              |
| O4  | **Which gate set the agent tests join.** They need a live DB **and** an API key — likely `-m stack` or a third marker, so a keyless machine still gets a green static gate.                                                                                                                                                                   | Gate placement is what keeps `uv run pytest` runnable for a reviewer with no key.                                                                                |
| O5  | **The 4 canonical questions (S2.3) and the ≥12 eval questions (S2.7).**                                                                                                                                                                                                                                                                       | Defined at step 1 with their expected tool + params each, before any agent code.                                                                                 |

**Status (08_24_2026, decided with the tech lead via Lavish review):** O1 = **A** (FollowUp rides the `result` frame: `display: "follow_up"` + optional `follow_up {missing_info, options[]}` field) · O2 = **A** (LangGraph `InMemorySaver`, client-generated `conversation_id` → `thread_id`) · O3a = **Anthropic API**, `claude-haiku-4-5-20251001`, dep `langchain-anthropic` (verified 1.6.1), reached through `init_chat_model` so the provider is one `.env` line (`LLM_MODEL`). Forced tool choice and real structured output both work, so enforcement is **provider-side**, not validation-plus-retry — that workaround existed only because LM Studio returned `400 Invalid tool_choice type: object`. Probed: **14/14** on the approved question list below, twice, median 2.2 s per call · O4 = **A** (agent tests under `-m stack`, hard-fail when the LLM provider is unreachable) · O3b = **`langchain.agents.create_agent`, prompt-controlled** (tech lead; verified in langchain 1.3.16) — Classify stays a separate structured call; the 3 legal outputs are the agent's only tools (sentinels for FollowUp/Refuse); rules enforced by a post-hoc wrapper + gates, escalation middleware → custom graph recorded in `agent-design.md` D6. One provider everywhere — dev, gates and PROD — so the recorded evidence is the same model the product ships on · O5 = **approved** — question lists in the next section, dates pinned to the dataset's verified 2025 range. Full *chose / why / gave up* entries land in `docs/decision-log.md` at step 4.

## Question lists (O5 — approved 08_24_2026)

Dataset verified: `order_date` spans **2025-01-01 → 2025-12-30**; regions `EU, UK, US-C, US-E, US-W`. Date-bearing questions pin absolute 2025 ranges — a relative range anchored to *today* resolves outside the data (valid per D15, useless as an eval). Rule 3's symbol resolution (`last_3_months` → dates) is covered by a **tools-layer unit test**, not an eval question.

**Canonical 4 (S2.3)** — one per display type:

| # | Question | Expected tool + params | Display | Oracle |
|---|---|---|---|---|
| 1 | "How many orders do we have in total?" | query · order_count · none | stat | 400 == `/api/kpis` |
| 2 | "Show delayed orders by week from October to December 2025" | query · delayed · week · 2025-10-01..2025-12-31 | line | CSV re-read (Oct/Nov/Dec = 26/24/24 orders) |
| 3 | "Which carrier has the highest delay rate?" | query · delay_rate · carrier | bar | GLS 28.6 top |
| 4 | "Compare on-time vs delayed orders per month" | query · params == delivery-performance route | stacked | Σ 359 |

**Eval set (S2.7)** — the 4 above plus:

| # | Question | Expected |
|---|---|---|
| 5 | "How many orders were delivered?" | query · delivered · none → stat (304) |
| 6 | "What is the average delivery time?" | query · avg_delivery_time · none → stat (3.8 days) |
| 7 | "Show order volume per month in 2025" | query · order_count · month → line (Σ 400) |
| 8 | "Total quantity shipped by product category" | query · quantity · product_category → bar |
| 9 | "Delay rate by warehouse" | query · delay_rate · warehouse → bar |
| 10 | "How many orders from US-E in July 2025?" | query · order_count · region=US-E · 2025-07 (oracle computed at step 1) |
| 11 | "What's the weather in Hong Kong?" | refusal — Classify, out-of-domain |
| 12 | "Write a poem about logistics" | refusal — Classify, out-of-domain |
| 13 | "Delayed orders by destination city" | refusal — Answer, unsupported group-by |
| 14 | "Show me the delayed orders trend" (no time range) | FollowUp · missing_info = time range |

**Pass bar:** at most 1 miss across the 14 (tasks.md's ≥11/12 ratio).

## Steps

1. Define the eval functions first — one automated check per AC: the S2.1/S2.2 unit tests, the S2.3/S2.4/S2.8 agent tests (real Anthropic API, structure-only assertions, ≤2× retry), the S2.5 API test + shared SSE frame reader, the S2.6 Playwright test, the S2.7 eval runner + report writer over the approved 14-question list above. Write them so they **FAIL** against today's code.
2. Scan `docs/agent-design.md` (incl. D6), `docs/architecture.md` §3–5, decision-log D20–D23, the four chat design files, `rules/python-coding-rules.md`, `rules/react-coding-rules.md`, and the existing S1.2 engine + `tests/conftest.py` fixtures.
3. O1–O5 are already resolved (spec review, above). Propose via Lavish only what is still open: the system prompt text (rules 1–7 in words), final Pydantic shapes + SSE serialization, and the front-end component split under `rules/react-coding-rules.md`. Wait for approval. Ready to go back and forth.
4. Implement when approved. Write the step-3 decisions into `docs/decision-log.md` under Slice 2 in full *chose / why / gave up* form; update `docs/architecture.md` only if a decision deviates from it.
5. Run both gate sets (`uv run pytest`, `uv run pytest -m stack`) from a cold stack (`docker compose down -v` first) and capture **every artifact in the manifest below** into this spec's `evidence/` folder. Pass → attach proof, done. Fail → fix and re-run.

### Evidence manifest (all eight required)

Naming follows Slice 1's `evidence/` folder. A missing file means the slice is not done.

| File | Command / source | What it proves |
|---|---|---|
| `01_red_baseline.txt` | step-1 evals on today's code | the tests can fail — a green suite that never went red proves nothing |
| `02_green_static.txt` | `uv run pytest` | code well-formed, layers hold (import-linter: `agent/` reaches `calculator/`/`data/` only through `tools/`), frontend build/type-check/lint |
| `03_green_stack.txt` | `uv run pytest -m stack` | the S2.1–S2.8 gates against the live stack and the real Anthropic API (O4 = A) |
| `04_chat_sse_capture.txt` | `curl -N` POST `/api/chat` from the host — one data question **and** one refusal | the raw frames: `stage`* → one `result` → `done`; the refusal as a `result` with `display: "unsupported"`; the reviewer can check every digit against the CSV |
| `05_backend_log.txt` | `docker compose logs backend`, same window, health-noise filtered | the answers came from the real service and real tool executions — no 500s, no stack traces |
| `06_chat_answer_screenshot.png` | Playwright full-page | answer card with chart + explainability panel showing metric + group-by, per the design files |
| `07_chat_refusal_screenshot.png` | Playwright | the `unsupported` state rendered as a normal answer |
| `08_eval_report.md` | the S2.7 runner | per-question verdicts over the approved 14 questions (at most 1 miss — the ≥11/12 ratio), 0 invented digits — S2.7 requires the report itself |

> `04` and `05` are both required and not interchangeable (same reasoning as Slice 1): the log proves the request was served, the captured frames prove the numbers were right. Capture them from the same run.

---

> **!!! IMPORTANT RULES !!!**
> - **Evidence of completion is mandatory.** No step or the task is "done" without proof the step-1 eval function actually passed when run. Use the form that demonstrates it: a screenshot or screen recording for UI, full test-run logs (command + pass/fail summary) for backend/test work, query output or sample rows for data, a successful run/pipeline log for infra. "It works" / "tests pass" with no artifact does not count.
> - **For this slice, evidence means all eight files in the manifest above** — including the raw SSE capture and both screenshots. Test output alone is not sufficient.
> - **`docs/agent-design.md` is finalized.** Its 7 strict rules bind every line of agent code — especially: every digit in prose exists in the tool result; free text only *after* a tool result; relative dates leave the LLM as symbols and the **tools layer** resolves them; both refusal paths emit the identical envelope; Classify context = last 10 messages, no more.
> - **The AI never computes and never writes SQL.** It picks a tool and fills whitelisted structured params (Pydantic). `tools/` validates against the whitelist **before** anything runs (S2.1). No AI-generated string reaches the query builder unvalidated.
> - **DO NOT touch `calculator/`.** Slice 2 adds zero calculator work (D10). If a question needs a metric the engine lacks, stop and raise it — that is a scope change, not a workaround.
> - **DO NOT put a formula in `agent/`, `tools/` or `api/`** — architecture Decision 1. Display-type selection (S2.2) is presentation routing, not a formula; it lives in `tools/`.
> - **`agent/` imports nothing from `calculator/` or `data/`** — only `tools/` (agent-design rule 5). The import-linter contracts must stay green.
> - **Agent tests call the real Anthropic API** (`claude-haiku-4-5-20251001` — O3a) — assert structure (tool, params, digits ⊆ tool output), never wording; retried ≤2×. `LLM_MODEL` and `ANTHROPIC_API_KEY` come from env (`.env.example` documents them, the key blank; S4.1 will gate this); tests **hard-fail** when the provider is unreachable or unauthorised — a skip that reads as green is what D19 rejected. **The key is never committed**: `.env` is gitignored, the setting is a `SecretStr`, and the evidence files are scanned for it before they are written. `uv run pytest -m stack` now costs money (~70 model calls per full run); the static gate stays keyless and offline.
> - **DO NOT break the Slice 0 + Slice 1 gates** (140 static + 125 stack). They are the regression net.
> - Data is **read-only**. The API connects as `app_ro`; no write path — which constrains the checkpointer choice (O2).
> - **DO NOT invent anything outside `docs/agent-design.md`, `docs/architecture.md`, `docs/requirement.md`, `docs/design/`, D20–D23.** Simple and correct beats complete. Open items go through step 3, not through code.
> - Write every step-3 decision as **chose / why / gave up** in `docs/decision-log.md`. Decisions without reasoning lose points even when the decision is right.
> - Python code MUST follow `rules/python-coding-rules.md`; React code MUST follow `rules/react-coding-rules.md` (CLAUDE.md rules 5 and 6).
> - If anything is unclear → ask. No hidden assumptions.
