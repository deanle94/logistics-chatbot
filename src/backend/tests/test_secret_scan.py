"""S4.2 — no secret committed, asserted the same way every other gate is (D7).

Zero-dependency by design: a scanner such as ``detect-secrets`` needs a curated
baseline that can itself mask a secret, and a per-machine binary like ``gitleaks``
would leave a reviewer's clone unable to run the gate. High-signal token shapes
over ``git ls-files`` content are enough for this repository; unknown token shapes
are an accepted trade-off, recorded in the decision log.

The quantifiers keep every pattern high-signal: prose that merely names a prefix
(this repository's own specs do) never matches, and this file cannot match itself.
It is also excluded from the walk outright, belt and braces.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from tests.conftest import REPO_ROOT

GIT_TIMEOUT_SECONDS = 60

SELF_PATH = Path(__file__).resolve()

#: Variables whose committed value must stay empty or a compose ``${...}`` reference.
KEY_VARIABLES: tuple[str, ...] = ("ANTHROPIC_API_KEY", "LANGSMITH_API_KEY")

#: (label, regex) for credential shapes that identify a leak regardless of file type.
TOKEN_PATTERNS: tuple[tuple[str, str], ...] = (
    ("anthropic-key", r"sk-ant-[A-Za-z0-9_-]{8,}"),
    ("aws-access-key-id", r"AKIA[0-9A-Z]{16}"),
    ("github-token", r"ghp_[A-Za-z0-9]{20,}"),
    ("github-pat", r"github_pat_[A-Za-z0-9_]{20,}"),
    ("private-key-block", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ("langsmith-key", r"lsv2_[A-Za-z0-9_]{8,}"),
)

#: ``NAME=value`` / ``NAME: value`` at line start with a real value on the same line.
#: An empty value (the .env.example placeholders) or a ``${...}`` compose reference is
#: allowed. ``[ \t]*`` on purpose: ``\s`` would cross the newline after ``NAME=``.
ASSIGNMENT_PATTERN = re.compile(
    rf"^[ \t]*(?:export[ \t]+)?({'|'.join(KEY_VARIABLES)})[ \t]*[=:][ \t]*(?!\$\{{)\S+",
    re.MULTILINE,
)


def _tracked_files() -> list[Path]:
    """Every path git currently tracks, minus this test file itself."""
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=GIT_TIMEOUT_SECONDS,
    )
    paths = (REPO_ROOT / name for name in result.stdout.split("\0") if name)
    return [path for path in paths if path.resolve() != SELF_PATH]


def _tracked_text() -> list[tuple[Path, str]]:
    """Each tracked file with its content decoded as text (binaries scan as ASCII)."""
    return [
        (path, path.read_bytes().decode("utf-8", errors="ignore"))
        for path in _tracked_files()
        if path.is_file()
    ]


def test_no_secret_token_in_tracked_files() -> None:
    """S4.2: no tracked file contains a credential-shaped token."""
    violations = [
        f"{path.relative_to(REPO_ROOT)}: {label}"
        for path, text in _tracked_text()
        for label, pattern in TOKEN_PATTERNS
        if re.search(pattern, text)
    ]
    assert not violations, f"secret-shaped tokens found in tracked files: {violations}"


def test_no_key_variable_assigned_a_value() -> None:
    """S4.2: no tracked file assigns a real value to a known key variable."""
    violations = [
        f"{path.relative_to(REPO_ROOT)}: {match.group(1)}"
        for path, text in _tracked_text()
        if (match := ASSIGNMENT_PATTERN.search(text))
    ]
    assert not violations, f"key variables assigned a value in tracked files: {violations}"


def test_env_file_is_git_ignored() -> None:
    """S4.2: `.env` stays git-ignored, so a local key can never be committed."""
    result = subprocess.run(
        ["git", "check-ignore", "-q", ".env"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=GIT_TIMEOUT_SECONDS,
    )
    assert result.returncode == 0, ".env is not git-ignored"
