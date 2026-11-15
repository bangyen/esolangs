"""Tests for the Chicken interpreter."""

import json
import sys
from functools import partial
from pathlib import Path

import pytest

from esolangs import ExecutionLimits, ExecutionResult, Language
from esolangs import run as execute
from esolangs.exceptions import HaltError, InterpreterLimitError
from esolangs.languages.chicken.interpreter import _Machine, run
from esolangs.runtime._isolated import termination_result_isolated
from esolangs.runtime._result_wire import decode_decision, encode_decision
from esolangs.runtime.io import ScriptedIO
from esolangs.vm import _capture_workspace, complete_vm
from tests.support.execution import termination_observed
from tests.support.raises import assert_halts_with_hint, assert_rejected_with_hint
from tests.support.vm_support import assert_rejected_output_retry

FIXTURES = Path(__file__).parent / "fixtures"


def _lines(*counts: int) -> str:
    return "".join(" ".join(["chicken"] * c) + "\n" for c in counts)


def _go(counts: tuple[int, ...], stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(_lines(*counts), io)
    return io.getvalue()


@pytest.mark.parametrize(
    ("name", "stdin", "output"),
    [
        ("hello", "", "Hello world"),
        ("hack_loop", "iiisdso", " 64 "),
        ("hack_loop", "dso", " 0 "),
        ("nan", "", "NaN"),
    ],
)
def test_wiki_programs_without_a_stated_output(name, stdin, output) -> None:
    """Outputs the page leaves unstated, checked against the programs' intent."""
    source = (FIXTURES / f"{name}.chicken").read_text()
    assert (
        execute(
            "Chicken", source, stdin=stdin, limits=ExecutionLimits(execution_timeout=10)
        ).output
        == output
    )


def test_99_chickens_counts_down_from_the_input() -> None:
    source = (FIXTURES / "99_chickens.chicken").read_text()
    out = execute(
        "Chicken", source, stdin="3", limits=ExecutionLimits(execution_timeout=10)
    ).output
    assert out == "3 chickens\n2 chickens\n1 chicken\nno chickens\n"
    assert (
        execute(
            "Chicken", source, stdin="99", limits=ExecutionLimits(execution_timeout=10)
        ).output.count("\n")
        == 100
    )


def test_empty_program_prints_the_pad() -> None:
    from .oracle_checks import check_raw_chicken

    check_raw_chicken()
    assert _go(()) == "0"
    for prefix in ((), (1, 10, 3)):
        source = _lines(*prefix, 11, 10, 15, 3, 8)
        native = termination_observed("Chicken", source, "", 1)
        assert not native.decision.halts
        assert native.decision.commands == 12
        assert termination_result_isolated("Chicken", source, "", 1) == native
        wire = json.loads(json.dumps(encode_decision(native.decision), allow_nan=False))
        assert decode_decision(wire) == native.decision


@pytest.mark.parametrize(
    ("counts", "output"),
    [
        ((12, 13, 2), "5"),  # numbers add
        ((12, 1, 2), "2chicken"),  # a string concatenates
        ((14, 13, 3), "1"),  # below minus top
        ((14, 13, 4), "12"),
        ((12, 12, 5), "true"),  # loose ==, printed as JavaScript prints it
        ((12, 1, 5), "false"),
        ((11, 1, 2, 11, 4), "NaN"),  # "1chicken" is not a number
        ((12, 1, 2, 1, 2), "2chickenchicken"),
        ((10 + 65, 9), "A"),
        # lands past the array; the pad is on top
        ((11, 13, 8), "0"),
    ],
)
def test_operators_follow_javascript(counts, output) -> None:
    assert _go(counts) == output


def test_a_taken_jump_counts_from_the_next_cell() -> None:
    # cond 1, offset 2: skips the two pushes after the jump
    assert _go((11, 12, 8, 15, 16, 17)) == "7"
    assert _go((11, 12, 8, 15, 16)) == "0"  # lands on the pad
    assert _go((10, 12, 8, 15, 16, 17)) == "7"  # cond 0: falls through to 7
    assert _go((10, 12, 8, 15, 16)) == "6"


def test_a_string_is_truthy_even_when_it_reads_as_zero() -> None:
    # input[0] is "0": push 0, load input, push 1, jump over the push 5
    assert _go((10, 6, 1, 11, 8, 15, 16), "0") == "6"


def test_load_reads_the_input_and_the_stack() -> None:
    assert _go((11, 6, 1), "xy") == "y"
    assert _go((13, 6, 0)) == "6"  # cell 3 is the second line, 6 chickens
    assert _go((16, 6, 0)) == "undefined"  # cell 6 would be the popped address
    assert _go((10 + 7, 6, 0)) == "undefined"
    assert _go((10 + 9, 6, 2)) == "undefined"  # cell 2 holds a number

    from tests.support.execution import assert_digit_cap_independent

    assert_digit_cap_independent(
        "Chicken", _lines(11, 6, 0, 6, 0), "9" * 641, "undefined"
    )

    policy = sys.get_int_max_str_digits()
    for rounds in (3, 14):
        source_lines = 1 + 4 * rounds
        top = source_lines + 3
        counts = [12]
        for _ in range(rounds):
            counts.extend((10 + top, 6, 0, 4))
        assert len(counts) == source_lines
        value = 1 << (1 << rounds)
        chunks = []
        while value:
            value, chunk = divmod(value, 10**9)
            chunks.append(chunk)
        expected = str(chunks.pop()) + "".join(
            f"{chunk:09d}" for chunk in reversed(chunks)
        )
        assert expected == "256" if rounds == 3 else len(expected) == 4933
        io = ScriptedIO()
        machine = _Machine(_lines(*counts), io)
        for _ in range(2 + 3 * rounds):
            assert not machine.halted
            machine.step()
        assert machine.halted
        assert machine.pointer == top
        assert io.getvalue() == expected
        assert (io.position(), io.reads, io.past_end) == (0, 1, 0)
    assert sys.get_int_max_str_digits() == policy


def test_store_overwrites_a_cell_and_grows_the_array() -> None:
    assert _go((15, 10 + 20, 7, 10 + 20, 6, 0)) == "5"
    assert _go((15, 10 + 20, 7, 10 + 19, 6, 0)) == "undefined"

    with pytest.raises(InterpreterLimitError, match="grow its store"):
        _go((27, 11, 6, 0, 7), "9" * 5001)


def test_input_is_the_whole_stdin(monkeypatch) -> None:
    assert _go((12, 6, 1, 12, 6, 1, 2), "a\nbcd\n") == "bb"
    policy = sys.get_int_max_str_digits()
    for digits in ("65", "0" * 5000 + "65"):
        stdin = "&#" + digits + ";"
        io = ScriptedIO(stdin)
        run(_lines(11, 6, 0), io)
        assert io.getvalue() == "A"
        assert (io.position(), io.reads, io.past_end) == (len(stdin), 1, 0)
    digits = "1" + "0" * 5000
    io = ScriptedIO("&#" + digits + ";")
    with pytest.raises(HaltError) as caught:
        run(_lines(11, 6, 0), io)
    assert str(caught.value) == "Chicken cannot print the code point " + digits
    assert (io.getvalue(), io.position(), io.reads, io.past_end) == (
        "",
        len(digits) + 3,
        1,
        0,
    )
    assert sys.get_int_max_str_digits() == policy

    for stdin in ("65", "0" * 5000 + "65"):
        io = ScriptedIO(stdin)
        machine = _Machine(_lines(11, 6, 0, 10, 3), io)
        for _ in range(5):
            assert not machine.halted
            machine.step()
        assert machine.halted
        assert machine.pointer == 8
        assert io.getvalue() == "65"
        assert (io.position(), io.reads, io.past_end) == (len(stdin), 1, 0)
    assert sys.get_int_max_str_digits() == policy

    from esolangs.languages.chicken import interpreter
    from tests.support.prepared_support import check_image_reuse

    check_image_reuse(
        "Chicken",
        _lines(11, 6, 1),
        interpreter,
        "_prepare_source",
        monkeypatch,
        cases=(("xA", "A"), ("yZ", "Z"), ("zQ", "Q")),
    )


def test_bad_words_are_rejected_with_a_repair_hint() -> None:
    assert_rejected_with_hint("Chicken", "chicken hen\n", "separated by spaces")


@pytest.mark.parametrize(
    ("counts", "message", "hint"),
    [
        ((10, 6, 0, 1, 2), "stack array", "numbers"),  # S[0] is the array
        ((10, 6, 99, 1), "undefined source", "source cell"),
        ((10, 10, 11, 3, 7), "non-index address", "non-negative"),
        ((11, 1, 8), "non-integer offset", "integer offset"),
    ],
)
def test_runtime_failures_carry_a_repair_hint(counts, message, hint) -> None:
    assert_halts_with_hint("Chicken", _lines(*counts), message, hint)


@pytest.mark.parametrize("debugger", [False, True])
@pytest.mark.parametrize(
    ("counts", "stdin", "message", "steps"),
    [
        ((11, 6, 0), "&#55296;", "code point 55296", 2),
        ((10, 6, 99, 1), "", "undefined source", 1),
        ((10, 10, 11, 3, 7), "", "non-index address -1", 4),
        ((11, 1, 8), "", "non-integer offset chicken", 2),
        ((10, 6, 0, 1, 2), "", "stack array", 3),
    ],
)
def test_fault_preserves_operands_and_instruction_on_retry(
    counts, stdin, message, steps, *, debugger: bool
) -> None:
    api = Language("Chicken")
    source = _lines(*counts)
    limits = ExecutionLimits(max_steps=steps + 1)
    if debugger:
        debug = api.make_debugger(source, stdin=stdin)
        vm = debug.vm
        assert debug.run(limits=ExecutionLimits(max_steps=steps)) == "max_steps"
        drive = partial(debug.run, limits=limits)
    else:
        vm = api.make_vm(source, stdin=stdin)
        for _ in range(steps):
            vm.step()
        drive = partial(complete_vm, vm, max_steps=steps + 1)
    state, workspace = vm.snapshot(), _capture_workspace(vm)
    for _ in range(2):
        with pytest.raises(HaltError, match=message) as stopped:
            drive()
        assert not vm.halted
        assert stopped.value.partial_output == vm.output == ""
        assert stopped.value.observation == ExecutionResult(
            "", len(stdin), 1, 0, steps=steps if debugger else 0
        )
        assert vm.snapshot() == state
        assert _capture_workspace(vm) == workspace


def test_successful_output_finishes_at_the_exact_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vm = Language("Chicken").make_vm(_lines(11, 6, 0), stdin="&#65;")
    assert complete_vm(vm, max_steps=3) == "A"
    assert vm.halted
    assert vm.ip == 6
    for source, value, prefix in (("", "0", 0), ("chicken", "chicken", 1)):
        assert_rejected_output_retry(
            "Chicken",
            source,
            value,
            value,
            prefix=prefix,
            monkeypatch=monkeypatch,
            stdin="unused",
            unchanged_if_unwritten=True,
            following_writes=(),
        )


def test_code_point_past_unicode_halts() -> None:
    with pytest.raises(HaltError, match="code point"):
        _go((10 + 99, 10 + 99, 4, 10 + 99, 4, 10 + 99, 4, 9))


def test_a_huge_store_address_is_refused() -> None:
    nines = (10 + 9, 4) * 7
    with pytest.raises(InterpreterLimitError):
        _go((11, 10 + 9, *nines, 7))
