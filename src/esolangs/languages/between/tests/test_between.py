"""Tests for the Between interpreter."""

from itertools import product

import pytest

from esolangs import ExecutionCapError, ExecutionLimits, ExecutionResult, Language
from esolangs import run as run_public
from esolangs.exceptions import HaltError
from esolangs.languages.between.interpreter import run
from tests.interpreters.runner import native_runner
from tests.support.vm_support import assert_rejected_output_retry

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


@pytest.mark.medium
def test_line_input_and_output_caps_preserve_python_code_points(monkeypatch) -> None:
    api = Language("Between")
    code = "'x'v.\n[x]i.\n[x]p."
    assert_rejected_output_retry(
        "Between",
        code,
        "AB",
        "AB",
        prefix=2,
        monkeypatch=monkeypatch,
        stdin="AB\nZ",
        unchanged_if_unwritten=True,
        following_writes=(),
    )
    text = "\U0001f600\ud800\udfff\r"
    prepared = api.prepare(code)
    result = api.run(code, stdin=text)
    assert (result.output, result.input_position, result.input_reads) == (text, 4, 1)
    assert prepared.run(stdin=text) == result
    assert api.run(code, stdin=text, isolated=True) == result

    steps = ExecutionLimits(max_steps=3)
    expected = ExecutionResult(text, 4, 1, 0, completion=result.completion, steps=3)
    assert prepared.run(stdin=text, limits=steps) == expected
    assert api.run(code, stdin=text, limits=steps) == expected
    debugger = prepared.make_debugger(stdin=text)
    assert debugger.run(limits=steps) == "halted"
    assert debugger.observation == expected

    exact = ExecutionLimits(max_steps=3, max_output=len(text))
    assert prepared.run(stdin=text, limits=exact) == expected
    for limit in (2, 3):
        with pytest.raises(ExecutionCapError, match="output limit") as caught:
            prepared.run(
                stdin=text, limits=ExecutionLimits(max_steps=3, max_output=limit)
            )
        assert caught.value.partial_output == text[:limit]
        assert caught.value.observation == ExecutionResult(
            text[:limit], 4, 1, 0, steps=2
        )

    crlf = api.run(code, stdin=text + "\n", isolated=True)
    assert crlf.output == text[:-1]
    assert crlf.input_position == len(text) + 1

    pending = api.make_debugger("[x]i.", stdin="first\nsecond")
    with pytest.raises(HaltError, match="undeclared variable") as first:
        pending.step()
    assert first.value.observation.input_position == 6
    assert first.value.observation.input_reads == 1
    snapshot = pending.snapshot()
    with pytest.raises(HaltError, match="undeclared variable") as retry:
        pending.step()
    assert retry.value is not first.value
    assert retry.value.observation == first.value.observation
    assert pending.snapshot() == snapshot

    from esolangs import ExecutionTimeoutError
    from esolangs.runtime.io import ScriptedIO

    read = ScriptedIO.input_str

    def fail_after_read(io, prompt="Input: "):
        read(io, prompt)
        error = ExecutionTimeoutError("reader exhausted its time budget")
        error.bound = "execution_timeout"
        raise error

    monkeypatch.setattr(ScriptedIO, "input_str", fail_after_read)
    pending = api.make_debugger(code, stdin="first\nsecond")
    pending.step()
    with pytest.raises(ExecutionTimeoutError) as first:
        pending.step()
    first.value.add_note("from the first observer")
    with pytest.raises(ExecutionTimeoutError) as retry:
        pending.step()
    assert retry.value is not first.value
    assert retry.value.bound == first.value.bound == "execution_timeout"
    assert retry.value.__notes__ == first.value.__notes__[:-1]
    assert retry.value.observation == first.value.observation
    assert pending.observation.input_reads == 1


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


def test_wide_numbers_survive_literals_input_conversion_and_output() -> None:
    from tests.support.execution import assert_digit_cap_independent

    digits = "9" * 641
    source = f"|{digits}|c.\n'x'v.\n[x]i.\n|[x]c.|p.\n|{digits}|p."
    assert_digit_cap_independent("Between", source, digits, digits * 2)
    with pytest.raises(HaltError, match="outside the program") as error:
        out("|" + "1" + "0" * 5000 + "|f.")
    assert str(error.value).startswith("goto 1" + "0" * 5000)
