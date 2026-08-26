# Slice 4 — gate evidence summary

Run date: 2026-08-26. Branch `features/slice4-hardening-docs`, merged to `main`
at `53af1e0` (merge --no-ff).

## Gates

| Gate | Command (from `src/backend/`) | Result |
|---|---|---|
| Red baseline (new gates vs pre-change repo) | `uv run pytest tests/test_docs_gate.py tests/test_secret_scan.py` | doc gate **RED** (2 failures: headings + env parity) — see `01_red_baseline.txt` |
| Static set (worktree, post-change) | `uv run pytest` | **218 passed**, 149 deselected, exit 0 |
| verify_all (S4.3, cold start) | `docker compose down -v` then `uv run pytest -m ""` | **367 passed** in 2:56, exit 0 — see `02_verify_all.txt` |
| Secret scan (S4.2) | `uv run pytest tests/test_secret_scan.py -v` | **3 passed** — see `03_secret_scan.txt` |
| Static set (merged main checkout, re-proof) | `uv run pytest` | **218 passed**, 149 deselected, exit 0 |

## Visual evidence

- `04_readme_render.png` — rendered README: the 8 required H2s in order, live URLs
  under Setup, PENCIL-0213 / CRAYON-0017 example prompts, AI-usage disclosure.
- `05_live_smoke.png` — live deployment https://main.d3pn3cxdlrbarv.amplifyapp.com/:
  dashboard KPIs correct (400 orders, 84.7% on-time) and a real forecast answer for
  "Forecast demand for PENCIL-0213 over the next 3 months" (values + inventory
  recommendation + methodology).

## Audits (adversarial, one per criterion — all met, high confidence)

S4.1 doc-check non-vacuous · S4.2 secret-scan non-vacuous · README content incl.
user amendments · scope fence (no application code) · red baseline + decision-log
entries · design conformance vs approved-solution.md.

## Param verification (not from memory)

pydantic-settings `model_fields` derivation proven by the red baseline printing the
derived 9-name missing set; `git ls-files -z` / `git check-ignore -q` semantics
proven by the passing scan; compose-derived values read off `docker-compose.yml`
lines 42–44/58.

## Deviations from the approved solution (all small, recorded)

1. `VITE_API_BASE_URL` added as a 6th commented `.env.example` entry — the approved
   derived-parity rule itself demands it; the "5 compose-derived vars" wording
   under-counted.
2. Secret-scan assignment regex uses `[ \t]*` not `\s*` around `=` — `\s` crossed
   the newline after the empty `ANTHROPIC_API_KEY=` placeholder and false-positived;
   the approved design requires empty placeholders to pass.
3. `01_red_baseline.txt` re-captured after that regex fix so the baseline reflects
   the final test code (doc gate red, secret scan green — repo holds no secrets).
4. Environment-only, no repo change: worktree `npm ci` needed `npm_config_os=win32`
   because the global `~/.npmrc` sets `os=linux`; pitfall logged.

## Side-effect files (disclosed)

`verify_all`'s stack tests regenerate their own Slice 2/3 evidence artifacts
(`07_eval_report.md` timestamp — score unchanged 18/18 — and three Playwright
screenshots). Committed as regenerated; equivalent content.
