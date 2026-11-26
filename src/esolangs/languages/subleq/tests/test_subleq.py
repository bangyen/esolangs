"""Tests for the Subleq interpreter."""

import random
import sys
from functools import partial

import pytest

from esolangs import (
    ArgumentError,
    ExecutionLimits,
    InterpreterLimitError,
    Language,
    ProgramError,
)
from esolangs.languages.subleq.interpreter import _Machine
from esolangs.languages.subleq.interpreter import run as run_subleq
from esolangs.registry._certification import load as load_certification
from esolangs.runtime.io import ScriptedIO
from esolangs.vm import complete_vm
from tests.interpreters.semantic_oracles import STDINS, agrees
from tests.interpreters.semantic_oracles import subleq as oracle
from tests.support.bit_lifecycle import check_byte_retry
from tests.support.raises import assert_halts_with_hint, assert_rejected_with_hint


@pytest.mark.medium
def test_bad_programs_carry_a_repair_hint() -> None:
    assert_rejected_with_hint("Subleq", "x", "decimal integers")
    assert_halts_with_hint("Subleq", "0 0", "incomplete Subleq", "three addresses")

    from .workspace_checks import check_workspace_subleq

    check_workspace_subleq(_corpus)


def _corpus():
    yield from ["", "12 13 -1", "3 -1 0 321", "-1 9 0 9 -1 0 9 9 -1 0", "0 0 0"]
    yield from ["9 3 3 9 -1 6 9 9 -1 3", "12 13 6 12 -1 9 13 -1 9 12 12 -1 3 2"]
    rng = random.Random(1702)
    for _ in range(96):
        cells = []
        for _ in range(3):
            a, b = rng.choice([9, 10, 11]), rng.choice([9, 10, 11])
            mode = rng.randrange(3)
            if mode == 1:
                a = -1
            elif mode == 2:
                b = -1
            cells.extend([a, b, rng.choice([-1, 0, 3, 6, 12])])
        cells.extend(rng.choices([-257, -1, 0, 1, 256, 321], k=3))
        yield " ".join(map(str, cells))


@pytest.mark.parametrize("stdin", STDINS)
def test_bounded_programs_match_the_oracle(stdin) -> None:
    for code in _corpus():
        agrees(_Machine, oracle, code, stdin)


@pytest.mark.parametrize(
    ("code", "outcome"),
    [
        ("x", ValueError),
        ("0", RuntimeError),
        ("-2 0 -1", ValueError),
        ("6 -1 0 6 6 -1 -1", "\xff"),
    ],
)
def test_oracle_controls(code, outcome) -> None:
    result = agrees(_Machine, oracle, code, "\x81")
    if isinstance(outcome, str):
        assert (result.halted, result.output) == (True, outcome)
    else:
        assert isinstance(result, outcome)
    assert not agrees(_Machine, oracle, "0 0 0", "").halted


def test_subleq_direct_jump_and_output(monkeypatch: pytest.MonkeyPatch) -> None:
    code = "9 -1 3 10 -1 6 0 0 -1 72 105"
    io = ScriptedIO()
    run_subleq(code, io)
    assert io.getvalue() == "Hi"
    check_byte_retry("Subleq", code, "Hi", 0, monkeypatch)


def test_subleq_input_and_eof(monkeypatch) -> None:
    code = "-1 9 3 9 -1 6 0 0 -1 0"
    from esolangs.languages.subleq import interpreter
    from tests.support.prepared_support import check_image_reuse

    check_image_reuse("Subleq", code, interpreter, "parse_int_memory", monkeypatch)
    io = ScriptedIO("A")
    run_subleq(code, io)
    assert io.getvalue() == "A"
    with pytest.raises(EOFError):
        run_subleq(code, ScriptedIO())

    from esolangs.languages.subleq.descriptor import LANGUAGE

    io = ScriptedIO("A")
    machine = _Machine("-1 9 3 9 -1 6 10 10 -1 0 0", io)
    for _ in range(3):
        machine.step()
    assert machine.halted
    assert io.getvalue() == "A"
    state = machine.snapshot()
    assert state[-1] > 0
    assert load_certification(LANGUAGE).payload is not None
    assert load_certification(LANGUAGE).payload(state) == (state[0], (), machine.ip, 0)
    assert load_certification(LANGUAGE).payload(
        (*state[:-1], 100)
    ) == load_certification(LANGUAGE).payload(state)


@pytest.mark.parametrize("code", ["-1 -2 0", "-2 0 0", "0 -2 0"])
def test_subleq_rejects_negative_data_addresses(code: str) -> None:
    with pytest.raises(ValueError, match="Subleq"):
        run_subleq(code, ScriptedIO("A"))


def test_subleq_zero_extended_memory() -> None:
    run_subleq("10 10 -1", ScriptedIO())


@pytest.mark.parametrize("debugger", [False, True])
def test_failed_subtraction_write_does_not_halt_on_retry(*, debugger: bool) -> None:
    api = Language("Subleq")
    code = f"6 -1 0 6 {10**30} 7 65"
    limits = ExecutionLimits(max_steps=2)
    if debugger:
        debug = api.make_debugger(code)
        vm = debug.vm
        drive = partial(debug.run, limits=limits)
    else:
        vm = api.make_vm(code)
        drive = partial(complete_vm, vm, max_steps=2)
    initial_memory = vm.memory
    for _ in range(2):
        with pytest.raises(InterpreterLimitError, match="grow its store") as stopped:
            drive()
        assert stopped.value.partial_output == vm.output == "A"
        assert stopped.value.observation.completion is None
        assert not vm.halted
        assert vm.ip == 3
        assert vm.memory == initial_memory


def test_successful_subtraction_write_takes_the_halt_jump() -> None:
    vm = Language("Subleq").make_vm("6 -1 0 6 6 7 65")
    assert complete_vm(vm, max_steps=2) == "A"
    assert vm.halted
    assert vm.ip == 7
    assert vm.memory[6] == 0


def test_large_addresses_keep_their_diagnostic_types() -> None:
    api = Language("Subleq")
    digits = "9" * 700
    cap = sys.get_int_max_str_digits()
    try:
        sys.set_int_max_str_digits(sys.int_info.str_digits_check_threshold)
        debugger = api.make_debugger(f"0 0 {digits}")
        debugger.step()
        assert debugger.halted
        with pytest.raises(ArgumentError, match=r"currently <integer with \d+ bits>"):
            debugger.break_at((0, 0))
        with pytest.raises(
            ProgramError, match=r"invalid Subleq data address <negative integer"
        ):
            api.run(f"-{digits} 0 0").unwrap()
    finally:
        sys.set_int_max_str_digits(cap)
