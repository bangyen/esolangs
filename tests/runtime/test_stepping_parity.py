"""The step path and :func:`esolangs.run` must agree, or say why they cannot."""

from __future__ import annotations

import pathlib
import sys
from dataclasses import replace
from importlib.resources import files

import pytest

import esolangs
import esolangs.debugger as debugger_api
from esolangs.registry import LANGUAGES
from esolangs.runtime._lifecycle import Completion
from esolangs.vm import (
    _capture_result,
    machine_traits,
    run_until_halt,
)
from tests.support.pick import first
from tests.support.reference import REFERENCE
from tests.support.vm_support import _STEP_BUDGET, _row

#: Enough for every generated boolean program in the suite to finish; the
#: slowest needs a few hundred thousand.


def _drive_steps(vm: debugger_api.VM) -> int:
    """Count active commands; the completion dump is outside the count."""
    steps = 0

    def before_step():
        nonlocal steps
        steps += 1
        return False

    assert run_until_halt(vm, _STEP_BUDGET, stop=before_step), (
        "stepping exhausted its command budget"
    )
    if vm.dumps_on_the_post_halt_step:
        vm.step()
    return steps


def _drive(vm: debugger_api.VM) -> str:
    """Step to a finalized answer, refusing exhausted budgets."""
    _drive_steps(vm)
    return vm.output


def _check_row(name: str, artifact: esolangs.Artifact, table: str, row: int) -> None:
    inputs = len(table).bit_length() - 1
    bits = [int(bit) for bit in f"{row:0{inputs}b}"]
    if LANGUAGES[name].parameterized:
        program = esolangs.instantiate(name, artifact, bits)
        stdin = ""
    else:
        program = artifact
        stdin = esolangs.encode_inputs(name, bits, truth_table=table)
    runtime = LANGUAGES[name].runtime
    seed = runtime.reproducible_seed if runtime.random else None
    want = esolangs.run(
        name,
        program,
        stdin=stdin,
        seed=seed,
        limits=esolangs.ExecutionLimits(max_steps=_STEP_BUDGET),
    )
    vm = debugger_api.make_vm(name, program, stdin=stdin, seed=seed)
    steps = _drive_steps(vm)
    got = _capture_result(vm)
    # A step-bounded run reports its count; the stepped capture does not, and
    # the debugger check below pins the count against the stepper's.
    assert got == replace(want, steps=None), (
        "execution observations",
        name,
        table,
        row,
        got,
        want,
    )
    debugger = debugger_api.make_debugger(name, program, stdin=stdin, seed=seed)
    assert debugger.run(limits=esolangs.ExecutionLimits(max_steps=steps)) == "halted", (
        name,
        table,
        row,
        steps,
    )
    assert debugger.observation == replace(want, steps=steps), (
        "source steps",
        name,
        table,
        row,
        debugger.observation,
        steps,
    )
    assert esolangs.read_answer(name, got.output) == table[row], (name, table, row)


class TestTheTraitsAreReportedBeforeAMachineExists:
    """A caller deciding *how* to drive should not have to build one first."""

    @pytest.mark.parametrize(
        "key", ["self_halts", "dumps_on_the_post_halt_step", "steppable_to_answer"]
    )
    def test_describe_carries_each_trait(self, key: str) -> None:
        """They were VM properties only, so seventeen needed bits to read one."""
        assert key in esolangs.LanguageInfo.__dataclass_fields__

    def test_describe_agrees_with_the_machine(self) -> None:
        """The class attribute and the live wrapper must not drift apart."""
        names = [first(answer_mode=mode) for mode in ("output", "dump", "termination")]
        for name in [*names, first(self_halts=False)]:
            facts = esolangs.describe(name)
            for key, value in machine_traits(name).items():
                assert getattr(facts, key) == value, (name, key)


def _steppable_languages() -> list[str]:
    """Return the languages this file's parity sweeps compare, by the same rule."""
    return [
        name
        for name in esolangs.list_languages()
        if esolangs.describe(name).boolean_generator
        and esolangs.describe(name).steppable_to_answer
        and esolangs.describe(name).answer_mode != "termination"
    ]


#: The floor the derived count has to clear.  Without it a filter that
#: admitted nothing would make ``checked == 0 == expected`` and pass.
_MIN_STEPPABLE = 50


class TestSteppingReachesTheSameAnswer:
    """The sweep that would have caught all seven at once."""

    @pytest.mark.slow
    def test_every_steppable_language_agrees_with_run(self, monkeypatch) -> None:
        """58/65 was six refused dump steps and one raise, not seven wrong bits."""
        # Counted, because a filter that quietly excluded everything would
        # leave this passing on nothing at all.
        checked = 0
        languages = _steppable_languages()
        assert len(languages) >= _MIN_STEPPABLE, languages
        assert set(languages) == {
            name
            for name, language in LANGUAGES.items()
            if language.backend is not None
            and language.runtime.capabilities.completion is not Completion.PERIODIC
            and language.contract.answer_mode != "termination"
        }
        tables = [f"{mask:0{1 << n}b}" for n in (1, 2) for mask in range(1 << (1 << n))]
        for name in languages:
            for table in tables:
                artifact = esolangs.generate(name, table)
                for row in range(len(table)):
                    _check_row(name, artifact, table, row)
                    checked += 1
        # Count every admitted row; an unfinished drive cannot count as success.
        assert checked == len(languages) * sum(map(len, tables)), checked
        capture = _capture_result

        def corrupt_reads(vm):
            result = capture(vm)
            return replace(result, input_reads=(result.input_reads or 0) + 1)

        with monkeypatch.context() as control:
            control.setattr(sys.modules[__name__], "_capture_result", corrupt_reads)
            with pytest.raises(AssertionError, match="execution observations"):
                _check_row(REFERENCE, esolangs.generate(REFERENCE, "01"), "01", 1)
        result_property = debugger_api.Debugger.observation

        def corrupt_steps(debugger):
            result = result_property.__get__(debugger)
            return replace(result, steps=result.steps + 1)

        with monkeypatch.context() as control:
            control.setattr(
                debugger_api.Debugger, "observation", property(corrupt_steps)
            )
            with pytest.raises(AssertionError, match="source steps"):
                _check_row(REFERENCE, esolangs.generate(REFERENCE, "01"), "01", 1)
        with monkeypatch.context() as control:
            control.setattr(sys.modules[__name__], "_STEP_BUDGET", 1)
            with pytest.raises(AssertionError, match="command budget"):
                _drive(debugger_api.make_vm(REFERENCE, "+[]"))


class TestStepPastHaltIsSafeEverywhere:
    """The claim that made the unconditional delegation defensible."""

    @pytest.mark.slow
    def test_no_language_faults_when_stepped_past_its_halt(self) -> None:
        """``Debugger.step`` now delegates always, so this must hold for all."""
        broke = []
        checked = eligible = 0
        for name in esolangs.list_languages():
            facts = esolangs.describe(name)
            if not facts.boolean_generator:
                continue
            if not facts.steppable_to_answer or not facts.self_halts:
                continue
            if facts.answer_mode == "termination":
                continue
            eligible += 1
            program, stdin = _row(name, "0110", [0, 1])
            vm = debugger_api.make_vm(name, program, stdin=stdin)
            _drive(vm)
            settled = _capture_result(vm)
            try:
                for _ in range(3):
                    vm.step()
            except Exception as exc:
                broke.append(f"{name}: {type(exc).__name__}: {exc}")
                continue
            if _capture_result(vm) != settled:
                broke.append(f"{name}: execution observations changed past the halt")
            checked += 1
        assert not broke, "\n".join(broke)
        assert checked == eligible > 0


class TestTheConstructorsTakeWhatRunTakes:
    """``check_program`` was called and its *return value* thrown away."""

    @pytest.mark.parametrize(
        "build", [debugger_api.make_vm, debugger_api.make_debugger]
    )
    def test_a_path_is_read_rather_than_handed_to_the_interpreter(
        self, build: object
    ) -> None:
        """It validated the file's contents, then passed the Path itself on."""
        example = pathlib.Path(
            str(files("esolangs") / esolangs.describe(REFERENCE).examples[0])
        )
        machine = build(REFERENCE, example, stdin="1\n0\n")
        assert machine.halted is False

    def test_the_path_and_the_source_build_the_same_machine(self) -> None:
        """Reading it here must match what a caller reading it gets."""
        example = pathlib.Path(
            str(files("esolangs") / esolangs.describe(REFERENCE).examples[0])
        )
        source = example.read_text().rstrip("\n")
        from_path = _drive(debugger_api.make_vm(REFERENCE, example, stdin="1\n0\n"))
        from_text = _drive(debugger_api.make_vm(REFERENCE, source, stdin="1\n0\n"))
        assert from_path == from_text
