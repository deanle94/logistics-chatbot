# Approved solution — Slice 4 Hardening & Docs

Approved by the user via Lavish review on 08_26_2026 ("approved and go ahead").
Decisions 1–3 were explicitly queued; Decision 4 was approved as the artifact's
recommended state under the blanket approval.

## Decisions

### D1 — Secret scan (S4.2): zero-dep pattern test  *(explicit pick)*
- **Chose:** a pytest in the static set (`tests/test_secret_scan.py`) that walks
  `git ls-files` and greps tracked file content for high-signal secret patterns:
  `sk-ant-` (Anthropic), `AKIA[0-9A-Z]{16}` (AWS), `ghp_`/`github_pat_` (GitHub),
  `-----BEGIN ... PRIVATE KEY-----`, `lsv2_` (LangSmith), and
  `<KNOWN_KEY_VAR>=<non-empty>` assignments outside `.env.example` placeholders.
  Also asserts `git check-ignore .env` exits 0.
- **Why:** same gate shape as D7 (test that shells out / pure python, exit-code
  verdict), no new dependency, no false-positive baseline to maintain.
- **Gave up:** entropy-based detection of unknown token shapes.
  `detect-secrets` (verified runnable, 1.5.0) rejected: needs a curated baseline
  that itself can mask a secret. `gitleaks` rejected: not installed, per-machine
  Go binary — a reviewer's clone couldn't run the gate.

### D2 — verify_all (S4.3): bare command, documented  *(explicit pick)*
- **Chose:** `verify_all` **is** `uv run pytest -m ""` (as already recorded in
  decision-log D7). README's Setup section documents the ritual verbatim:
  `docker compose down -v` (cold start) then `uv run pytest -m ""` from
  `src/backend/`. No wrapper script.
- **Why:** honors D7 ("pytest is already a runner"); zero new code to drift.
- **Gave up:** un-skippable cold start. A human can omit `down -v` and get a
  warm-volume pass; the README states why the cold start matters.

### D3 — Env-var parity (S4.1): commented lines in `.env.example`  *(explicit pick)*
- **Chose:** add the 5 compose-derived vars (`DATABASE_URL`, `SEED_DATABASE_URL`,
  `DATASET_PATH`, `READ_ONLY_ROLE`, `CORS_ALLOW_ORIGINS`) as **commented** entries
  with a note that compose derives them; set only when running outside docker.
  The doc-check derives the expected var list from the code itself —
  `config.py`'s three Settings classes via `model_fields` (verified: yields the
  8 names) plus a grep of `src/frontend/src` for `import.meta.env.<NAME>`
  (yields `VITE_API_BASE_URL`) — and asserts each name appears in
  `.env.example` (commented counts).
- **Why:** matches `docs/tasks.md` S4.1 literally ("every env var in code is in
  example file"); `.env.example` becomes the one complete env reference; the
  expected list can never go stale because it is derived, not hardcoded.
- **Gave up:** a smaller `.env.example` (grows ~7 lines). Rejected alternative:
  parity = union of `.env.example` + compose defaults (reinterprets the
  pass-when; requires YAML parsing in the test).

### D4 — README strictness & cap: exactly 8 H2s, body ≤ 150 lines  *(blanket approval of recommended)*
- **Chose:** doc-check (`tests/test_docs_gate.py`) asserts the README's H2 set
  equals exactly the 8 required headings in `docs/tasks.md` order: Setup,
  Architecture, AI approach, Key decisions, Assumptions, Limitations,
  Future improvements, AI-usage disclosure. `###` subsections are free. Body
  ≤ 150 lines. The current Deployment content folds into **Setup** as an H3.
- **Why:** strictest reading of the spec's "contains exactly these headings";
  the check cannot rot into "8 among 20".
- **Gave up:** Deployment as a top-level section.

## User amendments (from Lavish annotations — binding)

1. **Key decisions section: architecture decisions only.** Link layer
   boundaries / import contracts, D9 routes, D18 SQL-in-calculator, D24
   provider-enforced structure, agent-design D6. No deploy/tooling entries
   (D32 stays out of this table; live URLs still appear under Setup).
2. **Future improvements = the user's list, verbatim intent:** suggestion chips
   after each answer · token-limit usage · critique node validating the answer
   is built from the computation · RAG (user uploads + retrieval) · agent eval
   framework · LLM-generated conversation titles · conversation_histories with
   Postgres as pointer DB for the agent.
3. **Forecasting examples use SKUs `PENCIL-0213` and `CRAYON-0017`** (verified
   in `infra/data/mock_logistics_data.csv`: 3 orders each across ≥3 months) —
   they satisfy the ≥3-months-history need.
4. **Live check:** as part of the evidence step, also verify the live
   deployment at https://main.d3pn3cxdlrbarv.amplifyapp.com/ (renders + smoke),
   captured as `05_live_smoke.png`. The pytest gates themselves stay local —
   they are wired to the compose stack by design (D7/D19).

## Implementation order (per spec Steps)

1. **Red baseline first:** write `tests/test_docs_gate.py` +
   `tests/test_secret_scan.py`, run them against today's repo → must FAIL
   (README missing 6+ headings) → capture `evidence/01_red_baseline.txt`.
2. README rewrite (8 sections, links out, written from what exists),
   `.env.example` additions, decision-log entries (chose / why / gave up,
   concise — CLAUDE.md rule 10).
3. Gates: `uv run pytest` green locally, then cold stack
   (`docker compose down -v`) + `uv run pytest -m ""` → `02_verify_all.txt`;
   secret-scan test output → `03_secret_scan.txt`; rendered README screenshot →
   `04_readme_render.png`; live smoke → `05_live_smoke.png`.

## Scope fences (from spec — absolute)

- **No application code changes.** Docs + gates only.
- No new runner beyond D7's `pytest -m ""`.
- No secrets committed; `.env` stays ignored; `infra/data/` untouched.
- Nothing outside `docs/tasks.md` Slice 4.

## Known consequences / risks

- The 150-line cap is enforced by a test; future README growth must consciously
  raise the cap (a one-line test change + decision-log note).
- The secret scan only catches enumerated token shapes — accepted trade-off.
- Full `verify_all` makes ~70 billable Anthropic calls (unchanged from Slice 2+).
