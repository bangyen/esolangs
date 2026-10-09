"""What the CLI suites share: the examples directory, a bound, and both streams."""

import shlex
import sys
from collections.abc import Sequence
from pathlib import Path
from unittest.mock import patch

import pytest

import esolangs
from esolangs._execution import interpreter_module
from esolangs._suggest import Correction
from esolangs.cli import main

EXAMPLES = Path(__file__).parents[1] / "examples"


#: The bound a test gives a program it expects to *not finish*.  These
#: assert an exit code or a message, never an elapsed time, so the value is
#: only how long the suite sits still waiting for the alarm -- the runs it
#: is used on (`+[]`, and 123 on a row it answers by looping) are already
#: looping when the clock starts.  The floor is the slowest *halting* run,
#: which would be misread as a loop if cut short; measured across this
#: suite's corpus that is 0.296s, and these programs do not halt at all.
_LOOPS = "0.5"


class _FakeStdin:
    def __init__(self, data: str) -> None:
        self.data = data

    def isatty(self) -> bool:
        return False

    def read(self) -> str:
        return self.data


def _program(tmp_path: Path, source: str) -> str:
    """Write ``source`` to a file and return its path."""
    path = tmp_path / "prog.b"
    path.write_text(source)
    return str(path)


def call_both(
    args: list[str], capsys: pytest.CaptureFixture[str], stdin: str = ""
) -> tuple[str, str]:
    """Run ``main`` and return both streams."""
    with (
        patch.object(sys, "argv", ["esolangs", *args]),
        patch.object(sys, "stdin", _FakeStdin(stdin)),
    ):
        main()
    captured = capsys.readouterr()
    return str(captured.out), str(captured.err)


def _failure(
    args: list[str],
    capsys: pytest.CaptureFixture[str],
    code: int = 2,
    stdin: str = "",
) -> tuple[str, str]:
    """Run a command that must exit with ``code``; return both streams."""
    with pytest.raises(SystemExit) as caught:
        call_both(args, capsys, stdin)
    assert caught.value.code == code
    captured = capsys.readouterr()
    return captured.out, captured.err


def _refused(
    command: str, tmp_path: Path, capsys: pytest.CaptureFixture[str], stdin: str = ""
) -> str:
    """Run shell-quoted ``command``, which must exit 2; return its stderr.

    A ``prog:SRC`` word stands for a program file holding SRC.
    """
    args = [
        _program(tmp_path, word[5:]) if word.startswith("prog:") else word
        for word in shlex.split(command)
    ]
    return _failure(args, capsys, stdin=stdin)[1]


def repaired(source: str, corrections: Sequence[Correction]) -> str:
    """Apply ``suggest_corrections`` edits, checking each one's ``before``."""
    for correction in reversed(corrections):
        assert source[correction.start : correction.end] == correction.before
        source = (
            source[: correction.start] + correction.after + source[correction.end :]
        )
    return source


def assert_repair_runs(
    language: str,
    source: str,
    output: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The repaired ``source`` prints ``output``; the CLI previews, not edits."""
    handler = interpreter_module(language).suggest_corrections
    edits = handler(source)
    assert edits
    assert esolangs.run(language, repaired(source, edits), timeout=1) == output
    path = tmp_path / "program"
    path.write_text(source, encoding="utf-8")
    out, err = call_both(["suggest", language, str(path)], capsys)
    assert "->" in out
    assert not err
    assert path.read_text(encoding="utf-8") == source
