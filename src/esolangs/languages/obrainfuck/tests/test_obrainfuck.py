"""Tests for the OBrainfuck interpreter."""

import pytest

from esolangs import ExecutionLimits, Language
from esolangs.exceptions import ExecutionCapError
from esolangs.languages.obrainfuck.interpreter import ordinal_brackets, run
from esolangs.runtime.io import ScriptedIO


def _out(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


def test_kth_opener_pairs_with_kth_closer() -> None:
    # Nested pairing would skip both prints at a zero cell; ordinal pairing
    # jumps from the first ``[`` to the first ``]`` and runs on.
    assert ordinal_brackets(",[.[-].]") == {1: 5, 5: 1, 3: 7, 7: 3}
    assert _out(",[.[-].]", "\0") == "\0"
    # Nonzero: ``]``1 returns to the first print, counting the cell down.
    assert _out(",[.[-].]", "\3") == "\3\2\1\0"
    # The page: "][ is a valid program that falls into an infinite loop".
    with pytest.raises(ExecutionCapError):
        Language("OBrainfuck").run("][", limits=ExecutionLimits(max_steps=1000))
    for code, position in (("[[]", 1), ("[]]", 2), ("]", 0)):
        with pytest.raises(ValueError, match=f"at position {position}"):
            ordinal_brackets(code)
    with pytest.raises(EOFError):
        _out(",")
