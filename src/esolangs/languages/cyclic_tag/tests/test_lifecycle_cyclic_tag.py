"""Declared completion and debugging preserve the post-halt output boundary."""

import subprocess
import sys
from dataclasses import replace
from types import SimpleNamespace

import pytest

import esolangs
from esolangs import run, vm
from esolangs.debugger import make_debugger
from esolangs.languages.cyclic_tag import interpreter
from esolangs.results import Completion, CompletionReport


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
    monkeypatch.setattr(
        interpreter,
        "_execute",
        lambda _source, _io: CompletionReport(Completion.HALTED),
    )
    with pytest.raises(esolangs.InterpreterLimitError, match="declared policy"):
        run("Cyclic tag", ",1")


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
