"""S0.6 — tech-stack conformance, asserted against the manifests rather than the lockfiles.

``docs/technical-stack.md`` names the libraries this project must be built on. Checking
the declared dependencies (not the installed set) is deliberate: a transitively-installed
package would satisfy an import check while leaving the stack undeclared for the next
person who installs the project.
"""

from __future__ import annotations

import json
import tomllib

import pytest

from tests.conftest import BACKEND_ROOT, FRONTEND_ROOT

REQUIRED_BACKEND_PACKAGES = ("fastapi", "sqlalchemy", "pydantic", "langchain", "langgraph")
REQUIRED_FRONTEND_PACKAGES = ("react", "shadcn", "axios")


def _declared_backend_packages() -> set[str]:
    """Distribution names declared in ``[project.dependencies]``, lowercased."""
    with (BACKEND_ROOT / "pyproject.toml").open("rb") as handle:
        manifest = tomllib.load(handle)
    requirements: list[str] = manifest["project"]["dependencies"]
    names = set()
    for requirement in requirements:
        # Strip extras and any version specifier: "psycopg[binary]>=3" -> "psycopg".
        name = requirement.split("[")[0]
        for separator in (">=", "<=", "==", "~=", "!=", ">", "<", ";", " "):
            name = name.split(separator)[0]
        names.add(name.strip().lower())
    return names


def _declared_frontend_packages() -> set[str]:
    """Every name in ``dependencies`` and ``devDependencies``.

    ``shadcn`` is a CLI that copies components into the repo, so it legitimately lives
    in devDependencies rather than at runtime.
    """
    manifest = json.loads((FRONTEND_ROOT / "package.json").read_text(encoding="utf-8"))
    return {
        *manifest.get("dependencies", {}),
        *manifest.get("devDependencies", {}),
    }


@pytest.mark.parametrize("package", REQUIRED_BACKEND_PACKAGES)
def test_backend_declares_required_package(package: str) -> None:
    """FastAPI, SQLAlchemy, Pydantic, LangChain and LangGraph must be declared."""
    assert package in _declared_backend_packages()


@pytest.mark.parametrize("package", REQUIRED_FRONTEND_PACKAGES)
def test_frontend_declares_required_package(package: str) -> None:
    """React, shadcn and axios must be declared."""
    assert package in _declared_frontend_packages()
