"""Tests for the Pilas interpreter."""

import sys
from decimal import Decimal

import pytest

from esolangs.languages.pilas.interpreter import run
from tests.interpreters.runner import native_runner
from tests.support.vm_support import assert_rejected_output_retry

_out = native_runner(run)


def test_arithmetic_pops_a_then_b() -> None:
    from esolangs.languages.pilas.tests.oracle_checks import check_raw_pilas

    check_raw_pilas()
    # 9 6 - is b - a = 3, printed as '3' after adding 48.
    assert _out("96-6:+:+:++.\n0{0}") == "3"

    _check_out_of_range_character()


def _check_out_of_range_character() -> None:
    import esolangs

    api = esolangs.Language("Pilas")
    previous = sys.get_int_max_str_digits()
    try:
        sys.set_int_max_str_digits(640)
        for doublings in (0, 18, 2200):
            line = "99.9" + ":+" * doublings + "."
            source = line + "\n" + " " * len(line)
            prepared = api.prepare(source)
            bound = 2 * len(line)
            bounded = esolangs.ExecutionLimits(max_steps=bound)
            outcomes = (
                (api.execute(source), False),
                (api.execute(source, limits=bounded), True),
                (prepared.execute(), False),
                (prepared.execute(limits=bounded, isolated=True), True),
            )
            for outcome, counts_steps in outcomes:
                if not doublings:
                    result = outcome.unwrap()
                    assert result.output == "\t\t"
                    assert result.steps == (bound - 1 if counts_steps else None)
                    continue
                value = Decimal(9 << doublings)
                assert outcome.status == "fault"
                assert type(outcome.error) is esolangs.HaltError
                assert outcome.error.args == (
                    f"'.' cannot print {value} as a character",
                )
                assert outcome.error.partial_output == "\t"
                assert outcome.observation == esolangs.ExecutionResult(
                    "\t", 0, 0, 0, steps=bound - 2 if counts_steps else None
                )
    finally:
        sys.set_int_max_str_digits(previous)


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


def test_reads_bytes(tmp_path, monkeypatch) -> None:
    import esolangs

    source = ",.\n  "
    assert _out(source, "A") == "A"
    assert_rejected_output_retry(
        "Pilas",
        source,
        "A",
        "A",
        prefix=2,
        stdin="A",
        monkeypatch=monkeypatch,
        unchanged_if_unwritten=True,
        following_writes=(),
    )
    api = esolangs.Language("Pilas")
    path = tmp_path / "source.txt"
    path.write_bytes((source + "\r\n").encode())
    assert api.from_file(path).source == source + "\r\n"
    for program in (source + "\r\n", path):
        for options in ({}, {"limits": esolangs.ExecutionLimits(max_steps=100)}):
            with pytest.raises(esolangs.ProgramError, match="lines"):
                api.run(program, stdin="A", **options)
    native = api.from_file(path, normalize=True)
    assert native.source == source
    assert api.run(native, stdin="A").output == "A"
    api.to_file(api.from_source(source), path)
    assert path.read_bytes() == source.encode()
    assert api.run(path, stdin="A").output == "A"
    api.to_file(api.from_source(source), path, normalize=True)
    assert path.read_bytes() == (source + "\n").encode()

    from esolangs.languages.pilas import interpreter
    from tests.support.prepared_support import check_image_reuse

    check_image_reuse(
        "Pilas",
        ",.1{x}xx\nxxxxxxxxx",
        interpreter,
        "_parse",
        monkeypatch,
    )


@pytest.mark.parametrize(
    ("code", "match"),
    [("{\n", "unmatched"), ("}\n", "unmatched"), ("a\nb\nc", "lines")],
)
def test_malformed_programs(code: str, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        _out(code)
