"""Tests for the Aprknia interpreter."""

import sys
from decimal import Decimal

import pytest

from esolangs import ExecutionLimits, ExecutionResult, HaltError, Language
from esolangs.languages.aprknia import interpreter as native
from esolangs.languages.aprknia.interpreter import run
from tests.interpreters.runner import native_runner
from tests.support.prepared_support import check_image_reuse
from tests.support.vm_support import assert_rejected_output_retry

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


def test_reads_and_prints_a_byte(monkeypatch: pytest.MonkeyPatch) -> None:
    # Selector 0 reads, selector 1 prints the byte back.
    assert _out("11*!!!~!,1,", "A") == "A"
    assert_rejected_output_retry(
        "Aprknia",
        "11*!!!~!,1,",
        "A",
        "A",
        prefix=10,
        stdin="Aq",
        monkeypatch=monkeypatch,
        unchanged_if_unwritten=True,
        following_writes=(),
    )
    _check_wide_output()


def _check_wide_output() -> None:
    api = Language("Aprknia")
    two = "11*!!!!"
    doublings = 2300
    # Double the top, then discard the two other arithmetic results.
    prefix = "11," + two + (two + "*!!~!~!") * doublings
    decimal = str(Decimal(1 << (doublings + 1)))
    previous = sys.get_int_max_str_digits()
    try:
        sys.set_int_max_str_digits(640)
        for selector, character in (("1", True), (two, False)):
            source = prefix + selector + ","
            prepared = api.prepare(source)
            limits = ExecutionLimits(max_steps=len(source))
            for outcome, bounded in (
                (api.execute(source), False),
                (api.execute(source, limits=limits), True),
                (prepared.execute(), False),
                (prepared.execute(limits=limits, isolated=True), True),
            ):
                if character:
                    assert outcome.status == "fault"
                    assert type(outcome.error) is HaltError
                    assert outcome.error.args == (
                        f"',' cannot print {decimal} as a character",
                    )
                    assert outcome.observation == ExecutionResult(
                        "\x01", 0, 0, 0, steps=len(source) - 1 if bounded else None
                    )
                else:
                    result = outcome.unwrap()
                    assert result.output == "\x01" + decimal
                    assert result.steps == (len(source) if bounded else None)
    finally:
        sys.set_int_max_str_digits(previous)


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
