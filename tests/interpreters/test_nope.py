"""Nope. ignores arbitrary source and all input, including empty source."""

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.nope import _Machine, run


@pytest.mark.parametrize("code", ["", "Nope.", "114514", "[,☃\x00", "0" * 10000])
@pytest.mark.parametrize("stdin", ["", "114514", "☃\n0 1"])
def test_constant_output(code: str, stdin: str) -> None:
    io = ScriptedIO(stdin)
    run(code, io)
    assert io.getvalue() == "Nope."
    assert io.position() == 0


def test_empty_source_has_one_output_transition() -> None:
    io = ScriptedIO()
    machine = _Machine("", io)
    before = machine.snapshot()
    assert not machine.halted
    machine.step()
    assert machine.halted
    assert machine.snapshot() != before
    assert machine.ip == 1
    assert not hasattr(machine, "memory")
    assert not hasattr(machine, "stack")
    after = machine.snapshot()
    machine.step()
    assert machine.snapshot() == after
    assert io.getvalue() == "Nope."
