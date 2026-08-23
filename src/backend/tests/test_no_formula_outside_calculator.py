"""Architecture Decision 1, as an exit code rather than a code-review habit.

import-linter proves which layer may *import* what. It cannot prove that a business
definition was not retyped inside ``api/``. This test reads the source of every layer that
is forbidden to hold a formula and fails if a definition appears there — a second copy of
"delayed" is exactly the drift Decision 1 exists to prevent.

Comments and docstrings are stripped first (via ``ast.unparse``), because a module that
*says* "the delayed definition lives in the calculator" is doing the right thing, and a
grep over raw text cannot tell that apart from doing the wrong thing. Stripping also
normalises quoting, so the patterns below are written the way ``ast.unparse`` emits them.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.conftest import PACKAGE_ROOT

#: Layers that orchestrate or execute, but must never define. ``calculator/`` is absent on
#: purpose - it is the one place these patterns are allowed.
FORMULA_FREE_LAYERS: tuple[str, ...] = ("api", "tools", "agent", "data")

#: (pattern, why it counts as a business definition rather than plumbing).
FORBIDDEN_FRAGMENTS: tuple[tuple[str, str], ...] = (
    ("'delivered'", "the delivered status literal belongs to docs/business-definition.md"),
    ("'delayed'", "the delayed status literal belongs to docs/business-definition.md"),
    ("func.count(", "a conditional or plain count is a metric definition"),
    ("func.avg(", "an average is a metric definition"),
    ("func.sum(", "a sum is a metric definition"),
    ("date_trunc", "a time bucket is a dimension definition (D12)"),
    ("to_char", "a month label is a dimension definition"),
)


def _strip_docstrings(tree: ast.Module) -> ast.Module:
    """Drop every docstring in place, so only executable code is left to scan."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        if not node.body:
            continue
        first = node.body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
            if not isinstance(first.value.value, str):
                continue
            node.body = node.body[1:] if len(node.body) > 1 else [ast.Pass()]
    return tree


def _executable_source(path: Path) -> str:
    """A module's code with comments and docstrings removed and quoting normalised."""
    return ast.unparse(_strip_docstrings(ast.parse(path.read_text(encoding="utf-8"))))


def _layer_sources(layer: str) -> list[tuple[str, str]]:
    """Every Python file in a layer, as (relative path, executable source)."""
    return [
        (str(path.relative_to(PACKAGE_ROOT)), _executable_source(path))
        for path in sorted((PACKAGE_ROOT / layer).rglob("*.py"))
    ]


@pytest.mark.parametrize("layer", FORMULA_FREE_LAYERS)
@pytest.mark.parametrize(
    ("fragment", "reason"), FORBIDDEN_FRAGMENTS, ids=[f for f, _ in FORBIDDEN_FRAGMENTS]
)
def test_layer_holds_no_business_definition(layer: str, fragment: str, reason: str) -> None:
    """No layer but ``calculator/`` may spell out a metric or a bucket."""
    offenders = [name for name, source in _layer_sources(layer) if fragment in source]

    assert not offenders, f"{fragment} found in {layer}/{offenders}: {reason}"


@pytest.mark.parametrize("fragment", [fragment for fragment, _ in FORBIDDEN_FRAGMENTS])
def test_the_calculator_actually_holds_the_definitions(fragment: str) -> None:
    """The negative test above is only meaningful if the definitions live somewhere.

    Without this, deleting every formula in the project would turn the suite green.
    """
    calculator_source = "".join(text for _, text in _layer_sources("calculator"))

    assert fragment in calculator_source, f"{fragment} is defined nowhere at all"
