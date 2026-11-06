"""Nope. ignores arbitrary source and all input, including empty source."""

import pytest

from esolangs.languages.nope.interpreter import _Machine, run
from esolangs.runtime.io import ScriptedIO
from scripts.benchmark import WrittenState
from tests.support.workspace_oracle import WorkspaceOracle


@pytest.mark.parametrize("code", ["", "Nope.", "[,☃\x00"])
@pytest.mark.parametrize("stdin", ["", "☃\n0 1"])
def test_constant_output(code: str, stdin: str) -> None:
    io = ScriptedIO(stdin)
    run(code, io)
    assert io.getvalue() == "Nope."
    assert io.position() == 0


def test_empty_source_has_one_output_transition() -> None:
    from esolangs.languages.nope.tests.oracle_checks import check_raw_nope

    check_raw_nope()
    io = ScriptedIO()
    machine = _Machine("", io)
    before = machine.snapshot()
    measured = WrittenState(machine.workspace_snapshot())
    oracle = WorkspaceOracle(machine.workspace_snapshot())
    assert not machine.halted
    machine.step()
    assert machine.halted
    assert machine.snapshot() != before
    captured = machine.workspace_snapshot()
    assert captured.parts == (machine.state, io.progress()) == (True, 0)
    measured.sample(captured)
    oracle.sample(captured)
    assert measured.bits == oracle.bits == 1
    assert machine.ip == 1
    assert not hasattr(machine, "memory")
    assert not hasattr(machine, "stack")
    after = machine.snapshot()
    machine.step()
    assert machine.snapshot() == after
    assert io.getvalue() == "Nope."
