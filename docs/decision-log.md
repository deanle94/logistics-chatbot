# Decision Log

Every key decision as **chose / why / gave up**. Slice 4 (S4.1) folds this into the README.

`docs/architecture.md` section 4 owns the *architectural* decisions (one calculator, one
service, AI never computes). This file records the *implementation* decisions taken per
slice, and any deliberate deviation from that document.

---

## Slice 0 — Skeleton

### D1 — uv + `pyproject.toml` + `uv.lock`

|  |  |
| --- | --- |
| **Chose** | `uv` for dependency management and the Docker base image. |
| **Why** | PEP-621 native, so coding rule 14 (`src/` layout + `pyproject.toml`) comes free. The lockfile makes a reviewer's build byte-identical to ours, and `uv sync --frozen` in the Dockerfile fails loudly on a stale lock instead of quietly resolving something untested. |
| **Gave up** | One non-standard tool a reviewer may not know; `pip install -r requirements.txt` is more universally readable. |

### D2 — `import-linter` for the layer boundaries

|  |  |
| --- | --- |
| **Chose** | Declarative `forbidden` contracts in `[tool.importlinter]`, run as `lint-imports`. |
| **Why** | The architecture's import rules become configuration that reads like the architecture document, checked by one exit code. It follows the whole import graph, so an *indirect* leak (`agent → helper → data`) is caught — a per-file textual rule would miss exactly the leak most likely to happen. |
| **Gave up** | An extra dev dependency and a second lint command beside ruff. Rejected: nested `.ruff.toml` + `banned-api` (no new dep, but config scatters across five files and misses indirect leaks) and a hand-written `ast` walker (zero deps, but ~50 lines of infrastructure we would own). |
| **Note** | `main.py` is deliberately outside the contracts. It is the composition root; a root that could not reach across layers could not compose them. Every other module stays inside its boundary. |
| **Note** | The "only `data/` touches the database" contract sets `allow_indirect_imports = true` on purpose — `api/` may call `data/`, it just may not import SQLAlchemy itself. The two layer contracts keep the strict default. |

### D3 — One-shot seeder container, idempotent by replace

|  |  |
| --- | --- |
| **Chose** | A `seeder` service that runs `python -m logistics_analytics.data.seed` and exits 0; the API waits on `service_completed_successfully`. It deletes and reloads rather than inserting-if-missing. |
| **Why** | S0.3 requires "seed twice → still 400", which needs the seed to be a runnable command, not a first-boot side effect. It builds the schema from the same SQLAlchemy models the app uses, so schema and models cannot drift. Replace-not-append means a changed CSV can never leave stale rows behind looking like success. |
| **Gave up** | A third container and a slower cold start than a raw `COPY`. Rejected: `docker-entrypoint-initdb.d` (fastest, but only runs on an empty volume, so "seed twice" could not be asserted) and seeding in the API's startup lifespan (fewest parts, but self-contradictory — the API would need write privileges). |

### D4 — Two roles, `SELECT`-only grants, no view

|  |  |
| --- | --- |
| **Chose** | `app_owner` owns the tables and is used only by the seeder. `app_ro` holds `CONNECT + USAGE + SELECT` and is what the API connects as. No view or materialized view. |
| **Why** | Read-only is a *privilege*, not a convention, so no code path can opt out. Measured on a live `postgres:17-alpine`: with `SELECT`-only grants an `INSERT` fails with `permission denied for table orders`; `ALTER DEFAULT PRIVILEGES` extends this to Slice 1 tables automatically. |
| **Gave up** | Two connection strings in `.env.example`, and no object-level second lock. |
| **Considered and rejected** | A **materialized view** as the app's only object. The probe showed it does block `INSERT`/`UPDATE` (`cannot change materialized view`) even with `ALL` granted — but it does *not* protect the base table, `REFRESH` still succeeded, and it went stale (base 4 rows, view still 2). That last point is decisive: S0.3 asserts "the database has exactly 400 rows", and a materialized view creates two answers to that question. |
| **Considered and rejected** | `default_transaction_read_only = on`. One line, but a session default any code can turn off — it would pass the test while being security theatre. |

### D4a — Aggregation views: allowed later *(deliberate deviation)*

|  |  |
| --- | --- |
| **Chose** | SQL views containing aggregates may be introduced in a later slice if they earn their place. |
| **Why** | Explicit tech-lead decision, taken with the trade-off stated. |
| **Gave up** | Single ownership of formulas. `architecture.md` Decision 1 says the calculator is the sole owner of every business definition; a view holding "delay rate" or "on-time %" would define `delayed` in two languages, which is the drift that decision exists to prevent. At 400 rows there is no performance argument on the other side. |
| **Status** | No Slice 0 impact. It first matters when Slice 1 formulas land — the oracle tests there compare the calculator against the CSV, so a view-based metric would need its own oracle. |

### D5 — Multi-stage build served by nginx, `/api` proxied

|  |  |
| --- | --- |
| **Chose** | `node` builds the bundle, `nginx` serves it, `/api/` proxies to `backend:8000`. |
| **Why** | S0.5 needs the front-end to answer HTTP 200 from `docker compose up`; a React app is a folder of files, so something must serve it. Proxying puts browser and API on **one origin, so CORS never exists** in any slice. The `vite build` that S0.4 gates is also the artifact that ships, so a broken build cannot pass. Same shape as the public deploy S1.6 will need. |
| **Gave up** | No hot reload inside compose — a UI change needs `docker compose up --build frontend`, or `npm run dev` outside compose. If that loop becomes painful, a `docker-compose.override.yml` swapping in the dev server is a one-file addition. |

### D6 — Playwright against the real stack

|  |  |
| --- | --- |
| **Chose** | A real browser driving the nginx-served page, not a jsdom component test. |
| **Why** | S0.4 says "browser test", and asserting on text sourced from `/health` proves the entire chain in one check: page served, React rendered, proxy works, FastAPI answers, PostgreSQL reachable. It also replaces the separate front-end HTTP 200 check in S0.5 — a bare 200 would prove only the first link. Reused by S1.5, S2.6 and S3.3, so the cost amortises across three later slices. |
| **Gave up** | ~200 MB of browser binaries and a slower test that needs the stack up. |

### D7 — No runner script: every gate is a `pytest` test

|  |  |
| --- | --- |
| **Chose** | `ruff`, `mypy`, `lint-imports`, `npm run type-check/lint/build` and the compose smoke are each a test that shells out and asserts exit 0. Stack-dependent tests sit behind `-m stack`. |
| **Why** | `pytest` is already a runner; a bespoke `verify_slice0.py` would be ~60 lines whose only job is running other code. Two commands cover the slice, and S4.3's `verify_all` becomes `pytest -m ""`. A failure prints the tool's own message rather than a wrapper's summary. |
| **Gave up** | A lint failure is reported as a test failure, so the diagnosis is one level down in captured stdout; markers have to be remembered. Rejected: `Makefile` (`make` is not installed on the target machine) and "just document the commands" (no single exit code, so "green" becomes a human claim — which `docs/tasks.md` rules out). |

### Local development credentials live in `docker-compose.yml`

|  |  |
| --- | --- |
| **Chose** | Every credential is `${VAR:-local_dev_default}`; `.env.example` documents them; `.env` is git-ignored. |
| **Why** | S0.5 requires `docker compose up` to work as one command. Requiring a hand-made `.env` first would fail that criterion for a reviewer who just cloned the repo. |
| **Gave up** | Strictly, there are default passwords in a committed file. They are local-container-only and any non-local deployment must override every one of them. No real secret is committed. |

### D8 — Repo layout: code under `src/`, everything the stack needs under `infra/`, documents at the root

|  |  |
| --- | --- |
| **Chose** | Three root categories. `src/` is application code (`backend/`, `frontend/`); `infra/` is everything the stack needs but nobody writes as application code (`db/init/` provisioning, `data/` the dataset); `docs/`, `rules/`, `_1_Tasks/`, `CLAUDE.md` are documents and governance. `docker-compose.yml` stays at the root as the stack's entry point. |
| **Why** | A reviewer opening the repo sees three categories at once — what we wrote, what it runs on, what governs it — instead of eight sibling folders with no ranking. Requested by the tech lead for exactly that separation. |
| **Gave up** | The Python package now sits at `src/backend/src/logistics_analytics/` — the word `src` appears twice. Accepted deliberately: coding rule 14 requires `pyproject.toml` beside `src/<package>/` with a sibling `tests/`, and `test_structure.py` asserts it, so collapsing the inner `src/` would fail our own S0.2 eval to save one path segment. |
| **Gave up** | `docker-compose.yml` was *not* moved into `infra/`, so infra is split across two places. S0.5 requires `docker compose up` to work from the repo root as one command, and `-f infra/docker-compose.yml` would also re-base every relative path inside the file. The entry point stays where a reviewer will look for it. |
| **Gave up** | Filing `data/` under `infra/` understates one of its two roles. The CSV is the seeder's input *and* the test oracle — `conftest.py` re-reads it host-side, in no container at all, to derive 400 and 304/55/27/11/3 independently of the code under test. `infra/` reads as "how it is deployed", which covers only the first role. Overruled by the tech lead in favour of a smaller root; the oracle still works because only the path changed. |
| **Gave up** | Three governing documents had to be edited to match a folder rename (`docs/tasks.md`, `spec.md`, this file). Editing an acceptance criterion so it matches the filesystem is the wrong direction of travel; recorded below under corrections so the edit is traceable rather than silent. |
| **Blast radius** | In `docker-compose.yml`: three build contexts, the initdb bind mount, and the dataset bind mount — the *container-side* `DATASET_PATH: /data/...` is unchanged, since only the host half of the mount moved. In `tests/conftest.py`: a new `SRC_ROOT` between `BACKEND_ROOT` and `REPO_ROOT`, and `CSV_PATH`. Three markdown path citations. Nothing else referenced the old paths. The `.venv` had to be rebuilt — `uv` bakes the project's absolute path into the install and the console-script trampolines, so a moved venv fails with `uv trampoline failed to canonicalize script path`. `node_modules` survived the move: npm's Windows shims resolve relatively. |
| **Evidence** | 27 static + 6 stack gates green from a cold `docker compose down -v`, re-run after each move — reproduce with the two commands under *Verifying this repo* below. The cold start is what proves the `infra/` moves: `01_roles.sh` only executes on an empty volume (so `test_application_role_cannot_write` fails if the initdb mount is wrong), and the seeder re-reads the CSV through the dataset mount (so the 400-row and status-count tests fail if that one is wrong). |

---

## Corrections made to the specs

- **Dataset path, 08_23_2026.** `data/mock_logistics_data.csv` → `infra/data/mock_logistics_data.csv` in `docs/tasks.md` and `spec.md`, following D8. The file, its 400 rows and every expected number are unchanged — only its location moved.

- **`spec.md` S0.3 status labels.** The spec read `delivered/in_transit/delayed/... = 304/55/27/11/3`. An independent read of `infra/data/mock_logistics_data.csv` gives `delivered 304, delayed 55, in_transit 27, exception 11, canceled 3` — the numbers were right, the labels were swapped. Text corrected; the test derives the mapping from the CSV at runtime, so it can never drift again.

---

## AI usage disclosure

This project was built with heavy use of an AI coding assistant (Claude, via Claude Code).
The assistant read the specification documents, proposed the implementation options above
with their trade-offs, and wrote the code, the tests and the container configuration after
a human picked between the options. Every non-trivial decision on this page was reviewed
and, in two cases (D4a and the initial D4 choice), overruled or changed by the human tech
lead. Factual claims about third-party behaviour were verified by running them rather than
recalled — the PostgreSQL read-only findings in D4 come from a probe against a live
`postgres:17-alpine` container, and the dataset numbers come from an independent read of
the CSV. All acceptance criteria were executed rather than asserted; the captured run logs
are held with the task in our internal tracker, and anyone can reproduce them here with the
two commands below.

---

## Verifying this repo

Every acceptance criterion in this slice is a test that shells out and asserts exit 0, so
"green" is a command's verdict rather than a human claim. From `src/backend/`:

```bash
uv run pytest             # 27 static gates
uv run pytest -m stack    # 6 gates against the live compose stack
```

The second set brings the stack up itself. Run `docker compose down -v` first if you want a
cold start — `infra/db/init/01_roles.sh` executes only on an empty volume, so a warm run
proves less than it appears to.

The expected numbers (400 rows; `delivered 304, delayed 55, in_transit 27, exception 11,
canceled 3`) are derived in `tests/conftest.py` by re-reading
`infra/data/mock_logistics_data.csv` with the standard library, never from the seeder. If
the seeder and the oracle ever disagree, the tests fail.
