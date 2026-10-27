"""Tests for the Tiangou interpreter."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.languages.tiangou.interpreter import _Machine, run
from esolangs.runtime.io import ScriptedIO

TRUTH_MACHINE = "i p < : : o >"


def _out(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


def test_wiki_truth_machine_halts_on_zero() -> None:
    assert _out(TRUTH_MACHINE, "0") == "0"


def test_wiki_truth_machine_loops_on_one() -> None:
    # Resuming after '<' keeps the 1 on the stack; at the '<' it would pop it.
    io = ScriptedIO("1")
    machine = _Machine(TRUTH_MACHINE, io)
    for _ in range(60):
        machine.step()
    assert not machine.halted
    assert set(io.getvalue()) == {"1"}
    assert len(io.getvalue()) > 10


def test_minus_is_top_minus_second() -> None:
    # [1, 1, 1] -> [1, 0] -> 0 - 1; second minus top would print 1.
    assert _out("p p p - - o") == "-1"


def test_factorial_and_its_negative_branch() -> None:
    # 3 = (1 - -1) - -1, and 3! = 6; 0 is not positive, so 0 gives -(0!).
    assert _out('p q " - q " - ! o') == "6"
    assert _out("p : - ! o") == "-1"


def test_unset_marker_jump_is_a_no_op() -> None:
    assert _out("p > p o") == "1"


def test_reads_and_prints_integers() -> None:
    assert _out("i i o o", "42\n-7") == "-742"


def test_line_break_separates_like_a_space() -> None:
    assert _out("p\no") == "1"


def test_empty_pop_halts() -> None:
    with pytest.raises(HaltError):
        _out("o")


def test_unknown_command_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown command"):
        _out("p po")
