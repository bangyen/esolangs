"""Deadfish through the shared API, CLI and machinery."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

import esolangs
from tests.support.evaluation import _evaluate
from tests.support.reference import REFERENCE


def test_generate_refuses_a_language_with_no_generator() -> None:
    """A registered language may have no generator, and must say so."""
    with pytest.raises(esolangs.ArgumentError) as exc:
        esolangs.generate("Deadfish", "0110")
    message = str(exc.value)
    assert "no boolean generator" in message
    assert "generator contracts" in message
    assert "'int'" in message


@pytest.mark.medium
@pytest.mark.parametrize(
    "limits", [(), ("--max-steps", "5"), ("--isolated", "--execution-timeout", "2")]
)
def test_cli_leaves_unused_stdin_unread(
    tmp_path: Path, limits: tuple[str, ...]
) -> None:
    path = tmp_path / "program"
    path.write_text("io")
    reader, writer = os.pipe()
    with os.fdopen(reader, "rb") as source, os.fdopen(writer, "wb") as feed:
        feed.write(b"\xff")
        feed.flush()
        result = subprocess.run(
            [sys.executable, "-m", "esolangs", "run", *limits, "Deadfish", str(path)],
            stdin=source,
            capture_output=True,
            timeout=10,
            check=False,
        )
        feed.close()
        assert source.read() == b"\xff"
    assert (result.returncode, result.stdout, result.stderr) == (0, b"1\n", b"")


def test_supplied_program_never_generates(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("evaluation called a generator")

    monkeypatch.setattr(esolangs, "generate", refuse)
    assert _evaluate(REFERENCE, ",>,<.", inputs=2) == "0011"
    assert _evaluate("Deadfish", "o", inputs=1) == "00"
