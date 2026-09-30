"""Executed deterministic chunk expansion for narrow Thue sources."""

import pytest

from esolangs import generate
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.thue import _Machine, _matches
from esolangs.interpreters.randomness import Seeded
from esolangs.tools.thue import thue


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
    for n, floor in ((3, 9), (6, 9), (11, 12)):
        table = "".join(str(row.bit_count() & 1) for row in range(1 << n))
        natural = max(map(len, thue(table).splitlines()))
        assert max(map(len, thue(table, 1).splitlines())) == floor
        for width in (1, natural - 1):
            assert max(map(len, thue(table, width).splitlines())) < natural
        for row in (0, len(table) - 1):
            _execute(table, row, 1 if n < 11 else 80)
