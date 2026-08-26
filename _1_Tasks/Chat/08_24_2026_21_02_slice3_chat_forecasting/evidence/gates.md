# Slice 3 — gate record

Implemented via the discuss-first pipeline (user-approved solution in `../approved-solution.md`),
one implementer + 7 adversarial auditors + bounded fix loop, in worktree branch
`features/slice3-chat-forecasting`, merged to `main` as `d7c3102` (2026-08-26).

## Gate results

| Gate | Result | Evidence |
|---|---|---|
| Static (`uv run pytest`) | **212 passed, 149 deselected, exit 0** (worktree; re-proven on merged main — see below) | `02_green_static.txt` |
| Stack (`uv run pytest -m stack`) | **BLOCKED — not green as one single run.** Latest capture: 6 failed / 143 passed, all failures caused by the Anthropic API key's monthly spend cap | `03_green_stack.txt` |

## Why the stack gate is not green — and why the code is believed correct

The funded `ANTHROPIC_API_KEY` hit its configured monthly usage limit mid-run:

```
anthropic.BadRequestError: 400 — 'You have reached your specified API usage limits.
You will regain access on 2026-09-01 at 00:00 UTC.'
```

Every failing test in `03_green_stack.txt` is an LLM-dependent test that received the
backend's fault envelope after the cap tripped; every LLM-free test (oracles, seeding,
write-rejection, dashboard, health) passed.

Cumulative green coverage across the three live runs (all against the real stack + real model):

| Run (chronological) | Green there | Red there | Cause of red |
|---|---|---|---|
| Workflow verify run (08-25) | 147 incl. **all 4 forecast stack tests**, agent tests, Playwright | envelope key-set test, eval routing | 2 real gaps → fixed in fix round 1 (see deviations 7–8) |
| Post-fix run #2 (08-26) | 144 incl. **the grown 18-case eval** and the envelope test (both previously red) | 4 forecast tests + 1 Playwright | backend died mid-run; consistent with the API cap first tripping here |
| Post-fix run #3 (08-26, instrumented) | 143 | eval cases 15–18, 4 forecast tests, chat e2e | API cap confirmed in backend log (traceback above); no container crash — clean teardown only |

Independent live proof (before the cap died, same backend build): raw `curl -N` SSE captures in
`04_forecast_sse_capture.txt` show the full `interpreting → querying → forecasting → composing`
sequence, a forecast answer whose numbers hand-check against the CSV (PENCIL-0213 history 1,5,5 →
MA 4,5,5,5; total 19; ⌈19×1.15⌉=22), and the digit-free sparse-SKU refusal. `05_backend_log.txt`
covers the same window, no 500s.

**Path to `verified`:** after 2026-09-01 00:00 UTC (or with a raised limit / different funded key
in `.env`), run once from `src/backend`: `docker compose down -v` then `uv run pytest -m stack`.
One green run refreshes `03` + `07` and upgrades the spec status.

## Evidence manifest state

| File | State |
|---|---|
| `01_red_baseline.txt` | ✅ step-1 evals failing against pre-implementation code |
| `02_green_static.txt` | ✅ 212 passed, exit 0 |
| `03_green_stack.txt` | ⚠️ latest run, 6 failed — all API-cap-caused (see above) |
| `04_forecast_sse_capture.txt` | ✅ forecast + sparse refusal, same live window |
| `05_backend_log.txt` | ✅ same window as 04, filtered, no 500s |
| `06_forecast_card_screenshot.png` | ✅ from the green Playwright run (4 sections + dashed line) |
| `07_eval_report.md` | ⚠️ from run #3; cases 15–18 verdicts reflect the API cap, not routing (run #2 passed the same eval) |

## Audits (adversarial, read-only, one per criterion)

All 7 met at high confidence: S3.1 calculator (hand-oracle recursion-discriminating literals),
S3.2 routing, S3.3 card (testid + `stroke-dasharray` assertions), S3.4 refusal (both cases, one
envelope builder), S3.5 eval (+4 cases with exact params, CSV-verified SKU choices),
scope fences (S1.2 + agent/nodes/graph byte-identical, no formula outside calculator/, docs
amended), design conformance (D1/D2/D3/D4 all as approved). Full file:line evidence lives in the
workflow journal; decisions D27–D31 in `docs/decision-log.md`.

## Deviations from the approved solution (all small, all recorded)

1. `subgraphs=True` added to the astream call — the approved fallback: langgraph 1.2.11 swallows
   a custom event from inside `create_agent` without it (proven with a scripted fake model). No
   node name inspected. (D29)
2. `REFUSAL_REASON_KEY` moved `query_tool.py` → `schemas.py` (same value) to avoid a circular
   import. (D30)
3. `sse_reader.invented_digits()` also credits the `forecast` block — mirrors the backend's own
   grounding surface.
4. `test_tool_validation.py` closed-enum assertion updated for `MissingInfo.SKU`.
5. Refusal reason does not quote the SKU code (codes contain digits; refusals must be digit-free).
6. Test/eval SKUs are the dataset's own (PENCIL-0213, CRAYON-0017; PAPER-0197 sparse) — the design
   mock's SKU-1042 does not exist in the CSV.
7. `test_chat_api_stack.py` exact envelope key-set gained `"forecast"` (required by D1).
8. `forecast`/`ask_follow_up` tool descriptions reworded so a sku-less planning question draws a
   follow-up, not a refusal — descriptions are the sanctioned lever (D26/D31). Verified 5/5 live.

Merge note: main's uncommitted deploy-session WIP was stashed around the merge and fully restored;
its duplicate cp1252 fix was superseded by the committed one (keeping its `errors="replace"`
hardening), and its deployment decision-log entry was renumbered D27 → D32 to follow D27–D31.
