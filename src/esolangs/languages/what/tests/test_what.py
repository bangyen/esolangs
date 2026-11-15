"""Tests for the What!? interpreter."""

import sys
from dataclasses import replace

import pytest

from esolangs import ExecutionLimits, Language
from esolangs import run as public_run
from esolangs.exceptions import ArgumentError, HaltError, ProgramError
from esolangs.languages.what import interpreter as native
from esolangs.languages.what.interpreter import _Machine, run
from esolangs.results import ExecutionResult
from esolangs.runtime._state import WorkspaceVariant
from esolangs.runtime.io import ScriptedIO
from esolangs.vm import _capture_workspace
from tests.interpreters.runner import native_runner
from tests.support.execution import assert_digit_cap_independent
from tests.support.prepared_support import check_image_reuse
from tests.support.vm_support import assert_rejected_input_retry


@pytest.mark.medium
@pytest.mark.parametrize(
    ("source", "stdin", "valid", "output", "position", "error_type"),
    [
        ("??!!", "oops 7", "7", "7", 4, ArgumentError),
        ("??!!", "70000 7", "7", "7", 5, HaltError),
        ("?!!", "\U00010000A", "A", "65", 1, HaltError),
        ("???!!!", "z" * 257 + "\nok", "ok", "ok", 258, HaltError),
    ],
)
def test_rejected_reads_of_each_width_keep_the_original_fault(
    source, stdin, valid, output, position, error_type
) -> None:
    assert_rejected_input_retry(
        "What!?",
        source,
        stdin,
        valid,
        output,
        position=position,
        reads=1,
        error_type=error_type,
    )


_TRUTH = ".??([1:!!][1;,1.(-)]),0!!"
_BOTTLES = r"""99 " bottles of beer on the wall, ".
" bottles of beer.\n".
"Take one down and pass it around, ".
" bottles of beer on the wall.".
,,,,'s'
(!! !!! !! . !!! . !!! ,, 's'[0:......"no more"!!!,,,,,,][0;!!] ...!!!,,, !!!!)
...."No more bottles of beer on the wall, no more bottles of beer."!!!. !!!!
"Go to the store and buy some more, 99 bottles of beer on the wall."!!! !!!!"""


_run = native_runner(run)


def test_wiki_hello_world_and_cat(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _run('"Hello, World!"!!! !!!!') == "Hello, World!\n"
    assert _run("???!!!", "a line\nmore") == "a line"
    check_image_reuse("What!?", "???!!!", native, "parse", monkeypatch)


def test_wiki_truth_machine() -> None:
    # Input 0: ``(-)`` wraps 0 - 1 and counts down to 0 again.
    assert _run(_TRUTH, "0") == "0"
    io = ScriptedIO("1")
    machine = _Machine(_TRUTH, io)
    for _ in range(1000):
        machine.step()
    assert not machine.halted
    assert set(io.getvalue()) == {"1"}


def test_wiki_99_bottles_counts_from_98() -> None:
    # The ``'s'`` before the loop takes one bottle before the first verse.
    lines = _run(_BOTTLES).split("\n")
    assert lines[0] == "98 bottles of beer on the wall, 98 bottles of beer."
    assert (
        lines[-4]
        == "Take one down and pass it around, no more bottles of beer on the wall."
    )
    assert lines[-2].startswith("Go to the store")


def test_output_and_operator_runs_split_greedily(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # ``!!!!!!!`` is ``!!!!`` then ``!!!``; ``?????`` is ``???`` then ``??``.
    assert _run('"x"!!!!!!!') == "\nx"
    assert _run("?????!!!!!!!", "ab\n7") == "\nab"
    assert _run("?????!! !!!", "ab\n7") == "7ab"
    _check_output_retry(monkeypatch)


def test_arithmetic_uses_the_slot_to_the_left_and_wraps() -> None:
    from .oracle_checks import check_raw_what

    check_raw_what()
    assert _run("6.7*!!") == "42"
    assert _run("6.7-!!") == "1"
    assert _run("7.6-!!") == "65535"
    assert _run("3.7/!!") == "2"
    assert _run("5'abc'!!") == "2"
    assert _run("300.300*!!") == str(300 * 300 % 65536)


def test_conditionals_combine_operators() -> None:
    cases = {":": "5", ";": "", "<": "", ">": "", "<:": "5", ">:": "5"}
    for ops, want in cases.items():
        assert _run(f"5[5{ops}!!]") == want, ops
    assert _run("5[3<!!]") == "5"
    assert _run("5[3<;!!]") == ""
    assert _run("5[3<>!!]") == "5"
    assert _run('"ab"["ab":!!!]["b">!!!]["a";1!!]') == "abab1"
    # A literal below the string is "smaller" only when it really sorts below.
    assert _run('"b"["a"<1!!]') == "1"
    assert _run('"a"["b"<1!!]') == ""


def test_ip_is_minus_one_once_halted() -> None:
    machine = _Machine("1", ScriptedIO())
    assert machine.ip == 0
    machine.step()
    assert machine.halted
    assert machine.ip == -1


def test_a_false_conditional_skips_to_the_next_bracket() -> None:
    # Markers are read individually: the skip lands inside the outer body.
    assert _run("1[0:[1:2]3!!]") == "3"
    assert _run("1[1:[0:2]3!!]") == "3"
    # A true ``[0:(]`` opens a loop, closed outside the conditional.
    assert _run("0[0:(]!!)") == "0"


def test_reads_at_eof() -> None:
    assert _run("5?!!") == "0"
    assert _run("5??!!") == "0"
    assert _run('"a"???!!!') == "a"


def test_errors() -> None:
    with pytest.raises(HaltError, match="left the 256-slot tape"):
        _run(",")
    with pytest.raises(HaltError, match="no previous value"):
        _run("+")
    with pytest.raises(HaltError, match="division by zero"):
        _run(".1/")
    with pytest.raises(HaltError, match="exceeds 256 characters"):
        _run('"' + "x" * 257 + '"')
    with pytest.raises(HaltError, match="does not fit 16 bits"):
        _run("??", "70000")
    with pytest.raises(HaltError, match="surrogate"):
        _run("55296!")
    with pytest.raises(ArgumentError):
        _run("??", "x")
    for bad, match in [
        ('"a', "unterminated string"),
        ("'a", "unterminated quote"),
        ("(", "unmatched '\\('"),
        (")", "unmatched '\\)'"),
        ("[1:", "lacks a '\\]'"),
        ("[:]", "lacks a literal"),
        ("[1]", "bad conditional operator"),
        ("[1::]", "bad conditional operator"),
        ("65536", "exceeds 65535"),
        ('"\\t"', "unknown escape"),
    ]:
        with pytest.raises(ValueError, match=match):
            _run(bad)

    policy = sys.get_int_max_str_digits()
    digits = "1" + "0" * 5000
    for sign in ("+", "-"):
        text = sign + digits
        message = (
            f"What!?: input {'-' if sign == '-' else ''}{digits} does not fit 16 bits"
        )
        io = ScriptedIO(text + "\nQ")
        machine = _Machine("??", io)
        before = machine.state
        with pytest.raises(HaltError) as caught:
            machine.step()
        assert type(caught.value) is HaltError
        assert str(caught.value) == message
        assert machine.state == before
        assert not machine.halted
        assert machine.ip == 0
        assert (io.getvalue(), io.position(), io.progress(), io.reads, io.past_end) == (
            "",
            len(text),
            len(text),
            1,
            0,
        )
        assert io.input_char() == ord("\n")
        assert io.input_char() == ord("Q")
        for bound in (None, 2):
            with pytest.raises(HaltError) as public:
                public_run(
                    "What!?",
                    "??",
                    stdin=text + "\nQ",
                    limits=ExecutionLimits(max_steps=bound),
                )
            assert type(public.value) is HaltError
            assert str(public.value) == message
            assert public.value.partial_output == ""
            assert public.value.observation == ExecutionResult(
                "", len(text), 1, 0, completion=None, steps=None if bound is None else 0
            )
    text = "0" * 5000 + "65"
    assert _run("??!!", text + "\nQ") == "65"
    for bound in (None, 2):
        result = public_run(
            "What!?",
            "??!!",
            stdin=text + "\nQ",
            limits=ExecutionLimits(max_steps=bound),
        )
        assert (
            result.output,
            result.input_position,
            result.input_reads,
            result.input_past_end,
        ) == ("65", len(text), 1, 0)
        assert result.completion is not None
        assert result.completion.kind.value == "halted"
        assert result.steps == (None if bound is None else 2)
    assert sys.get_int_max_str_digits() == policy

    _check_wide_source_literals()


def _check_wide_source_literals() -> None:
    api = Language("What!?")
    zeros = "0" * 641
    source = f"{zeros}65[{zeros}65:!]"
    assert_digit_cap_independent("What!?", source, "", "A")
    digits = "9" * 641
    previous = sys.get_int_max_str_digits()
    try:
        sys.set_int_max_str_digits(640)
        assert api.run(source, limits=ExecutionLimits(max_steps=8)).output == "A"
        for invalid, offset in ((digits, 0), (f"65[{digits}:!]", 3)):
            for options in (
                {},
                {"limits": ExecutionLimits(max_steps=8)},
                {"isolated": True},
            ):
                outcome = api.execute(invalid, **options)
                assert outcome.status == "rejected"
                assert type(outcome.error) is ProgramError
                assert str(outcome.error) == (
                    f"What!?: literal {digits} at offset {offset} exceeds 65535"
                )
    finally:
        sys.set_int_max_str_digits(previous)


def _check_output_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    api = Language("What!?")
    limits = ExecutionLimits(max_steps=8)
    write = ScriptedIO._write
    attempts: list[object] = []
    prefix = ""

    def reject_first(port: ScriptedIO, value: object) -> None:
        attempts.append(value)
        if len(attempts) == 1:
            write(port, prefix)
            raise HaltError("temporary write refusal")
        write(port, value)

    for source, first, second in (
        ("65!66!", "A", "B"),
        ("123!!65!", 123, "A"),
        ('"abc"!!!"d"!!!', "abc", "abcd"),
    ):
        clean = api.make_debugger(source)
        assert clean.run(limits=limits) == "halted"
        text = str(first)
        assert clean.observation.output == text + second
        for accepted in range(len(text) + 1):
            attempts.clear()
            prefix = text[:accepted]
            replay = api.make_debugger(source)
            replay.step()
            before = replay.observation
            boundary = replay.snapshot()
            workspace = _capture_workspace(replay.vm)
            with monkeypatch.context() as scoped:
                scoped.setattr(ScriptedIO, "_write", reject_first)
                with pytest.raises(HaltError, match="write refusal") as exc:
                    replay.step()
                partial = replace(before, output=prefix)
                assert exc.value.observation == replay.observation == partial
                if accepted:
                    instruction, *components = workspace.parts
                    assert replay.snapshot() == (*boundary, accepted)
                    assert _capture_workspace(replay.vm).parts == (
                        WorkspaceVariant("pending_output", (instruction, accepted)),
                        *components,
                    )
                else:
                    assert replay.snapshot() == boundary
                    assert _capture_workspace(replay.vm) == workspace
                assert replay.run(limits=limits) == "halted"
            retry = (
                []
                if accepted == len(text)
                else [text[accepted:] if accepted else first]
            )
            assert attempts == [first, *retry, second]
            assert type(attempts[0]) is type(first)
            assert replay.observation == clean.observation
            assert replay.snapshot() == clean.snapshot()
            assert _capture_workspace(replay.vm) == _capture_workspace(clean.vm)
            assert exc.value.observation == partial
