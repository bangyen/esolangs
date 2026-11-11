"""Tests for the Aprknia interpreter."""

import pytest

from esolangs.languages.aprknia import interpreter as native
from esolangs.languages.aprknia.interpreter import run
from tests.interpreters.runner import native_runner
from tests.support.prepared_support import check_image_reuse

#: Pushes 7 then 3, b and a for the page's snippets.
_SEVEN_THREE = "11*!!!!" + "1*!!!!" * 5 + "11*!!!!1*!!!!"
#: Prints the top as an integer (selector 2), then drops it.
_PRINT = "11*!!!!,!"


_out = native_runner(run)


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
    from esolangs.languages.aprknia.tests.oracle_checks import check_raw_aprknia

    check_raw_aprknia()
    # -1 / 2 is 0 and -1 mod 2 is -1; 1 / 0 and 1 mod 0 are both 0.
    minus_one = "11*!!!~!1*!!!~!"
    assert _out(minus_one + "11*!!!!*!~!~!~!" + _PRINT) == "0"
    assert _out(minus_one + "11*!!!!*~!~!~!~!" + _PRINT) == "-1"
    assert _out("111*!!!~!*~!~!~!~!" + _PRINT) == "0"


def test_reads_and_prints_a_byte() -> None:
    # Selector 0 reads, selector 1 prints the byte back.
    assert _out("11*!!!~!,1,", "A") == "A"


def test_loop_runs_while_positive(monkeypatch: pytest.MonkeyPatch) -> None:
    # 3 counts down to 0, printing each step's value.
    three = "11*!!!!1*!!!!"
    assert _out(three + "[" + _PRINT[:-1] + "1*!!!~!]") == "321"
    check_image_reuse(
        "Aprknia",
        three + "[" + _PRINT[:-1] + "1*!!!~!]",
        native,
        "_prepare_source",
        monkeypatch,
        cases=(("", "321"),) * 3,
    )


@pytest.mark.parametrize("code", ["[", "]"])
def test_unmatched_brackets(code: str) -> None:
    with pytest.raises(ValueError, match="unmatched"):
        _out(code)
