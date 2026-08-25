"""S0.2c — prove the import-boundary lint actually fails when a boundary is crossed.

A green lint is worthless if it is green unconditionally. This test copies the source
tree to a temporary directory, plants a module in ``agent/`` that imports
``calculator/``, and asserts the lint rejects it. The control case runs the identical
command on the unmodified copy and asserts it passes, so a failure can only come from
the planted import and never from a broken config or a missing package.

The copy keeps the real ``src/`` untouched: a crashed test can never leave a poisoned
module behind in the repository.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from tests.conftest import BACKEND_ROOT

LINT_TIMEOUT_SECONDS = 300

VIOLATION_SOURCE = '''"""Planted boundary violation. Written by a test, never committed."""

from logistics_analytics.calculator import __name__ as _forbidden

__all__ = ["_forbidden"]
'''


def _run_lint(project_dir: Path) -> subprocess.CompletedProcess[str]:
    """Run import-linter against a copied project tree.

    ``PYTHONPATH`` points at the copy's ``src/`` so import-linter builds the graph from
    the temporary tree rather than the installed package.
    """
    return subprocess.run(
        [
            "uv",
            "run",
            "--project",
            str(BACKEND_ROOT),
            "--no-sync",
            "lint-imports",
            "--config",
            str(project_dir / "pyproject.toml"),
        ],
        cwd=project_dir,
        capture_output=True,
        text=True,
        # Windows would otherwise decode the pipes as cp1252 and crash the reader thread
        # on the config's non-ASCII characters, leaving stdout None (approved gate repair).
        encoding="utf-8",
        timeout=LINT_TIMEOUT_SECONDS,
        check=False,
        env={
            **_clean_env(),
            "PYTHONPATH": str(project_dir / "src"),
        },
    )


def _clean_env() -> dict[str, str]:
    """Inherit the ambient environment minus any PYTHONPATH we would otherwise stack on."""
    import os

    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return env


@pytest.fixture
def project_copy(tmp_path: Path) -> Path:
    """A throwaway copy of the backend project: ``pyproject.toml`` plus ``src/``."""
    destination = tmp_path / "project"
    destination.mkdir()
    shutil.copy2(BACKEND_ROOT / "pyproject.toml", destination / "pyproject.toml")
    shutil.copytree(BACKEND_ROOT / "src", destination / "src")
    return destination


def test_control_copy_passes_the_lint(project_copy: Path) -> None:
    """The untouched copy must pass, otherwise the violation test proves nothing."""
    result = _run_lint(project_copy)
    assert result.returncode == 0, (
        "the unmodified copy failed the import lint, so the negative test below would "
        f"be meaningless\n--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )


def test_planted_violation_fails_the_lint(project_copy: Path) -> None:
    """agent/ importing calculator/ must be rejected (architecture section 3)."""
    planted = project_copy / "src" / "logistics_analytics" / "agent" / "_planted_violation.py"
    planted.write_text(VIOLATION_SOURCE, encoding="utf-8")

    result = _run_lint(project_copy)

    assert result.returncode != 0, (
        "import-linter accepted agent -> calculator; the boundary is not enforced\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    assert "calculator" in result.stdout, (
        f"lint failed but did not name the crossed boundary\n--- stdout ---\n{result.stdout}"
    )
