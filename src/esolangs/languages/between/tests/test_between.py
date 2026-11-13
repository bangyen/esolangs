"""Tests for the Between interpreter."""

from itertools import product

import pytest

from esolangs import ExecutionLimits
from esolangs import run as run_public
from esolangs.exceptions import HaltError
from esolangs.languages.between.interpreter import run
from tests.interpreters.runner import native_runner

out = native_runner(run)


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
        # Line 0 is the first instruction; blanks and ``#`` lines are not counted.
        ("# top\n\n|2|f.\n|1|p.\n|0|p.\n.x.", "0"),
        ("'a'v.\n[a]p.", "0"),
    ],
)
def test_conditions_nest(code: str, printed: str) -> None:
    assert out(code) == printed


@pytest.mark.medium
def test_apostrophes_in_strings() -> None:
    """A string closes at the first apostrophe an operation follows."""
    assert out("'can't stop'p.") == "can't stop"
    with pytest.raises(ValueError, match="unterminated"):
        out("'it's'p.")
    for text in ("\ud800\udfff", "\ud800", "\udfff", "\U000103ff"):
        assert (
            run_public(
                "Between",
                f"'{text}'p.",
                isolated=True,
                limits=ExecutionLimits(max_output=len(text)),
            ).output
            == text
        )


def test_groups_nest_and_compute(monkeypatch) -> None:
    from esolangs.languages.between import interpreter
    from tests.support.prepared_support import check_image_reuse

    check_image_reuse(
        "Between",
        "'a'v.\n[a]s|12|\n[a]p.",
        interpreter,
        "_parse",
        monkeypatch,
        cases=(("", "12"), ("", "12"), ("", "12")),
    )
    assert out("'a'v.\n[a]s|3|\n[a]s|[a]+|4||\n[a]s|[a]*|[a]+|1|||\n[a]p.") == "56"
    assert out("'a'v.\n[a]s|'12'c.|\n[a]p.") == "12"

    for a, b, c in product((*range(5), 65536), range(4), range(3)):
        code = f"'a'v.\n[a]s|{a}|\n[a]s|[a]+|{b}||\n[a]s|[a]*|[a]+|{c}|||\n[a]p."
        assert out(code) == str((a + b) * (a + b + c)), code


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
