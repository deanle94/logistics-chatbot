# RULES MUST FOLLOW - NO ESCUSE - NO EXCEPTION - HIGHLY IMPORTANT
## 1. (architecture & data)
- [ ] 🔴 `core` — **AI never computes answers.** It only picks the tool and fills in structured parameters.
- [ ] 🔴 `core` — **Data must be correct.** Right aggregation, right filtering. Reviewers will check numbers against the dataset.
- [ ] Treat all data as **read-only**.
- [ ] Use the provided dataset/database (one unified dataset).
- [ ] **Never execute raw AI-generated SQL without validation** — prefer structured query generation (AI outputs JSON like `{metric, filters, group_by}`, your code builds the safe query).
- [ ] Clearly separate three layers: **AI interpretation** / **data computation** / **business logic**. Reference to ./docs/architecture.md - part Separation of concerns by folder
- [ ] Do **not** commit secrets to the repository.
- [ ] 🟡 `easy-to-forget` — **Don't over-engineer.** Simple and correct beats complete and polished.
- [ ] 🟡 `easy-to-forget` — **Clearly explain trade-offs.** For every key decision, write down: what we chose, why, and what we gave up. The spec values *reasoning* over completeness — decisions without reasoning lose points even when they are good decisions.
- [ ] 🟡 `easy-to-forget` — **Disclose AI usage** while building. Undisclosed AI usage may be treated negatively — one honest paragraph in the README removes the risk.

## 2. All your decision making Must follow the design in docs\architecture.md and docs\requirement.md. DO NOT invent anything new outside the scope and make thing over-engineer.
## 3. If there is anything you're unsure, ask me. DON'T Make any hidden assumption.
## 4. When design the technical solution(components & class design), use the technical stack defined in docs\technical-stack.md and rules in rules\
## 5. When generate python code, use this rule: rules\python-coding-rules.md
## 6. When generate front-end code(React), use this rules: rules\react-coding-rules.md
## 7. For the UI implementation, must use docs\design. Use playright to validate the screen created.
## 8. Repository structure — put new files where they belong
Three top-level categories. Reasoning in `docs/decision-log.md` D8.

```
src/                      code we write
  backend/                pyproject.toml + src/logistics_analytics/ + tests/
    src/logistics_analytics/
      agent/ api/ tools/ calculator/ data/   the five layers (rule 1 above)
      config.py main.py                      composition root, outside the import contracts
  frontend/               package.json + src/ + e2e/
infra/                    what the stack needs, but nobody writes as application code
  db/init/                psql provisioning, runs once on an empty volume
  data/                   the read-only dataset — seeder input AND test oracle
docs/ rules/ _1_Tasks/    documents and governance
docker-compose.yml        stack entry point, stays at the root
```

- The **inner** `src/` in `src/backend/src/` is deliberate — python-coding-rules 14 requires `pyproject.toml` beside `src/<package>/` with a sibling `tests/`. `tests/test_structure.py` asserts it. Do not collapse it.
- **Never move or edit `infra/data/`.** It is read-only, and `tests/conftest.py` re-reads it host-side to derive the expected numbers independently of the code under test (the spec's oracle rule).
- Moving any of these folders means updating `docker-compose.yml` (build contexts + bind mounts) and the path constants at the top of `tests/conftest.py`. Prove the move with a cold start: `docker compose down -v`, then both gate sets.

## 9. Verify with the gates, not by eye
From `src/backend/`:
- `uv run pytest` — 140 static gates (ruff, ruff format, mypy, import-linter, planted violation, structure, deps, health, SQL builder, API contract, no-formula-outside-calculator, frontend build/type-check/lint)
- `uv run pytest -m stack` — 125 gates against the live compose stack (row count, status counts, write rejection, re-seed, the KPI + query oracles, the four routes, Playwright)

Counts are Slice 1. Slice 0 was 27 / 6. The correctness gates are the stack set, not the
static set — a calculator that emits SQL can only be checked against the CSV by running it
(decision-log D18/D19), so `uv run pytest` alone never proves a number is right.

Both must exit 0. Capture the output as evidence — "it works" without an artifact does not count.

## 10. when capture decision in docs/decision-log.md. Must precise and only capture main reason. DO NOT verbose here