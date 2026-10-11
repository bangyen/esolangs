"""Dimensional generator tests."""

import pytest

from esolangs import generate
from esolangs import tools as boolean
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.dimensional import _Machine
from esolangs.tools.dimensional import dimensional
from esolangs.tools.wrap import (
    wrap_program,
)
from tests.support.witness_tables import witnesses
from tests.tools.boolean_runners import (
    run_dimensional,
)


@pytest.mark.parametrize("n", [1, 2, 8])
@pytest.mark.parametrize("bit", ["0", "1"])
def test_constant_reads_into_scratch_and_prints_a_fresh_literal(
    n: int, bit: str
) -> None:
    table = bit * (1 << n)
    programs = [generate("Dimensional", table, width=w) for w in (None, 1, 20)]
    programs.append(generate("Dimensional", table, balance=True))
    for program in programs:
        for row in range(1 << n):
            io = ScriptedIO("\n".join(f"{row:0{n}b}") + "\nextra")
            machine = _Machine(program, io)
            for _ in range(1000):
                if machine.halted:
                    break
                machine.step()
            assert machine.halted
            assert (io.getvalue(), io.reads) == (bit, n)


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
    # Ignored inputs paint nothing: 0011 ignores the second, 0101 the first.
    xor = len(dimensional("0110", 1))
    assert len(dimensional("0011", 1)) < xor
    assert len(dimensional("0101", 1)) < xor


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
        """One painted cell an entry, whichever bit, until a zero run is a loop."""
        full = "0" + "1" * 63
        spaced = "01" * 31 + "11"
        one = "0" * 63 + "1"
        assert len(boolean.dimensional(full)) == len(boolean.dimensional(spaced))
        assert len(boolean.dimensional(one)) < len(boolean.dimensional(full))
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


@pytest.mark.parametrize(
    ("program", "token"),
    [
        ("+=30.", "=30"),
        ("+:x.", ":x"),
        ("+>~3.", ">~3"),
        ("+!12.", "!12"),
        ("+?7.", "?7"),
        ("+$4.", "$4"),
        ("+{2}.", "{2"),
    ],
)
def test_dimensional_keeps_every_operand_with_its_command(
    program: str, token: str
) -> None:
    """A break inside any of these changes what the program does."""
    assert token in wrap_program(program, "dimensional", 1).split("\n")
