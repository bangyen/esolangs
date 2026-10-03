"""Cyclic tag execution and source conventions."""

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.queue_based.cyclic_tag import _Machine, run
from esolangs.tools.cyclic_tag import cyclic_tag


def test_generated_size_formula() -> None:
    for n in range(1, 4):
        for value in range(1 << (1 << n)):
            table = f"{value:0{1 << n}b}"
            template = cyclic_tag(table)
            assert len(template) == 5 * len(table) + 2 * n + 1


@pytest.mark.parametrize("code", ["", "1", "1,,0", "x,1", "1,0;1"])
def test_invalid_source(code: str) -> None:
    with pytest.raises(ValueError, match="Cyclic tag"):
        run(code, ScriptedIO())


def test_source_offsets_and_cycle_snapshot() -> None:
    machine = _Machine(" 1; 1,1", ScriptedIO())
    assert machine.ip == 1
    machine.step()
    assert machine.ip == 4
    before = machine.snapshot()
    machine.step()
    machine.step()
    assert machine.snapshot() == before
    assert not machine.halted
