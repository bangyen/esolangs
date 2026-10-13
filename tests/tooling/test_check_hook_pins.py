"""The hook-rev gate compares each mapped hook against its pyproject pin."""

from pathlib import Path
from typing import Any

import pytest

from tests.tooling.script_support import load

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "checks" / "check_hook_pins.py"

_PYPROJECT = """\
[dependency-groups]
dev = [
    "ruff==0.16.9",
    "mypy==2.3.1",
]
"""


def load_script() -> Any:
    return load(SCRIPT)


def _plant(tmp_path: Path, hook_rev: str, pyproject: str = _PYPROJECT) -> None:
    (tmp_path / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    (tmp_path / ".pre-commit-config.yaml").write_text(
        "repos:\n"
        "  - repo: https://github.com/charliermarsh/ruff-pre-commit\n"
        f"    rev: {hook_rev}\n"
        "    hooks:\n"
        "      - id: ruff\n",
        encoding="utf-8",
    )


def test_a_matching_rev_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    script = load_script()
    _plant(tmp_path, "v0.16.9")
    monkeypatch.setattr(script, "ROOT", tmp_path)
    assert script.main() == 0


def test_a_drifted_rev_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    script = load_script()
    _plant(tmp_path, "v0.16.8")
    monkeypatch.setattr(script, "ROOT", tmp_path)
    assert script.main() == 1
    assert "pyproject pins 0.16.9, hook rev is v0.16.8" in capsys.readouterr().out


def test_a_missing_hook_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = load_script()
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT, encoding="utf-8")
    (tmp_path / ".pre-commit-config.yaml").write_text("repos:\n", encoding="utf-8")
    monkeypatch.setattr(script, "ROOT", tmp_path)
    assert script.main() == 1


def test_a_version_range_is_not_treated_as_a_pin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = load_script()
    # `ruff>=0.16.9` is a range, not the exact pin the gate compares against,
    # so there is nothing to match and the hook must report it.
    _plant(
        tmp_path,
        "v0.16.9",
        pyproject='[dependency-groups]\ndev = ["ruff>=0.16.9"]\n',
    )
    monkeypatch.setattr(script, "ROOT", tmp_path)
    assert script.main() == 1
