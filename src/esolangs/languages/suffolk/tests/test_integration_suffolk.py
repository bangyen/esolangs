"""Suffolk through the shared API, CLI and machinery."""

from pathlib import Path
from types import SimpleNamespace

import pytest

import esolangs
import esolangs.debugger as debugger_api
from esolangs import run
from esolangs.runtime._lifecycle import POST_HALT_REPORT, Completion
from esolangs.runtime.io import ScriptedIO
from esolangs.vm import (
    complete_vm,
    make_vm,
    run_until_halt,
    run_until_halt_or_cycle,
    run_until_halt_or_value_growth,
)
from tests.support.certification_barrier import guarded_worker
from tests.support.cli_support import run_cli
from tests.support.execution import run_observed
from tests.support.generator_support import evaluate_generated
from tests.support.vm_support import _STEP_BUDGET, _row


class TestSelfHaltsIsAWarningNotAGuarantee:
    """``False`` promised the step loop never returns.  It can."""

    def test_a_bare_step_loop_halts_and_the_wording_says_so(self) -> None:
        program = esolangs.generate("Suffolk", "0110")
        vm = debugger_api.make_vm(
            "Suffolk", program, stdin=esolangs.encode_inputs("Suffolk", [1, 0])
        )
        steps = 0
        while not vm.halted and steps < 100_000:
            vm.step()
            steps += 1
        assert vm.halted
        assert vm.output == "1"
        doc = debugger_api.VM.self_halts.__doc__ or ""
        assert "does not promise" in doc
        # The fact lives on Suffolk, not in the shared VM docstring.
        assert "Suffolk" not in doc
        assert "does not promise" in esolangs.describe("Suffolk").spec


def test_isolated_evaluation_requires_a_deadline() -> None:
    with pytest.raises(esolangs.ArgumentError, match="finite"):
        evaluate_generated("Suffolk", "0110", None, isolated=True)


@pytest.mark.parametrize("limit", [0, 1])
def test_value_growth_detector_accepts_eof_halt_at_step_limit(limit: int) -> None:
    machine = make_vm("Suffolk", ",")
    if limit == 0:
        machine.step()
    assert run_until_halt_or_value_growth(machine, limit) is True


@pytest.mark.medium
def test_a_non_self_halting_machine_can_already_be_finished() -> None:

    vm = make_vm("Suffolk", ",", stdin="1")
    assert not vm.self_halts
    assert run_until_halt(vm, 2)
    assert complete_vm(vm, max_steps=0) == run("Suffolk", ",", stdin="1").output


def test_the_value_growth_detector_proves_a_climb_and_declines_a_repeat() -> None:
    """Suffolk's ``>>!`` loops climb in value on a tape that never grows."""
    climbing = ">>!>>!>>!>>!>>!>>!>>!>>!>>>!>>!>>!>><!>>"
    assert run_until_halt_or_value_growth(make_vm("Suffolk", climbing)) is False
    lapping = make_vm("Suffolk", "1{z:[}] !. ;")
    assert run_until_halt_or_value_growth(lapping) is False

    # A program that cycles is the cycle detector's, and is not certified.
    sample = "!" * 66 + "<."
    assert run_until_halt_or_cycle(make_vm("Suffolk", sample)) is False
    with pytest.raises(TimeoutError):
        run_until_halt_or_value_growth(make_vm("Suffolk", sample), 20_000)
    # `<` alone rewinds to a cell it already read: a repeat, not a climb.
    with pytest.raises(TimeoutError):
        run_until_halt_or_value_growth(make_vm("Suffolk", "<"), 5_000)


def test_documented_eof_halts_with_the_answer() -> None:
    """Suffolk's programs end *by* running out of input."""

    program = esolangs.generate("Suffolk", "0110")
    stdin = esolangs.encode_inputs("Suffolk", [1, 0], truth_table="0110")
    assert (
        run(
            "Suffolk",
            program,
            stdin=stdin,
            limits=esolangs.ExecutionLimits(execution_timeout=20),
        ).output
        == "1"
    )


def test_suffolk_no_longer_disagrees_with_itself() -> None:
    """``run`` answered and the debugger raised, for the same call."""
    table = "0110"
    for bits, want in (([0, 0], "0"), ([0, 1], "1"), ([1, 0], "1"), ([1, 1], "0")):
        program, stdin = _row("Suffolk", table, bits)
        assert (
            run(
                "Suffolk",
                program,
                stdin=stdin,
                limits=esolangs.ExecutionLimits(execution_timeout=20),
            ).output
            == want
        )
        debugger = debugger_api.make_debugger("Suffolk", program, stdin=stdin)
        assert debugger.run(max_steps=_STEP_BUDGET) == "halted"
        assert debugger.output == want


@pytest.mark.slow
def test_the_readme_suffolk_flow_completes(tmp_path: Path) -> None:
    """Generate then run, the README's first pair, for all four rows."""
    generated = run_cli("generate", "Suffolk", "0110")
    path = tmp_path / "su.txt"
    path.write_text(generated.stdout.rstrip("\n"))
    got = "".join(
        run_cli(
            "run",
            "Suffolk",
            str(path),
            stdin=esolangs.encode_inputs("Suffolk", [a, b]),
        ).stdout
        for a in (0, 1)
        for b in (0, 1)
    )
    assert got == "0110"


def test_native_completion_distinguishes_eof_from_an_actual_repeat(monkeypatch):
    from esolangs.languages.suffolk.interpreter import _Machine

    machine = _Machine("<", ScriptedIO())
    state = machine.snapshot()
    machine.step()
    assert machine.snapshot() == state
    assert not machine.halted
    result = run_observed("Suffolk", "<")
    assert result.completion.kind is Completion.PERIODIC
    assert result.completion.cycle.state == state
    assert (
        result.completion.cycle.first_pass,
        result.completion.cycle.repeat_pass,
        result.completion.cycle.commands_per_pass,
    ) == (0, 1, 1)
    with guarded_worker():
        assert run_observed("Suffolk", "<", isolated=True) == result

    ended = run_observed("Suffolk", ",")
    assert ended.completion.kind is Completion.HALTED
    assert ended.completion.cycle is None
    assert (ended.input_position, ended.input_reads, ended.input_past_end) == (0, 0, 1)

    from esolangs import vm
    from esolangs.languages.suffolk import interpreter

    with guarded_worker(expected=2):
        assert esolangs.run("Suffolk", "<", isolated=True) == result
        assert esolangs.run("Suffolk", ",", isolated=True) == ended
    monkeypatch.setattr(
        vm,
        "interpreter_module",
        lambda _name, **_options: SimpleNamespace(
            prepare_machine=interpreter.prepare_machine
        ),
    )
    debug = debugger_api.make_debugger("Suffolk", "<")
    assert not debug.self_halts
    assert debug.steppable_to_answer
    assert debug.run(max_steps=3) == "max_steps"
    assert debug.observation.completion is None
    assert debug.observation.steps == 3
    eof = debugger_api.make_debugger("Suffolk", ",")
    assert eof.run(max_steps=1) == "halted"
    assert eof.observation == ended._replace(steps=1)
    monkeypatch.setattr(interpreter, "_execute", lambda *_args: POST_HALT_REPORT)
    with pytest.raises(esolangs.InterpreterLimitError, match="declared policy"):
        esolangs.run("Suffolk", "<")
