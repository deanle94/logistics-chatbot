---
status: draft
created: 08_26_2026
updated: 08_26_2026
---

# Slice4 Hardening Docs

## Your Role

Senior Software Engineer focused on delivery hardening — reviewer-facing docs, secret hygiene, one-shot verification gates. Writing style: concise, clear, plain language. Short sections. No walls of text.

## Intent

- **Problem:** README has only 2 headings today (`# logistics-chatbot`, `## Deployment`) — the 8 the assessment requires are missing. Nothing machine-checks docs or secrets, and "everything green" still takes two commands plus human memory.
- **Approach:** Extend the existing gate pattern (decision-log: each check = a pytest test that shells out and asserts exit 0). Doc-check and secret scan become tests in the static set. `verify_all` is already decided: `uv run pytest -m ""` runs static + stack in one exit code — wrap it in a tiny script only if step 3 shows a script adds value (e.g. ordering, cold-start).
- **Idea:** README written last, from what already exists — it *links* to `docs/decision-log.md` and `docs/architecture.md`, never duplicates them. That is what keeps it short.

## Acceptance Criteria

Source: `docs/tasks.md` → Slice 4 table (S4.1–S4.3). Every criterion = a command exits 0.

- **S4.1 README + env example + decision log** — doc-check test passes: README contains exactly these headings — Setup, Architecture, AI approach, Key decisions, Assumptions, Limitations, Future improvements, AI-usage disclosure — and every env var read by the code appears in `.env.example`. Runs under `uv run pytest` (no stack needed).
- **S4.2 No secrets committed** — secret scan over the repo exits 0; `.env` is git-ignored (already true — keep it that way and assert it).
- **S4.3 `verify_all` one-shot gate** — one command, exit 0 == every check in this repo green (static + stack), per decision-log: `verify_all` = `pytest -m ""`. — **Slice gate.**
- **Conciseness (user rule, proxy check)** — README body ≤ *[150 lines — placeholder, confirm at step 3]*; each of the 8 sections renders on one screen. Enforced by the doc-check test so "concise" is a gate, not an opinion.
- **Regression** — Slice 0–3 gates stay green: `uv run pytest` and `uv run pytest -m stack` both exit 0 after the change.

## Steps

1. Define the eval functions first — the doc-check test (8 headings + env-var parity + line cap), the secret-scan test, the `verify_all` invocation. Run them against today's repo so they **FAIL** (README is missing 6+ headings → guaranteed red).
2. Scan: README, `.env.example`, `config.py` + compose file (which env vars the code actually reads), `docs/decision-log.md`, the existing gate tests (their shell-out pattern), `.gitignore`.
3. Propose via Lavish: README outline (per-section one-liners), secret-scan mechanism options (≥2, with trade-offs — e.g. dedicated scanner dep vs. pattern test), `verify_all` form (bare `pytest -m ""` vs. thin script). Wait for approval; go back and forth.
4. Implement when approved. New decisions land in `docs/decision-log.md` as chose / why / gave up — precise, main reason only.
5. Cold stack (`docker compose down -v`), run `verify_all`, capture every artifact in the manifest below into this spec's `evidence/` folder. Pass → attach proof, done. Fail → fix and re-run.

### Evidence manifest (all four required)

| File | Command / source | What it proves |
|---|---|---|
| `01_red_baseline.txt` | step-1 evals on today's repo | the new gates can fail |
| `02_verify_all.txt` | the S4.3 one-shot command | everything green in one exit code |
| `03_secret_scan.txt` | the S4.2 scan | no secrets in the repo |
| `04_readme_render.png` | rendered README (top + headings visible) | the 8 sections exist and read short |

---

> **!!! IMPORTANT RULES !!!**
> - **Evidence of completion is mandatory.** No step or the task is "done" without proof the step-1 eval function actually passed when run. Use the form that demonstrates it: a screenshot or screen recording for UI, full test-run logs (command + pass/fail summary) for backend/test work, query output or sample rows for data, a successful run/pipeline log for infra. "It works" / "tests pass" with no artifact does not count.
> - **Docs must be concise, clear, easy to understand.** Short sentences, tables over prose, link to existing docs instead of repeating them. If a section runs long, cut it.
> - **AI-usage disclosure is required content**, not optional — one honest paragraph in the README (CLAUDE.md rule 1).
> - **DO NOT touch application code.** This slice is docs + gates only. Slice 0–3 tests are the regression net; both existing gate sets must stay green.
> - **Honor prior decisions:** `verify_all` = `pytest -m ""` (decision-log). Don't invent a parallel runner without a step-3 decision.
> - No secrets committed; `.env` stays git-ignored; data stays read-only.
> - **DO NOT invent anything outside** `docs/tasks.md` Slice 4. Simple and correct beats complete. Anything open goes through step 3, not through code.
> - Every step-3/4 decision → `docs/decision-log.md` as **chose / why / gave up**, concise (CLAUDE.md rule 10).
> - If anything is unclear → ask. No hidden assumptions.
