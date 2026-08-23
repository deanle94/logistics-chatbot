"""S0.2b — the static quality gates, each asserted by its own exit code.

D7: there is no bespoke runner script. ``pytest`` is already a runner, so every gate
is a test that shells out and asserts ``returncode == 0``. A failure prints the tool's
own output, so the diagnosis is the tool's message rather than a wrapper's summary.
"""

from __future__ import annotations

import subprocess

import pytest

from tests.conftest import BACKEND_ROOT

GATE_TIMEOUT_SECONDS = 300

#: (test id, argv). Run through ``uv run`` so each tool resolves from the project
#: environment rather than whatever happens to be on PATH.
GATES: list[tuple[str, list[str]]] = [
    ("ruff-check", ["uv", "run", "ruff", "check", "."]),
    ("ruff-format", ["uv", "run", "ruff", "format", "--check", "."]),
    ("mypy", ["uv", "run", "mypy"]),
    ("import-linter", ["uv", "run", "lint-imports"]),
]


@pytest.mark.parametrize(("gate", "argv"), GATES, ids=[gate for gate, _ in GATES])
def test_static_gate_passes(gate: str, argv: list[str]) -> None:
    """Coding rules 1-2 plus the architecture import boundaries, as exit codes."""
    result = subprocess.run(
        argv,
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
        timeout=GATE_TIMEOUT_SECONDS,
        check=False,
    )
    assert result.returncode == 0, (
        f"{gate} failed with exit code {result.returncode}\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
