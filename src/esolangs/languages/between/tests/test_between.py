"""Tests for the Between interpreter."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.languages.between.interpreter import run
from esolangs.runtime.io import ScriptedIO


def out(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


def test_goto_is_zero_based_and_skips_comments() -> None:
    """Line 0 is the first instruction; blanks and ``#`` lines are not counted."""
    assert out("# top\n\n|2|f.\n|1|p.\n|0|p.\n.x.") == "0"


def test_unset_variable_is_zero() -> None:
    assert out("'a'v.\n[a]p.") == "0"


def test_goto_to_the_end_halts_and_beyond_raises() -> None:
    assert out("|1|f.") == ""
    with pytest.raises(HaltError, match="outside"):
        out("|2|f.")


@pytest.mark.parametrize(
    ("code", "printed"),
    [
        ("|3|f(True)\n|1|p.\n.x.\n|2|p.", "2"),
        ("|3|f(False)\n|1|p.\n.x.\n|2|p.", "1"),
        ("|3|f(((False)r(False))n.)\n|1|p.\n.x.\n|2|p.", "2"),
        ("|3|f(((False)r(True))n.)\n|1|p.\n.x.\n|2|p.", "1"),
    ],
)
def test_conditions_nest(code: str, printed: str) -> None:
    assert out(code) == printed


def test_apostrophes_in_strings() -> None:
    """A string closes at the first apostrophe an operation follows."""
    assert out("'can't stop'p.") == "can't stop"
    with pytest.raises(ValueError, match="unterminated"):
        out("'it's'p.")


def test_groups_nest_and_compute() -> None:
    assert out("'a'v.\n[a]s|3|\n[a]s|[a]+|4||\n[a]s|[a]*|[a]+|1|||\n[a]p.") == "56"
    assert out("'a'v.\n[a]s|'12'c.|\n[a]p.") == "12"


def test_types_are_strict() -> None:
    with pytest.raises(HaltError):
        out("'1'=|1|")
    with pytest.raises(HaltError, match="int group"):
        out("'a'v.\n[a]s|'a'+'b'|")
    with pytest.raises(HaltError):
        out("'x'c.")


@pytest.mark.parametrize(
    "code", ["|1|s|1|", ".x|1|", "|1|p|1|", "|1|+.", "|1|f", "|(p.)|p."]
)
def test_malformed_lines_raise(code: str) -> None:
    with pytest.raises(ValueError, match=r"\w"):
        out(code)
