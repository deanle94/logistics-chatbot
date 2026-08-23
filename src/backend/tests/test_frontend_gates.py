"""S0.4 — the front-end type-checks, lints and builds, each as an exit code.

These gates live with the backend tests on purpose: D7 put every Slice 0 gate behind a
single ``pytest`` invocation, so "is the slice green?" is one command rather than a
checklist a human has to remember.

They need ``node_modules``, which the session fixture installs once if it is absent.
No docker is involved, so they run in the default (non-``stack``) selection.
"""

from __future__ import annotations

import subprocess

import pytest

from tests.conftest import FRONTEND_ROOT, resolve_executable

INSTALL_TIMEOUT_SECONDS = 900
GATE_TIMEOUT_SECONDS = 600

GATES: list[tuple[str, list[str]]] = [
    ("type-check", ["run", "type-check"]),
    ("lint", ["run", "lint"]),
    ("build", ["run", "build"]),
]


@pytest.fixture(scope="session", autouse=True)
def node_modules() -> None:
    """Install front-end dependencies once per session if they are missing."""
    if (FRONTEND_ROOT / "node_modules").is_dir():
        return
    subprocess.run(
        [resolve_executable("npm"), "install"],
        cwd=FRONTEND_ROOT,
        check=True,
        timeout=INSTALL_TIMEOUT_SECONDS,
    )


@pytest.mark.parametrize(("gate", "args"), GATES, ids=[gate for gate, _ in GATES])
def test_frontend_gate_passes(gate: str, args: list[str]) -> None:
    """``npm run type-check`` / ``lint`` / ``build`` must each exit 0."""
    result = subprocess.run(
        [resolve_executable("npm"), *args],
        cwd=FRONTEND_ROOT,
        capture_output=True,
        text=True,
        timeout=GATE_TIMEOUT_SECONDS,
        check=False,
    )
    assert result.returncode == 0, (
        f"front-end {gate} failed with exit code {result.returncode}\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
