"""Execution tests for the Nopstacle Boolean-generator prototype."""

from itertools import product

import pytest

from esolangs.exceptions import TruthTableError
from esolangs.interpreters.grid_based.nopstacle import _Machine
from esolangs.tools.nopstacle import instantiate_nopstacle, nopstacle
from esolangs.vm import run_until_halt_or_cycle


def _result(program: str) -> str:
    """Return the termination answer from the registered interpreter."""
    return "0" if run_until_halt_or_cycle(_Machine(program.splitlines())) else "1"


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


def test_instantiated_program_is_nopstacle_source() -> None:
    program = instantiate_nopstacle(nopstacle("0110"), [1, 0])
    rows = program.splitlines()
    assert {char for row in rows for char in row} <= {" ", "#"}
    assert _Machine(rows).grid[0][0] == " "


@pytest.mark.parametrize("bits", [[], [0], [0, 2], [0, 1, 0]])
def test_instantiation_rejects_wrong_bits(bits: list[int]) -> None:
    with pytest.raises(TruthTableError):
        instantiate_nopstacle(nopstacle("0110"), bits)
