"""S4.1 — the reviewer-facing docs, machine-checked.

The README's shape is a gate, not an opinion: exactly the eight required H2
headings in ``docs/tasks.md`` order, a 150-line body cap, and every environment
variable the code reads named in ``.env.example``. The expected variable list is
derived from the code at test time — ``config.py``'s Settings classes plus the
front-end's ``import.meta.env`` reads — so it can never go stale.
"""

from __future__ import annotations

import re

from logistics_analytics.config import LlmSettings, SeedSettings, Settings
from tests.conftest import FRONTEND_ROOT, REPO_ROOT

README_PATH = REPO_ROOT / "README.md"
ENV_EXAMPLE_PATH = REPO_ROOT / ".env.example"

#: The eight required H2 headings, in the exact order docs/tasks.md S4.1 lists them.
REQUIRED_HEADINGS: tuple[str, ...] = (
    "Setup",
    "Architecture",
    "AI approach",
    "Key decisions",
    "Assumptions",
    "Limitations",
    "Future improvements",
    "AI-usage disclosure",
)

#: Conciseness caps: "concise" is a gate, not an opinion (spec acceptance criterion).
MAX_README_LINES = 150
MAX_SECTION_LINES = 40


def _readme_lines() -> list[str]:
    """The README body as lines, read fresh so each test sees the current file."""
    return README_PATH.read_text(encoding="utf-8").splitlines()


def _h2_headings(lines: list[str]) -> list[tuple[int, str]]:
    """``(line index, title)`` of every H2, ignoring lines inside fenced code blocks."""
    headings: list[tuple[int, str]] = []
    in_fence = False
    for index, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        elif not in_fence and line.startswith("## "):
            headings.append((index, line[3:].strip()))
    return headings


def _expected_variables() -> set[str]:
    """Every environment variable the code reads, derived from the code itself.

    Backend: the three Settings classes' field names, uppercased — pydantic-settings
    reads each field from the environment variable of that name. Front-end: every
    ``import.meta.env.<NAME>`` read under ``src/frontend/src``.
    """
    names = {
        field.upper()
        for settings_class in (Settings, LlmSettings, SeedSettings)
        for field in settings_class.model_fields
    }
    reader = re.compile(r"import\.meta\.env\.([A-Za-z_][A-Za-z0-9_]*)")
    for path in (FRONTEND_ROOT / "src").rglob("*.ts*"):
        names.update(
            match.group(1).upper() for match in reader.finditer(path.read_text(encoding="utf-8"))
        )
    return names


def test_readme_has_exactly_the_required_headings() -> None:
    """S4.1: the H2 set equals the eight required headings, in order — no extras."""
    titles = [title for _, title in _h2_headings(_readme_lines())]
    assert titles == list(REQUIRED_HEADINGS), (
        f"README.md H2 headings must be exactly {list(REQUIRED_HEADINGS)}, found {titles}"
    )


def test_readme_stays_short() -> None:
    """Conciseness cap: whole body <= 150 lines, each H2 section <= 40 lines."""
    lines = _readme_lines()
    assert len(lines) <= MAX_README_LINES, (
        f"README.md is {len(lines)} lines; the cap is {MAX_README_LINES}"
    )
    headings = _h2_headings(lines)
    boundaries = [index for index, _ in headings] + [len(lines)]
    for (start, title), end in zip(headings, boundaries[1:], strict=True):
        section_length = end - start
        assert section_length <= MAX_SECTION_LINES, (
            f"README section {title!r} is {section_length} lines; the cap is {MAX_SECTION_LINES}"
        )


def test_env_example_names_every_variable_the_code_reads() -> None:
    """S4.1 env parity: each derived variable name appears in .env.example.

    A commented mention counts — compose derives some values itself, and the
    example file documents that rather than duplicating the derivation.
    """
    content = ENV_EXAMPLE_PATH.read_text(encoding="utf-8")
    missing = sorted(
        name
        for name in _expected_variables()
        if not re.search(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])", content)
    )
    assert not missing, f".env.example does not mention: {missing}"
