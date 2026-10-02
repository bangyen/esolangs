"""Executed deterministic chunk expansion for narrow Thue sources."""

import pytest

from esolangs import generate
from esolangs import tools as boolean
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.thue import _Machine, _matches
from esolangs.interpreters.other.thue import run as run_thue
from esolangs.interpreters.randomness import Seeded
from esolangs.tools.thue import thue
from tests.tools.reader_support import _TABLES, _bits


def _execute(table: str, row: int, width: int) -> None:
    n = len(table).bit_length() - 1
    io = ScriptedIO("\n".join(f"{row:0{n}b}"))
    machine = _Machine(generate("Thue", table, width), io, Seeded(row))
    for _ in range(5 * len(table) + 4 * n + 10):
        if machine.halted:
            break
        assert len(_matches(machine.state, machine.rules)) == 1
        machine.step()
    assert machine.halted
    assert io.getvalue() == table[row]
    assert io.reads == n


@pytest.mark.medium
@pytest.mark.parametrize("width", [1, 7, 8, 9, 10, 13, 40])
def test_narrow_sources_execute_every_three_input_table(width: int) -> None:
    for value in range(256):
        table = f"{value:08b}"
        floor = max(map(len, thue(table, 1).splitlines()))
        assert max(map(len, thue(table, width).splitlines())) <= max(width, floor)
        for row in range(8):
            _execute(table, row, width)


def test_layout_never_widens_the_natural_source() -> None:
    for n in range(1, 9):
        table = "".join(str(row.bit_count() & 1) for row in range(1 << n))
        natural = max(map(len, thue(table).splitlines()))
        for width in range(1, natural + 2):
            assert max(map(len, thue(table, width).splitlines())) <= natural
    for table in ("01", "0110", "01101001"):
        plain = thue(table)
        natural = max(map(len, plain.splitlines()))
        for width in (natural, natural + 1):
            assert thue(table, width) == plain
        for width in range(1, natural):
            assert max(map(len, thue(table, width).splitlines())) <= max(width, 9)
            for row in range(len(table)):
                _execute(table, row, width)


@pytest.mark.medium
def test_expansion_crosses_name_widths_without_rewrite_collisions() -> None:
    for n in (4, 6, 8):
        table = "".join(str(row.bit_count() & 1) for row in range(1 << n))
        for width in (1, 13, 40, 80):
            program = thue(table, width)
            if width < len(table) + 3:
                assert max(map(len, program.splitlines())) < len(table) + 3
            for row in (0, 1, len(table) // 2, len(table) - 1):
                _execute(table, row, width)


@pytest.mark.medium
def test_chunk_bounds_stay_narrower_across_marker_digit_boundaries() -> None:
    """Expansion needs T>=8; its bound max(width,9,3d+3) is below T+3."""
    for n, floor in ((3, 7), (6, 9), (11, 12)):
        table = "".join(str(row.bit_count() & 1) for row in range(1 << n))
        natural = max(map(len, thue(table).splitlines()))
        assert max(map(len, thue(table, 1).splitlines())) == floor
        for width in (1, natural - 1):
            assert max(map(len, thue(table, width).splitlines())) < natural
        for row in (0, len(table) - 1):
            _execute(table, row, 1 if n < 11 else 80)


@pytest.mark.medium
def test_short_tree_executes_one_and_two_input_tables() -> None:
    """Every rewrite is unique, including constant tables, and reads in order."""
    for n in (1, 2):
        for value in range(1 << (1 << n)):
            table = format(value, f"0{1 << n}b")
            assert max(map(len, thue(table, 1).splitlines())) == 7
            for row in range(1 << n):
                _execute(table, row, 1)
    assert len(thue("0110", 1)) == 90


def test_thue_spells_the_table_once_and_its_rules_are_fixed() -> None:
    """Its emission is the table plus a constant: ``T + 187`` characters.

    ``T + 199`` before the line read became the marker itself: the rules
    ``0::=P`` and ``1::=Q`` only renamed it, so every three-input table
    sheds twelve characters, 52,992 to 49,920 over all 256.
    """
    sizes = [len(boolean.thue("01" * (2 ** (n - 1)))) for n in (1, 2, 3, 4)]
    assert sizes == [2**n + 187 for n in (1, 2, 3, 4)]
    total = sum(len(boolean.thue(f"{value:08b}")) for value in range(256))
    assert total == 49920


@pytest.mark.parametrize("table", _TABLES)
def test_thue_never_leaves_the_draw_a_choice(table: str) -> None:
    """Every state a generated program reaches offers exactly one rewrite.

    Thue picks the rewrite at random, by spec, and the interpreter draws.
    What makes these programs reproducible anyway is this invariant, so it is
    asserted by running them rather than argued in a docstring: one applicable
    rule at one position, in every state, on every row.
    """
    from esolangs.interpreters.other.thue import _Machine, _matches

    n = len(table).bit_length() - 1
    program = boolean.thue(table)
    for row in range(2**n):
        stdin = "".join(f"{bit}\n" for bit in _bits(row, n))
        machine = _Machine(program, ScriptedIO(stdin), Seeded(row))
        while not machine.halted:
            found = _matches(machine.state, machine.rules)
            assert len(found) == 1, (table, row, machine.state[:60], found)
            machine.step()


@pytest.mark.parametrize("table", _TABLES)
def test_thue_answers_the_same_under_every_draw(table: str) -> None:
    """Three seeds and the unseeded ``secrets`` draw agree, row by row."""
    n = len(table).bit_length() - 1
    program = boolean.thue(table)
    for row in range(2**n):
        stdin = "".join(f"{bit}\n" for bit in _bits(row, n))
        answers = set()
        for rng in (Seeded(0), Seeded(1), Seeded(9), None):
            io = ScriptedIO(stdin)
            run_thue(program, io, rng)
            answers.add(io.getvalue())
        assert answers == {table[row]}, (table, row, answers)


@pytest.mark.medium
def test_thue_contracted_heads_keep_a_unique_rewrite() -> None:
    """Ready and waiting symbols leave exactly one rewrite before each read."""
    from esolangs.interpreters.other.thue import _Machine, _matches

    assert max(map(len, boolean.thue("0110", 1).splitlines())) == 7
    for n in range(1, 4):
        for value in range(1 << (1 << n)):
            table = format(value, f"0{1 << n}b")
            program = boolean.thue(table, 1)
            for row, expected in enumerate(table):
                stdin = "".join(f"{bit}\n" for bit in _bits(row, n))
                io = ScriptedIO(stdin)
                machine = _Machine(program, io, Seeded(row))
                while not machine.halted:
                    assert len(_matches(machine.state, machine.rules)) == 1
                    machine.step()
                assert io.getvalue() == expected


@pytest.mark.medium
def test_thue_fixed_width_chunk_names_expand_before_reading() -> None:
    """The marker alphabet excludes every table and control symbol."""
    from esolangs.interpreters.other.thue import _Machine, _matches

    for n in range(4, 7):
        table = "".join(
            str((row * 17 + row // 3).bit_count() % 2) for row in range(1 << n)
        )
        program = boolean.thue(table, 1)
        assert max(map(len, program.splitlines())) == 9
        for row, expected in enumerate(table):
            stdin = "".join(f"{bit}\n" for bit in _bits(row, n))
            io = ScriptedIO(stdin)
            machine = _Machine(program, io, Seeded(row))
            while not machine.halted:
                assert len(_matches(machine.state, machine.rules)) == 1
                machine.step()
            assert io.getvalue() == expected
