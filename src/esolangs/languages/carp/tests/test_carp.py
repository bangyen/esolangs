"""Tests for the CARP interpreter."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.languages.carp.interpreter import run
from esolangs.runtime.io import ScriptedIO

ADD = """INC r3 2 # r3 is used for control flow
INP r1 3
INP r2 4
DEC r2 6
DEC r3 9
INC r1 7
INC r3 8
DEC r3 4
OUT r1 10
DEC r1 0"""


def _run(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


@pytest.mark.parametrize(("a", "b"), [(0, 0), (3, 4), (7, 8), (9, 6)])
def test_page_addition_program(a: int, b: int) -> None:
    assert _run(ADD, f"{a} {b}") == str(a + b)


def test_inc_at_15_jumps_without_wrapping() -> None:
    code = "INC r1 1\n" * 15 + "INC r1 18\nOUT r1 0\nOUT r1 0\nCLR r1 0\nOUT r1 0"
    assert _run(code) == "150"  # line 17 skipped, no wrap to 0


def test_dec_at_zero_falls_through_and_nonzero_jumps() -> None:
    assert _run("DEC r1 3\nOUT r1 0\nOUT r1 0") == "00"
    assert _run("INP r1 0\nDEC r1 4\nOUT r1 0\nOUT r1 0\nOUT r1 0", "1") == "00"


def test_clr_and_line_zero_halts() -> None:
    assert _run("INP r1 0\nCLR r1 0\nOUT r1 0\nDEC r2 0\nOUT r1 0", "5") == "00"
    assert _run("INC r1 0\nINC r1 0\nOUT r1 0") == "2"  # below 15: falls through
    assert _run("INC r1 2\nDEC r1 0\nOUT r1 0") == ""  # DEC at 1 jumps to 0


@pytest.mark.parametrize(
    "code",
    ["", "# only a comment", "FOO r1 1", "INC r0 1", "INC r16 1", "INC r1", "INC 1 1"],
)
def test_malformed_program(code: str) -> None:
    with pytest.raises(
        ValueError, match=r"instruction|command|register|line|malformed"
    ):
        _run(code)


def test_input_must_fit_a_nibble() -> None:
    with pytest.raises(HaltError):
        _run("INP r1 0", "16")


def test_input_at_eof() -> None:
    with pytest.raises(EOFError):
        _run("INP r1 0")
