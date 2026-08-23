"""AI-powered logistics analytics dashboard.

The package is split into five layers, one folder each, mirroring
``docs/architecture.md`` section 3. The import rules between them are enforced by
import-linter (see ``[tool.importlinter]`` in ``pyproject.toml``); they are the only
thing keeping the layers independent, because everything runs in one process.
"""

__version__ = "0.1.0"
