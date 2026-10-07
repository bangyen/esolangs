"""Dimensional generator tests."""

import pytest

from esolangs import generate
from esolangs import tools as boolean
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.dimensional import _Machine
from esolangs.tools.dimensional import dimensional
from tests.tools.boolean_runners import (
    run_dimensional,
)
from tests.witness_tables import witnesses


@pytest.mark.medium
def test_bare_axis_leaves_execute_all_small_tables() -> None:
    for n in range(1, 4):
        for table in witnesses(n):
            program = generate("Dimensional", table, width=1)
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
    program = generate("Dimensional", table, width=1)
    for row in (0, 1, len(table) // 2, len(table) - 1):
        io = ScriptedIO("\n".join(format(row, f"0{n}b")))
        machine = _Machine(program, io)
        for _ in range(50_000):
            if machine.halted:
                break
            machine.step()
        assert machine.halted
        assert (io.getvalue(), io.reads) == (table[row], n)


class TestDimensional:
    def test_a_bare_move_is_the_addressing(self) -> None:
        """A bare >/< takes its dimension from the cell, which is the point."""
        program = boolean.dimensional("0110")
        bare = [
            i
            for i, c in enumerate(program)
            if c in "><" and not program[i + 1 :][:1].isdigit()
        ]
        assert len(bare) == 3, program

    def test_the_table_costs_two_characters_an_entry(self) -> None:
        """One painted cell an entry, whichever bit it is."""
        full = "1" * 64
        one = "0" * 63 + "1"
        assert len(boolean.dimensional(full)) == len(boolean.dimensional(one))
        parity = "".join("1" if bin(i).count("1") % 2 else "0" for i in range(64))
        assert len(boolean.dimensional(parity)) < 10_000

    def test_a_sparse_table_pays_only_for_its_prefix(self) -> None:
        """An unvisited cell already reads 0, so painting stops at the last one."""
        early = "1" + "0" * 15
        late = "0" * 15 + "1"
        assert len(boolean.dimensional(early)) < len(boolean.dimensional(late))

    def test_scales_beyond_the_old_reference_cap(self) -> None:
        """The v3.0 interpreter's unbounded cells lift the old n <= 12 cap."""
        program = boolean.dimensional("0" * 4095 + "1")
        got = run_dimensional(program, ["1"] * 12)
        assert got == "1"


class TestGeneratorEdgePaths:
    def test_dimensional_validation(self) -> None:
        """The Dimensional generator rejects bad truth tables."""
        with pytest.raises(ValueError, match="power-of-two"):
            boolean.dimensional("011")
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.dimensional("0123")
