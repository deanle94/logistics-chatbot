---
status: implemented
created: 08_23_2026
updated: 08_23_2026
---

# Slice0 Skeleton

## Your Role

Senior Full Stack Engineer (React / TypeScript + Python / FastAPI), with Docker Compose experience

## Intent

- **Problem:** Repo has docs + dataset (`infra/data/mock_logistics_data.csv`, 400 rows) but zero code. Nothing runs. Later slices (dashboard, chat, forecast) need a running, layered skeleton to build on.
- **Approach:** To be decided during step 3 — per `docs/tasks.md`: "no implementation choices here; per task we'll pick options + trade-offs later". Must stay inside `docs/architecture.md` (§3 folder layers + import rules) and `docs/technical-stack.md`.
- **Idea:** No assumptions yet. Known constraints only: one Python service + one PostgreSQL (read-only role), React + shadcn front-end, everything up via `docker compose up`.

## Acceptance Criteria

Source: `docs/tasks.md` → Slice 0 table (S0.1–S0.6). Every criterion = a command exits 0. No eyeball checks.

- **S0.1 Back-end boots** — `GET /health` → 200 and body reports DB reachable. Config read from env vars only. *(API test + DB ping test)*
- **S0.2 Layer boundaries** — folders `agent/ api/ tools/ calculator/ data/` exist under `src/<package>/` (coding rule 14); `ruff check` + `ruff format --check` + `mypy` exit 0 (rules 1–2); import-boundary lint passes (`agent/` never imports `calculator/`/`data/`; `calculator/`+`data/` never import `agent/`; only `data/` touches DB); a planted violation makes the lint FAIL. *(structure test + lint + planted-violation test)*
- **S0.3 Dataset loaded read-only** — DB has exactly 400 rows; status counts delivered/delayed/in_transit/exception/canceled = 304/55/27/11/3 *(label order corrected 08_23_2026 against the CSV: the original text swapped `in_transit` and `delayed`; the numbers were always right)*; a write via app role is rejected; running the seed twice → still 400. *(DB test)*
- **S0.4 Front-end boots** — React app with shadcn initialised + HTTP client; build, type-check, lint all exit 0; page renders the backend status text fetched from `/health`. *(browser test)*
- **S0.5 Compose runs everything** — `docker compose up` → front-end 200, back-end `/health` 200, DB row count 400. *(compose smoke script)*
- **S0.6 Tech-stack conformance** — back-end deps include FastAPI, SQLAlchemy, Pydantic, LangChain, LangGraph; front-end deps include React, shadcn, axios. *(dependency check script)*

**Slice gate:** S0.5 + S0.6 green.

**Oracle rule:** expected numbers (400, 304/55/27/11/3) come from an independent read of the CSV — never from the code under test.

## Steps

1. Define the eval functions first — one automated check per AC above (tests + smoke/dep scripts). Write them so they FAIL on the empty repo.
2. Scan `docs/architecture.md` (§3 folders, §4 decisions), `docs/technical-stack.md`, `docs/business-definition.md`, the CSV header, and `CLAUDE.md` rules.
3. Propose the solution via the Lavish skill (≥2 options per non-trivial choice: e.g. import-boundary enforcement tool, seeding strategy, read-only role approach, compose layout). Each option: what we choose / why / what we give up. Wait for approval. Ready to go back and forth.
4. Implement when approved. Record chosen trade-offs in the decision log for the README (Slice 4 needs them).
5. Run all eval functions + `docker compose up` smoke and capture output as evidence. Pass → attach proof, done. Fail → fix and re-run.

---

> **!!! IMPORTANT RULES !!!**
> - **Evidence of completion is mandatory.** No step or the task is "done" without proof the step-1 eval function actually passed when run. Use the form that demonstrates it: a screenshot or screen recording for UI, full test-run logs (command + pass/fail summary) for backend/test work, query output or sample rows for data, a successful run/pipeline log for infra. "It works" / "tests pass" with no artifact does not count.
> - **Python code MUST follow `rules/python-coding-rules.md`** (14 rules: type hints, ruff, no bare except, DI, context managers, logging not print, src/ layout + `pyproject.toml`, etc.). Rules 1, 2, 14 are also checked by the S0.2 eval.
> - **DO NOT** add business logic, KPIs, agent, or tools code — Slice 0 is structure only. Folders may hold only placeholders / `__init__.py`.
> - **DO NOT** invent anything outside `docs/architecture.md`, `docs/requirement.md`, `docs/technical-stack.md`. Don't over-engineer: simple and correct beats complete.
> - **DO NOT** commit secrets. Use `.env.example` + env vars; `.env` git-ignored.
> - Data is **read-only**. DB app role must not have write privileges.
> - Write down every key decision as: chose / why / gave up (spec scores reasoning, not completeness).
> - Disclose AI usage while building (one honest paragraph, goes into README later).
> - If anything is unclear → ask. No hidden assumptions.
