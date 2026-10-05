"""Nope.'s single output transition must change the snapshot."""

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.nope import _Machine
from tests.interpreters.views import view as vm_view


def test_empty_source_has_one_output_transition() -> None:
    io = ScriptedIO()
    machine = _Machine("", io)
    before = machine.snapshot()
    assert not machine.halted
    machine.step()
    assert machine.halted
    assert machine.snapshot() != before
    assert vm_view(machine, "ip") == 1
    assert not hasattr(machine, "memory")
    assert not hasattr(machine, "stack")
    after = machine.snapshot()
    machine.step()
    assert machine.snapshot() == after
    assert io.getvalue() == "Nope."
