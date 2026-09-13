"""Execution tests for the Nopstacle Boolean-generator prototype."""

from itertools import product

import pytest

from esolangs.exceptions import TruthTableError
from esolangs.tools.nopstacle import instantiate_nopstacle, nopstacle

_DELTA = ((-1, 0), (0, -1), (1, 0), (0, 1))


def _result(program: str) -> str:
    """Run enough Nopstacle steps to prove a local cycle or copy crossing."""
    rows = program.splitlines()
    height, width = len(rows), len(rows[0])
    x = y = 0
    direction = 2  # down
    seen: set[tuple[int, int, int]] = set()
    for _ in range(width * height * 4 + 1):
        copy = (x // width, y // height)
        if copy != (0, 0):
            return "1"
        state = (x, y, direction)
        if state in seen:
            return "0"
        seen.add(state)
        dx, dy = _DELTA[direction]
        nx, ny = x + dx, y + dy
        blocked = nx < 0 or ny < 0 or rows[ny % height][nx % width] == "#"
        if blocked:
            direction = (direction + 1) % 4
        else:
            x, y = nx, ny
    raise AssertionError("the prototype gadget neither cycled nor crossed a copy")


@pytest.mark.parametrize(
    "table",
    ["00", "01", "10", "11", "0001", "0110", "0111", "1110", "01101001"],
)
def test_representative_tables_execute(table: str) -> None:
    template = nopstacle(table)
    n = len(table).bit_length() - 1
    got = "".join(
        _result(instantiate_nopstacle(template, list(bits)))
        for bits in product(range(2), repeat=n)
    )
    assert got == table


def test_template_carries_each_input_and_the_table() -> None:
    assert nopstacle("0110").splitlines() == [
        "Nopstacle Boolean prototype",
        "0110",
        "{X0}{X1}",
    ]


def test_instantiated_program_is_rectangular_nopstacle() -> None:
    program = instantiate_nopstacle(nopstacle("0110"), [1, 0])
    rows = program.splitlines()
    assert {char for row in rows for char in row} <= {" ", "#"}
    assert len({len(row) for row in rows}) == 1
    assert rows[0][0] == " "


@pytest.mark.parametrize("bits", [[], [0], [0, 2], [0, 1, 0]])
def test_instantiation_rejects_wrong_bits(bits: list[int]) -> None:
    with pytest.raises(TruthTableError):
        instantiate_nopstacle(nopstacle("0110"), bits)
