"""Tests for the Pilas interpreter."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.languages.pilas.interpreter import run
from esolangs.runtime.io import ScriptedIO


def _out(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


def test_arithmetic_pops_a_then_b() -> None:
    # 9 6 - is b - a = 3, printed as '3' after adding 48.
    assert _out("96-6:+:+:++.\n0{0}") == "3"


def test_lines_alternate_and_tilde_crosses() -> None:
    # Line one moves 7 over; line two then prints 7 + 41 = '0'.
    assert _out("7~" + " " * 14 + "\n  6:+:+:+7-+.") == "0"


def test_brace_loops_while_zero_on_its_own_line() -> None:
    # Counts 0 up to 1 once: the body runs, then the 1 exits.
    assert _out("0{1}6:+:+:+.\n0{0}") == "0"


def test_halts_when_either_pointer_runs_off() -> None:
    assert _out("6:+:+:+.\n1") == ""


def test_wiki_while_zero_translation() -> None:
    # The page's loop, entered on a zero cell and left once it is set.
    code = "0:~:{1+:~:}6:+:+:+1+.\n    {    }0{0}          "
    assert _out(code) == "1"


def test_reads_bytes() -> None:
    assert _out(",.\n  ", "A") == "A"


def test_empty_pop_halts() -> None:
    with pytest.raises(HaltError):
        _out("+\n ")


@pytest.mark.parametrize(
    ("code", "match"),
    [("{\n", "unmatched"), ("}\n", "unmatched"), ("a\nb\nc", "lines")],
)
def test_malformed_programs(code: str, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        _out(code)
