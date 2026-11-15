"""Forbin through the shared API, CLI and machinery."""

import pytest

import esolangs.debugger as debugger_api
from esolangs import ExecutionResult, Language
from esolangs.exceptions import HaltError, InputExhaustedError
from esolangs.vm import run_until_halt, run_until_halt_or_ancestor
from tests.support.vm_support import assert_proof_fault


@pytest.mark.parametrize("debugged", [False, True])
def test_live_detectors_keep_vm_fault_evidence(*, debugged: bool) -> None:
    assert_proof_fault(
        run_until_halt_or_ancestor,
        "Forbin",
        "main { out 0,1,0,0,0,0,0,1; x = (in 0); }",
        InputExhaustedError,
        "A",
        debugged=debugged,
    )


@pytest.mark.parametrize("debugged", [False, True])
def test_ancestor_detector_recognizes_a_known_halt_at_zero_budget(
    *, debugged: bool
) -> None:
    make = debugger_api.make_debugger if debugged else debugger_api.make_vm
    machine = make("Forbin", "main { x = 1; }")
    snapshot = machine.snapshot()
    with pytest.raises(TimeoutError, match="after 0 pushed frames"):
        run_until_halt_or_ancestor(machine, limit=0)
    assert machine.snapshot() == snapshot
    assert run_until_halt(machine, limit=2) is True
    snapshot = machine.snapshot()
    assert run_until_halt_or_ancestor(machine, limit=0) is True
    assert machine.snapshot() == snapshot


def test_ancestor_detector_examines_the_last_allowed_push() -> None:
    source = "main { f 0; }\nf x { f 0; }"
    machine = debugger_api.make_vm("Forbin", source)
    with pytest.raises(TimeoutError, match="after 1 pushed frames"):
        run_until_halt_or_ancestor(machine, limit=1)
    machine = debugger_api.make_vm("Forbin", source)
    assert run_until_halt_or_ancestor(machine, limit=2) is False


@pytest.mark.medium
@pytest.mark.parametrize(
    ("expression", "stdin", "error_type", "first_past_end", "replay"),
    [
        ("return (in 0);", "", InputExhaustedError, 1, ()),
        ("b = (in 0); return missing;", "Q", HaltError, 0, (ord("Q"),)),
    ],
)
def test_failed_expression_retries_keep_input_and_output_evidence(
    expression, stdin, error_type, first_past_end, replay
) -> None:
    api = Language("Forbin")
    source = f"f {{ out 0,1,0,0,0,0,0,1; {expression} }}\nmain {{ x = (f 0); }}"
    consumed = len(stdin)
    for outcome in (
        api.execute(source, stdin=stdin),
        api.prepare(source).execute(stdin=stdin),
        api.execute(source, stdin=stdin, isolated=True),
    ):
        assert type(outcome.error) is error_type
        assert outcome.observation == ExecutionResult(
            "A", consumed, consumed, first_past_end
        )

    debugger = api.make_debugger(source, stdin=stdin)
    position = debugger.ip
    fault_state = None
    for attempt in (1, 2):
        with pytest.raises(error_type) as stopped:
            debugger.step()
        assert debugger.ip == position
        assert stopped.value.observation == ExecutionResult(
            "A", consumed, consumed, attempt * first_past_end, steps=0
        )
        snapshot = debugger.snapshot()
        assert snapshot[-1] == (replay, 1)
        if fault_state is not None:
            assert snapshot == fault_state
        fault_state = snapshot


class TestForbin:
    def test_locals_and_cursor(self) -> None:
        vm = debugger_api.make_vm("Forbin", "main { x = 1; }")
        assert vm.ip == (0,)
        assert vm.memory == []
        assert vm.stack == []
        vm.step()
        assert vm.ip == (1,)
        assert vm.memory == [1]
        vm.step()  # main's body is exhausted; the frame pops
        assert vm.halted
        assert vm.memory == []  # the frame stack has emptied

    def test_ip_exposes_the_call_stack(self) -> None:
        # a statement-position call pushes a new frame, deepening ip
        vm = debugger_api.make_vm("Forbin", "main { f 0; }\nf x { y = 1; }")
        assert vm.ip == (0,)
        vm.step()  # f 0; pushes a frame for f, advancing main's own cursor
        assert vm.ip == (1, 0)
        vm.step()  # y = 1; inside f
        assert vm.ip == (1, 1)
        vm.step()  # f's body is exhausted; the frame pops
        assert vm.ip == (1,)
        vm.step()  # main's body is exhausted; the frame pops
        assert vm.halted
