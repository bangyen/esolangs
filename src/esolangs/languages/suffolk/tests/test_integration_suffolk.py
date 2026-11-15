"""Suffolk through the shared API, CLI and machinery."""

from dataclasses import replace
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
from tests.support.reference import REFERENCE
from tests.support.vm_support import (
    _STEP_BUDGET,
    _row,
    assert_proof_fault,
    assert_rejected_output_retry,
)


@pytest.mark.parametrize("debugged", [False, True])
def test_live_detectors_keep_vm_fault_evidence(*, debugged: bool) -> None:
    assert_proof_fault(
        run_until_halt_or_value_growth,
        "Suffolk",
        ",.,.",
        esolangs.ProgramError,
        "@",
        debugged=debugged,
        stdin="A\U0010ffff",
    )


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

    class SwapAfterCommand(debugger_api.Debugger):
        def __init__(self, replacement):
            super().__init__(make_vm(REFERENCE, "+."))
            self.replacement = replacement

        def step(self):
            super().step()
            self.vm = self.replacement

    for max_steps in (1, 4):
        active = make_vm("Suffolk", ",.", stdin="B")
        original_ip = active.ip
        with pytest.raises(esolangs.ArgumentError, match="machine that self-halts"):
            complete_vm(active, max_steps=max_steps)
        outer = debugger_api.Debugger(SwapAfterCommand(active))
        with pytest.raises(esolangs.ArgumentError, match="machine that self-halts"):
            complete_vm(outer, max_steps=max_steps)
        assert outer.observation.steps == 1
        assert active.ip == original_ip
        assert active.output == ""

    already_halted = debugger_api.Debugger(SwapAfterCommand(vm))
    assert complete_vm(already_halted, max_steps=1) == vm.output
    assert already_halted.observation.steps == 1


def test_the_value_growth_detector_proves_a_climb_and_declines_a_repeat() -> None:
    """Suffolk's ``>>!`` loops climb in value on a tape that never grows."""
    climbing = ">>!>>!>>!>>!>>!>>!>>!>>!>>>!>>!>>!>><!>>"
    assert run_until_halt_or_value_growth(make_vm("Suffolk", climbing)) is False
    lapping = make_vm("Suffolk", "1{z:[}] !. ;")
    assert run_until_halt_or_value_growth(lapping) is False

    short = debugger_api.make_debugger("Suffolk", "!")
    with pytest.raises(TimeoutError, match="after 1 steps"):
        run_until_halt_or_value_growth(short, limit=1)
    assert short.observation.steps == 1

    exact = debugger_api.make_debugger("Suffolk", "!")
    assert run_until_halt_or_value_growth(exact, limit=2) is False
    assert exact.observation.steps == 2

    # A program that cycles is the cycle detector's, and is not certified.
    sample = "!" * 66 + "<."
    assert run_until_halt_or_cycle(make_vm("Suffolk", sample)) is False
    with pytest.raises(TimeoutError):
        run_until_halt_or_value_growth(make_vm("Suffolk", sample), 20_000)
    # `<` alone rewinds to a cell it already read: a repeat, not a climb.
    with pytest.raises(TimeoutError):
        run_until_halt_or_value_growth(make_vm("Suffolk", "<"), 5_000)


def test_documented_eof_halts_with_the_answer(monkeypatch) -> None:
    """Suffolk's programs end *by* running out of input."""
    assert_rejected_output_retry(
        "Suffolk",
        ",.",
        "A",
        "A",
        prefix=1,
        stdin="B",
        unchanged_if_unwritten=True,
        following_writes=(),
        monkeypatch=monkeypatch,
    )

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
        assert (
            debugger.run(limits=esolangs.ExecutionLimits(max_steps=_STEP_BUDGET))
            == "halted"
        )
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

    api = esolangs.Language("Suffolk")
    record = api.catalog.languages[api.name]

    def prepare(_source, _options):
        def initialize(io):
            io.print_char(chr(io.input_char()))
            return custom

        return initialize

    monkeypatch.setattr(interpreter, "custom_prepare", prepare, raising=False)
    scoped = esolangs.Catalog(
        [
            replace(
                record,
                runtime=replace(record.runtime, machine_preparation="custom_prepare"),
            )
        ]
    ).bind(api.name)
    prepared = scoped.prepare("<")
    limits = esolangs.ExecutionLimits(max_steps=2)
    observed = esolangs.ExecutionResult("A", 1, 1, 0, steps=0)
    for fields, diagnostic in (
        ({}, "callable snapshot"),
        ({"snapshot": 0}, "callable snapshot"),
        ({"snapshot": lambda: [0]}, "hashable state"),
        ({"snapshot": lambda: ([0],)}, "hashable state"),
        ({"halted": "active", "snapshot": lambda: 0}, "halted must be a bool"),
    ):
        custom = SimpleNamespace(step=lambda: None, **({"halted": False} | fields))
        for outcome in (
            scoped.execute("<", stdin="A", limits=limits),
            prepared.execute(stdin="A", limits=limits),
        ):
            assert isinstance(outcome.error, esolangs.InterpreterLimitError)
            assert diagnostic in str(outcome.error)
            assert outcome.observation == outcome.error.observation == observed
        custom.halted = True
        assert prepared.run(stdin="A", limits=limits) == replace(
            observed, completion=ended.completion
        )

    class Alternating:
        halted = False
        index = 0

        def step(self):
            self.index += 1

        @property
        def snapshot(self):
            index = self.index
            return lambda: (index % 2,)

    custom = Alternating()
    stepped = prepared.run(stdin="A", limits=limits)
    assert stepped.output == "A"
    assert stepped.steps == stepped.completion.cycle.repeat_pass == 2

    original = TypeError("snapshot comparison refused")

    class RefusedComparison:
        def __hash__(self):
            return 0

        def __eq__(self, _other):
            raise original

    custom = SimpleNamespace(
        step=lambda: None, halted=False, snapshot=RefusedComparison
    )
    with pytest.raises(TypeError, match="snapshot comparison") as caught:
        prepared.execute(stdin="A", limits=limits)
    assert caught.value is original
    _check_snapshot_key_faults(scoped, interpreter, monkeypatch)

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
    assert debug.run(limits=esolangs.ExecutionLimits(max_steps=3)) == "max_steps"
    assert debug.observation.completion is None
    assert debug.observation.steps == 3
    eof = debugger_api.make_debugger("Suffolk", ",")
    assert eof.run(limits=esolangs.ExecutionLimits(max_steps=1)) == "halted"
    assert eof.observation == replace(ended, steps=1)
    monkeypatch.setattr(interpreter, "_execute", lambda *_args: POST_HALT_REPORT)
    with pytest.raises(esolangs.InterpreterLimitError, match="declared policy"):
        esolangs.run("Suffolk", "<")


def _check_snapshot_key_faults(api, interpreter, monkeypatch):
    fault = None
    fail_hash = None
    hashes = 0

    class Key:
        def __hash__(self):
            nonlocal hashes
            hashes += 1
            if fault is not None and hashes == fail_hash:
                raise fault
            return 29

        def __eq__(self, other):
            if fault is not None and fail_hash is None:
                raise fault
            return isinstance(other, Key)

    class Machine:
        halted = dumps_on_the_post_halt_step = False
        steppable_to_answer = True
        snapshot = staticmethod(Key)

        def __init__(self, io):
            self.io = io
            io.print_char(chr(io.input_char()))

        def step(self):
            self.io.print_str("!")

        @property
        def output(self):
            return self.io.getvalue()

    class CallerSnapshot(debugger_api.Debugger):
        def snapshot(self):
            return Key()

    with monkeypatch.context() as hooks:
        hooks.setattr(interpreter, "custom_prepare", lambda *_args: Machine)
        prepared = api.prepare("<")
        limits = esolangs.ExecutionLimits(max_steps=2)

        def make_debugger():
            return prepared.make_debugger(stdin="A")

        def prove():
            return run_until_halt_or_cycle(make_debugger(), limit=2)

        calls = (
            (lambda: prepared.make_vm(stdin="A").snapshot(), 1, None, True),
            (lambda: make_debugger().snapshot(), 1, None, True),
            (lambda: debugger_api.Debugger(make_debugger()).snapshot(), 2, None, True),
            (prove, 1, 0, True),
            (prove, None, 1, True),
            (lambda: prepared.run(stdin="A", limits=limits), 1, 0, True),
            (lambda: prepared.run(stdin="A", limits=limits), None, 1, True),
            (
                lambda: debugger_api.Debugger(
                    debugger_api.Debugger(Machine(ScriptedIO("A")))
                ).snapshot(),
                2,
                None,
                False,
            ),
            (
                lambda: run_until_halt_or_cycle(
                    CallerSnapshot(prepared.make_vm(stdin="A")), limit=2
                ),
                1,
                0,
                False,
            ),
        )
        for invoke, fail_hash, steps, owned in calls:
            fault = esolangs.HaltError("snapshot key refused")
            hashes = 0
            with pytest.raises(
                esolangs.HaltError, match="snapshot key refused"
            ) as caught:
                invoke()
            assert caught.value is fault
            if fail_hash is not None:
                assert hashes == fail_hash
            if owned:
                output = "A!" if steps == 1 else "A"
                assert fault.observation == esolangs.ExecutionResult(
                    output, 1, 1, 0, steps=steps
                )
                assert fault.partial_output == output
            else:
                assert fault.observation is None
                assert fault.partial_output == ""

        foreign = esolangs.ExecutionResult("other", 2, 1, 0, steps=7)
        for observation in (None, foreign):
            fault = esolangs.HaltError("foreign key fault")
            fault.observation = observation
            fault.partial_output = "other"
            fail_hash = None
            with pytest.raises(esolangs.HaltError, match="foreign key fault") as caught:
                prove()
            assert caught.value is fault
            assert fault.observation is observation
            assert fault.partial_output == "other"

        fault = None
        assert prove() is False
        result = prepared.run(stdin="A", limits=limits)
        assert result.output == "A!"
        assert result.steps == result.completion.cycle.repeat_pass == 1


@pytest.mark.medium
@pytest.mark.parametrize("worker", [False, True])
def test_bounded_runs_keep_the_native_first_repeat_boundary(worker):
    api = esolangs.Language("Suffolk")
    artifact = api.from_source("!" * 49 + "<.<!")
    steps = len(artifact.source)
    native = api.run(artifact)
    assert native.output == "0"
    assert native.completion.cycle.repeat_pass == steps
    expected = replace(native, steps=steps)
    prepared = api.prepare(artifact)
    limits = esolangs.ExecutionLimits(
        max_steps=steps, total_timeout=5 if worker else None
    )
    assert api.run(artifact, limits=limits) == expected
    assert prepared.run(limits=limits) == expected
    assert api.evaluate(artifact, [0], limits=limits) == esolangs.BooleanEvaluation(
        "0", expected
    )

    earlier = prepared.execute(limits=replace(limits, max_steps=steps - 1))
    assert earlier.bound == "max_steps"
    assert earlier.observation == replace(expected, completion=None, steps=steps - 1)
    eof = api.run(",.", stdin="A", limits=replace(limits, max_steps=3))
    assert eof == replace(api.run(",.", stdin="A"), steps=3)
    assert eof.output == "@"
    assert eof.completion.kind is Completion.HALTED

    debugger = prepared.make_debugger()
    assert (
        debugger.run(limits=esolangs.ExecutionLimits(max_steps=2 * steps))
        == "max_steps"
    )
    assert debugger.output == "00"
    assert debugger.observation.completion is None
