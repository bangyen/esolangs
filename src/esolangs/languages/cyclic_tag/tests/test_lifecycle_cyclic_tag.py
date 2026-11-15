"""Declared completion and debugging preserve the post-halt output boundary."""

import subprocess
import sys
from dataclasses import replace
from types import SimpleNamespace

import pytest

import esolangs
from esolangs import run, vm
from esolangs.debugger import Debugger, make_debugger
from esolangs.languages.cyclic_tag import interpreter
from esolangs.results import Completion, CompletionReport
from tests.support.reference import REFERENCE
from tests.support.vm_support import assert_vm_finalization_is_shared


@pytest.mark.parametrize("finalize", ["step", "complete_vm"])
def test_debuggers_share_the_finalized_output(finalize) -> None:
    assert_vm_finalization_is_shared("Cyclic tag", ",10", 2, "0", finalize)
    if finalize == "complete_vm":
        _check_complete_vm_receiver_replacements()
        _check_run_step_override_dump()


def _check_run_step_override_dump() -> None:
    class Override(Debugger):
        def __init__(self, target, *, direct: bool) -> None:
            super().__init__(target)
            self.direct = direct
            self.calls = 0

        def step(self) -> None:
            self.calls += 1
            if self.direct:
                self.vm.step()
            else:
                super().step()

    api = esolangs.Language("Cyclic tag")
    limits = esolangs.ExecutionLimits(max_steps=0)
    for direct in (False, True):
        target = api.make_vm(",1")
        target.step()
        live = Override(target, direct=direct)
        assert live.halted
        assert live.output == ""
        for _ in range(2):
            assert live.run(limits=limits) == "halted"
            assert live.output == "1"
            assert live.observation.completion.kind is Completion.POST_HALT
            assert live.observation.steps == 0
            assert live.calls == 1


def _check_complete_vm_receiver_replacements():
    class SwapAfterDump(Debugger):
        def __init__(self, original, replacement):
            super().__init__(original)
            self.original = original
            self.replacement = replacement

        def step(self):
            dumping = self.vm is self.original and self.halted
            super().step()
            if dumping:
                self.vm = self.replacement

    def wrap(original, replacement, *, nested):
        switched = SwapAfterDump(original, replacement)
        return Debugger(switched) if nested else switched

    api = esolangs.Language("Cyclic tag")
    for nested in (False, True):
        for prehalted, limit, next_steps in (
            (True, 0, 0),
            (False, 2, 1),
            (False, 3, 2),
            (True, None, 2),
        ):
            original = api.make_vm(",1")
            if prehalted:
                original.step()
            next_vm = vm.make_vm(REFERENCE, "+.")
            live = wrap(original, next_vm, nested=nested)
            if next_steps == 2:
                assert vm.complete_vm(live, max_steps=limit) == "\x01"
                assert live.observation.completion.kind is Completion.HALTED
            else:
                with pytest.raises(
                    esolangs.ExecutionCapError, match="max_steps"
                ) as caught:
                    vm.complete_vm(live, max_steps=limit)
                assert caught.value.bound == "max_steps"
                assert caught.value.partial_output == ""
                assert caught.value.observation == live.observation
                assert live.observation.steps == limit
                assert not live.halted
            assert original.output == "1"
            assert next_vm.ip == next_steps
            assert live.observation.steps == int(not prehalted) + next_steps

        original = api.make_vm(",1")
        next_vm = api.make_vm(",0")
        next_vm.step()
        live = wrap(original, next_vm, nested=nested)
        assert vm.complete_vm(live, max_steps=1) == "0"
        assert original.output == "1"
        assert live.observation.completion.kind is Completion.POST_HALT
        assert live.observation.steps == 1

        original = api.make_vm(",1")
        next_vm = vm.make_vm(REFERENCE, ",.,", stdin="A")
        live = wrap(original, next_vm, nested=nested)
        with pytest.raises(esolangs.InputExhaustedError) as caught:
            vm.complete_vm(live, max_steps=4)
        assert original.output == "1"
        assert caught.value.partial_output == "A"
        assert caught.value.observation == esolangs.ExecutionResult(
            "A", 1, 1, 1, steps=3
        )


@pytest.mark.medium
def test_declared_metadata_and_completion_routes(monkeypatch):
    subprocess.run(
        [
            sys.executable,
            "-c",
            """
import sys
from esolangs.vm import machine_traits
module = 'esolangs.languages.cyclic_tag.interpreter'
assert module not in sys.modules
assert machine_traits('Cyclic tag')['dumps_on_the_post_halt_step']
assert module not in sys.modules
from esolangs.vm import make_vm
make_vm('Cyclic tag', ',1')
assert module in sys.modules, 'loading control did not fire'
""",
        ],
        check=True,
        timeout=10,
    )
    for source, expected, steps in ((",", "", 0), (",1", "1", 1), (";,10", "0", 2)):
        native = run("Cyclic tag", source, stdin="unused")
        isolated = run("Cyclic tag", source, stdin="unused", isolated=True)
        assert native == isolated
        assert native.output == expected
        assert native.completion == CompletionReport(Completion.POST_HALT)
        assert native.input_position == native.input_reads == native.input_past_end == 0
        debug = make_debugger("Cyclic tag", source, stdin="unused")
        for _ in range(steps):
            debug.step()
        assert debug.halted
        assert debug.output == ""
        assert debug.observation.completion is None
        assert debug.observation.steps == steps
        debug.step()
        finalized = debug.observation
        snapshot = debug.snapshot()
        assert finalized == replace(native, steps=steps)
        debug.step()
        assert debug.observation == finalized
        assert debug.snapshot() == snapshot
    _check_callback_replacement_boundaries(monkeypatch)
    _check_callback_halt_boundaries(monkeypatch)
    monkeypatch.setattr(
        interpreter,
        "_execute",
        lambda _source, _io: CompletionReport(Completion.HALTED),
    )
    with pytest.raises(esolangs.InterpreterLimitError, match="declared policy"):
        run("Cyclic tag", ",1")


def _check_callback_replacement_boundaries(monkeypatch):
    for after_dump, active in ((False, True), (True, True), (True, False)):
        receiver = make_debugger("Cyclic tag", ",1")
        debug = Debugger(receiver)
        if not after_dump:
            receiver.step()
        replacement = vm.make_vm("Cyclic tag", ",0")
        if not active:
            replacement.step()
        checked = []

        def swap(
            machine,
            *,
            after=after_dump,
            target=replacement,
            seen=checked,
            receiver=receiver,
        ):
            seen.append((machine.halted, machine.output))
            if machine.halted and bool(machine.output) == after:
                receiver.vm = target
            return False

        debug.break_when(swap)
        limits = esolangs.ExecutionLimits(max_steps=int(after_dump))
        expected_halt = "max_steps" if active else "halted"
        assert debug.run(limits=limits) == expected_halt
        assert debug.observation.steps == int(after_dump)
        if active:
            assert not debug.halted
            assert debug.output == ""
            assert checked[-1] == (False, "")
            assert debug.run(limits=esolangs.ExecutionLimits(max_steps=1)) == "halted"
        assert debug.output == "0"
        assert debug.observation.completion.kind is Completion.POST_HALT
        assert debug.observation.steps == int(after_dump) + int(active)

    now = [0.0]
    monkeypatch.setattr("esolangs.runtime._controller.monotonic", lambda: now[0])
    debug = make_debugger("Cyclic tag", ",")

    def swap_after_deadline(_machine):
        debug.clear_breakpoints()
        debug.vm = vm.make_vm("Cyclic tag", ",1")
        now[0] = 2.0
        return False

    debug.break_when(swap_after_deadline)
    deadline = esolangs.ExecutionLimits(execution_timeout=1, max_steps=1)
    assert debug.run(limits=deadline) == "execution_timeout"
    assert not debug.halted
    assert debug.output == ""
    assert debug.observation.steps == 0


def test_dump_breakpoint_hits_do_not_survive_rewrapping() -> None:
    owner = esolangs.Language("Cyclic tag").prepare(",1").make_vm()
    owner.step()
    assert owner.halted
    assert not owner.output
    old, new = Debugger(owner), Debugger(owner)
    middle = Debugger(old)
    outer = Debugger(middle)

    def replace_without_hit(vm):
        if vm.output:
            vm.vm = new
        return False

    outer.break_when(lambda vm: bool(vm.output) and vm.vm is old)
    outer.break_when(replace_without_hit)
    assert outer.run(limits=esolangs.ExecutionLimits(max_steps=0)) == "halted"
    assert middle.vm is new
    assert outer.observation.steps == 0
    assert outer.output == "1"


def _check_callback_halt_boundaries(monkeypatch):
    limits = esolangs.ExecutionLimits(max_steps=1)
    machine = vm.make_vm("Cyclic tag", ",1")
    assert vm.run_until_halt(machine, limit=1)
    assert machine.output == ""
    assert vm.complete_vm(machine, max_steps=0) == "1"

    class StopAfterStep:
        def __init__(self, machine, stop):
            self.machine = machine
            self.stop = stop

        def __bool__(self):
            self.machine.step()
            return self.stop

    for requested in (False, True):
        machine = vm.make_vm("Cyclic tag", ",1")
        result = StopAfterStep(machine, requested)
        assert vm.run_until_halt(machine, limit=1, stop=lambda result=result: result)
        assert machine.halted
        assert machine.output == ""
        assert vm.complete_vm(machine, max_steps=0) == "1"

        debug = make_debugger("Cyclic tag", ",1")
        checks = []

        def breakpoint_before_dump(machine, first=requested, checks=checks):
            checks.append(machine.halted)
            if not machine.halted:
                machine.step()
                return first
            return machine.output == ""

        debug.break_when(breakpoint_before_dump)
        assert debug.run(limits=limits) == "breakpoint"
        assert checks == ([False] if requested else [False, True])
        assert debug.halted
        assert debug.output == ""
        assert debug.observation.steps == 0
        debug.clear_breakpoints()
        assert debug.run(limits=esolangs.ExecutionLimits(max_steps=0)) == "halted"
        assert debug.output == "1"
        assert debug.observation.steps == 0

    now = [0.0]
    monkeypatch.setattr("esolangs.runtime._controller.monotonic", lambda: now[0])
    debug = make_debugger("Cyclic tag", ",1")

    def halt_after_deadline(machine):
        if not machine.halted:
            machine.step()
            now[0] = 2.0
        return False

    debug.break_when(halt_after_deadline)
    deadline = esolangs.ExecutionLimits(execution_timeout=1, max_steps=1)
    assert debug.run(limits=deadline) == "execution_timeout"
    assert debug.halted
    assert debug.output == ""
    assert debug.observation.steps == 0


def test_declared_debug_surface_ignores_incidental_machine_attributes(monkeypatch):
    monkeypatch.setattr(interpreter._Machine, "completion", Completion.HALTED)
    monkeypatch.setattr(interpreter._Machine, "ip_shape", "opaque", raising=False)
    monkeypatch.setattr(interpreter._Machine, "ptr", 17, raising=False)
    monkeypatch.setattr(interpreter._Machine, "stack", [999], raising=False)
    monkeypatch.setattr(
        interpreter._Machine,
        "surprise",
        property(lambda _self: "incidental"),
        raising=False,
    )
    monkeypatch.setattr(
        vm,
        "interpreter_module",
        lambda _name, **_options: SimpleNamespace(
            prepare_machine=interpreter.prepare_machine
        ),
    )
    machine = vm.make_vm("Cyclic tag", ",10")
    assert machine.dumps_on_the_post_halt_step
    assert machine.self_halts
    assert machine.steppable_to_answer
    assert not machine.eof_is_a_value
    assert machine.ip_shape == "offset"
    assert machine.ip == 0
    assert machine.ptr is None
    assert machine.stack == []
    cells = machine.memory
    cells.clear()
    assert machine.memory == [1, 0]
    assert machine.views == (("answer", "None"), ("head", "0"), ("live", "'10'"))
    assert vm.complete_vm(machine, max_steps=2) == "0"
    assert vm.complete_vm(machine, max_steps=0) == "0"
    assert run("Cyclic tag", ",10").output == "0"
