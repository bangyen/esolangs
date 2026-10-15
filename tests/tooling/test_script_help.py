"""Every argparse script under ``scripts/`` still starts: ``--help`` exits 0.

Most scripts run only by hand (``just gendiff``), so a broken import or parser
would surface at the moment someone needs the tool.  Run as ``just`` runs
them, in a fresh interpreter from the repo root.
"""

import subprocess
import sys
from pathlib import Path

import pytest

from tests.tooling.script_support import REPO_ROOT

pytestmark = pytest.mark.medium


def _entry_points() -> list[Path]:
    """Return every script that parses arguments and runs as ``__main__``."""
    return sorted(
        path.relative_to(REPO_ROOT)
        for path in (REPO_ROOT / "scripts").rglob("*.py")
        if "argparse" in (text := path.read_text(encoding="utf-8"))
        and "__main__" in text
    )


def _help(script: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


@pytest.mark.parametrize("script", _entry_points(), ids=str)
def test_the_script_prints_its_usage(script: Path) -> None:
    """``--help`` exits 0 with a usage line, before any real work."""
    result = _help(script)
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("usage:"), result.stdout[:200]


def test_the_discovery_finds_the_known_scripts() -> None:
    """Negative control: an empty glob would pass every case vacuously."""
    found = {path.as_posix() for path in _entry_points()}
    assert {"scripts/gendiff.py", "scripts/verify/gate.py"} <= found


def test_a_script_that_cannot_import_fails(tmp_path: Path) -> None:
    """Positive control: the check fails a script that no longer starts."""
    broken = tmp_path / "broken.py"
    broken.write_text("import argparse\nimport no_such_module\n", encoding="utf-8")
    assert _help(broken).returncode != 0
