"""Tests for the Aprknia interpreter."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.languages.aprknia.interpreter import run
from esolangs.runtime.io import ScriptedIO

#: Pushes 7 then 3, b and a for the page's snippets.
_SEVEN_THREE = "11*!!!!" + "1*!!!!" * 5 + "11*!!!!1*!!!!"
#: Prints the top as an integer (selector 2), then drops it.
_PRINT = "11*!!!!,!"


def _out(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


@pytest.mark.parametrize(
    ("snippet", "value"),
    [
        ("*!!!!", "10"),
        ("*!!!~!", "4"),
        ("*!!~!~!", "21"),
        ("*!~!~!~!", "2"),
        ("*~!~!~!~!", "1"),
    ],
)
def test_wiki_snippets(snippet: str, value: str) -> None:
    assert _out(_SEVEN_THREE + snippet + _PRINT) == value


def test_division_truncates_and_zero_divides_to_zero() -> None:
    # -1 / 2 is 0 and -1 mod 2 is -1; 1 / 0 and 1 mod 0 are both 0.
    minus_one = "11*!!!~!1*!!!~!"
    assert _out(minus_one + "11*!!!!*!~!~!~!" + _PRINT) == "0"
    assert _out(minus_one + "11*!!!!*~!~!~!~!" + _PRINT) == "-1"
    assert _out("111*!!!~!*~!~!~!~!" + _PRINT) == "0"


def test_reads_and_prints_a_byte() -> None:
    # Selector 0 reads, selector 1 prints the byte back.
    assert _out("11*!!!~!,1,", "A") == "A"


def test_loop_runs_while_positive() -> None:
    # 3 counts down to 0, printing each step's value.
    three = "11*!!!!1*!!!!"
    assert _out(three + "[" + _PRINT[:-1] + "1*!!!~!]") == "321"


def test_empty_pop_halts() -> None:
    with pytest.raises(HaltError):
        _out("!")


@pytest.mark.parametrize("code", ["[", "]"])
def test_unmatched_brackets(code: str) -> None:
    with pytest.raises(ValueError, match="unmatched"):
        _out(code)
