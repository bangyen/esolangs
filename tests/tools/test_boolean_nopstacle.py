"""Execution tests for the Nopstacle Boolean generator."""

import random
from itertools import pairwise, product

import pytest

from esolangs.exceptions import TruthTableError
from esolangs.interpreters.grid_based.nopstacle import _Machine
from esolangs.tools.nopstacle import instantiate_nopstacle, nopstacle
from esolangs.vm import run_until_halt_or_cycle
from tests.tools.test_boolean_contract import _dense


def _result(program: str) -> str:
    """Return the termination answer from the registered interpreter.

    A ``1`` is a proven cycle, not a step budget: the diverging run ends on
    the all-blank bottom row heading right, which the machine's snapshot
    folds to one state, so Brent's algorithm reports it at once.
    """
    return "0" if run_until_halt_or_cycle(_Machine(program.splitlines())) else "1"


def _rows(n: int) -> list[list[int]]:
    return [list(bits) for bits in product(range(2), repeat=n)]


def _check(table: str) -> None:
    """Every row of ``table`` answers correctly, at one program length."""
    n = len(table).bit_length() - 1
    template = nopstacle(table)
    programs = [instantiate_nopstacle(template, bits) for bits in _rows(n)]
    assert len({len(p) for p in programs}) == 1
    assert "".join(map(_result, programs)) == table


@pytest.mark.parametrize("n", [1, 2, 3])
def test_every_table_through_three_inputs(n: int) -> None:
    for index in range(2 ** (2**n)):
        _check(format(index, f"0{2**n}b"))


@pytest.mark.parametrize("n", [4, pytest.param(5, marks=pytest.mark.medium)])
def test_random_tables_at_four_and_five_inputs(n: int) -> None:
    rng = random.Random(n)
    for _ in range(30):
        _check("".join(rng.choice("01") for _ in range(2**n)))


def test_template_holds_each_input_once_in_order() -> None:
    template = nopstacle("01101001")
    slots = [line for line in template.splitlines() if "{X" in line]
    assert [line.strip() for line in slots] == ["{X0}", "{X1}", "{X2}"]
    assert template.count("{X") == 3


def test_instantiated_program_is_a_padded_nopstacle_rectangle() -> None:
    program = instantiate_nopstacle(nopstacle("0110"), [1, 0])
    rows = program.splitlines()
    assert {char for row in rows for char in row} <= {" ", "#"}
    assert len({len(row) for row in rows}) == 1
    assert _Machine(rows).grid[0][0] == " "


def test_a_bit_is_one_run_of_cells_per_level() -> None:
    """Level ``i`` reads its input at ``2**i`` node columns, one pitch apart."""
    template = nopstacle("0" * 8)
    zero = instantiate_nopstacle(template, [0, 0, 0]).splitlines()
    for i in range(3):
        one = instantiate_nopstacle(template, [int(k == i) for k in range(3)])
        diff = [
            (y, x)
            for y, (a, b) in enumerate(zip(zero, one.splitlines(), strict=True))
            for x in range(len(a))
            if a[x] != b[x]
        ]
        assert len(diff) == 2**i
        assert len({y for y, _ in diff}) == 1
        assert {b for _, b in diff} == set(range(28, 0, -(2 ** (3 - i)) * 4))


def test_size_grows_as_the_table_times_its_input_count() -> None:
    """Width doubles per input and each input owns three rows: ``n * 2**n``."""
    sizes = [
        len(instantiate_nopstacle(nopstacle(_dense(n)), [1] * n)) for n in range(1, 9)
    ]
    assert sizes == [89, 220, 527, 1234, 2837, 6424, 14363, 31774]
    for n, (a, b) in enumerate(pairwise(sizes), start=1):
        assert 2 * a < b <= 2 * a * (3 * (n + 1) + 7) / (3 * n + 7)


@pytest.mark.parametrize("bits", [[], [0], [0, 2], [0, 1, 0]])
def test_instantiation_rejects_wrong_bits(bits: list[int]) -> None:
    with pytest.raises(TruthTableError):
        instantiate_nopstacle(nopstacle("0110"), bits)


def test_instantiation_rejects_a_foreign_template() -> None:
    with pytest.raises(ValueError, match="Nopstacle"):
        instantiate_nopstacle("{X1}{X0}", [0, 1])
