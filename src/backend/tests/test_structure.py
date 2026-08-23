"""S0.2a — the five architecture layers exist as real packages.

Folder names alone would be cosmetic; requiring ``__init__.py`` is what makes each
layer an importable unit that import-linter can then draw a boundary around.
"""

from __future__ import annotations

import pytest

from tests.conftest import BACKEND_ROOT, LAYERS, PACKAGE_ROOT


def test_src_layout_is_standard() -> None:
    """Coding rule 14: source under ``src/<package>/`` next to a ``pyproject.toml``."""
    assert (BACKEND_ROOT / "pyproject.toml").is_file()
    assert PACKAGE_ROOT.is_dir()
    assert (PACKAGE_ROOT / "__init__.py").is_file()
    assert not (BACKEND_ROOT / "setup.py").exists()


@pytest.mark.parametrize("layer", LAYERS)
def test_layer_is_an_importable_package(layer: str) -> None:
    """Each of agent/api/tools/calculator/data is a package, not a bare folder."""
    layer_dir = PACKAGE_ROOT / layer
    assert layer_dir.is_dir(), f"missing layer folder: {layer}"
    assert (layer_dir / "__init__.py").is_file(), f"layer {layer} is not a package"
