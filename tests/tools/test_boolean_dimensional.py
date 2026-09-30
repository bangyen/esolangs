"""Bare dimension operands preserve painted small-table leaves."""

import pytest

from esolangs import generate
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.dimensional import _Machine
from esolangs.tools.dimensional import dimensional


@pytest.mark.medium
def test_bare_axis_leaves_execute_all_small_tables() -> None:
    for n in range(1, 4):
        for value in range(1 << (1 << n)):
            table = format(value, f"0{1 << n}b")
            program = generate("Dimensional", table, 1)
            assert max(map(len, program.splitlines())) == (1 if n <= 2 else 2)
            for row, expected in enumerate(table):
                io = ScriptedIO("\n".join(format(row, f"0{n}b")))
                machine = _Machine(program, io)
                for _ in range(5000):
                    if machine.halted:
                        break
                    machine.step()
                assert machine.halted
                assert (io.getvalue(), io.reads) == (expected, n)
    assert len(dimensional("0110", 1)) == 429


@pytest.mark.parametrize("width", [None, 2, 3, 8, 80])
def test_other_widths_preserve_the_established_build(width: int | None) -> None:
    from esolangs.tools.wrap import wrap_program

    for table in ("00", "11", "0110", "0001", "10010110"):
        assert dimensional(table, width) == wrap_program(
            dimensional(table), "dimensional", width
        )


@pytest.mark.parametrize("n", [4, 6])
def test_larger_tables_keep_the_established_index(n: int) -> None:
    table = "".join(str((row * 73 + row // 3) & 1) for row in range(1 << n))
    program = generate("Dimensional", table, 1)
    for row in (0, 1, len(table) // 2, len(table) - 1):
        io = ScriptedIO("\n".join(format(row, f"0{n}b")))
        machine = _Machine(program, io)
        for _ in range(50_000):
            if machine.halted:
                break
            machine.step()
        assert machine.halted
        assert (io.getvalue(), io.reads) == (table[row], n)
