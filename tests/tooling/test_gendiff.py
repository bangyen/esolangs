"""The generator diff: silent on an unchanged tree, loud on a mutant."""

import importlib
import shutil
from pathlib import Path

import pytest

from esolangs.registry import LANGUAGES
from tests.support.reference import REFERENCE
from tests.tooling.script_support import REPO_ROOT, load

gendiff = load(REPO_ROOT / "scripts" / "gendiff.py")

#: Appended to the reference generator: its LANGUAGE now prefixes a "+".
_MUTATION = """
import dataclasses as _dataclasses

_unmutated = LANGUAGE.backend.generate
LANGUAGE = _dataclasses.replace(
    LANGUAGE, backend=_dataclasses.replace(
        LANGUAGE.backend,
        generate=lambda table, *a, **k: "+" + _unmutated(table, *a, **k)
    )
)
"""


def test_outputs_cover_every_request_and_repeat() -> None:
    first = gendiff.outputs(REFERENCE, 2)
    # Tables through n=2 (4 + 16), each at six options.
    assert len(first) == 20 * 6
    assert gendiff.outputs(REFERENCE, 2) == first


def test_differences_include_a_missing_request() -> None:
    assert gendiff.differences({"a": "x", "b": "y"}, {"a": "x"}) == ["b"]


@pytest.mark.medium  # three generator processes and a copy of src: ~3 s
def test_an_unchanged_tree_matches_and_a_mutant_is_caught(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def snapshot(ref: str, scratch: Path) -> Path:
        assert ref == "snapshot"
        # Generator optimizations legitimately differ from HEAD before commit.
        return shutil.copytree(
            REPO_ROOT / "src",
            scratch / "src",
            ignore=shutil.ignore_patterns("__pycache__"),
        )

    monkeypatch.setattr(gendiff, "_checkout", snapshot)
    module = importlib.import_module(LANGUAGES[REFERENCE].backend.generate.__module__)
    mutant = tmp_path / "mutant.py"
    mutant.write_text(Path(module.__file__ or "").read_text() + _MUTATION)
    argv = [REFERENCE, "--old", "snapshot", "--max-n", "1", "--mutant", str(mutant)]
    assert gendiff.main(argv) == 0
    out = capsys.readouterr().out
    assert "0 differ from snapshot" in out
    assert "control: mutant differs on 24" in out
