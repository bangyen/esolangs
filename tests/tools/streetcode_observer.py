# ruff: noqa: SLF001 - execute the machine and inspect complete trace states.
# ruff: noqa: SLF001 - execute the machine and inspect complete trace states.
# ruff: noqa: SLF001 - execute the machine and inspect complete trace states.
# ruff: noqa: SLF001 - execute the machine and inspect complete trace states.
# ruff: noqa: SLF001 - execute the machine and inspect complete trace states.
# ruff: noqa: SLF001 - execute generated programs and inspect route invariants.
"""Check emitted truth-table rows, character reads, and valid driving."""

from esolangs.interpreters.grid_based.streetcode import _Machine
from esolangs.interpreters.io import ScriptedIO


def check(source, table, row):
    n = len(table).bit_length() - 1
    io = ScriptedIO(format(row, f"0{n}b"))
    machine = _Machine._for_run(source.splitlines(), io)
    for generation in range(100000):
        if machine.halted:
            assert io.getvalue() == table[row], (table, row, io.getvalue())
            assert io.reads == n
            assert io.position() == n
            return generation
        old = machine.row, machine.col
        machine.step()
        if not machine.halted:
            assert abs(machine.row - old[0]) + abs(machine.col - old[1]) == 1
        assert machine.grid.open_at(machine.row, machine.col)
    raise AssertionError("generated program bound exceeded")
