"""Execution tests for the Crement Boolean-generator prototype."""

from itertools import product

import pytest

from esolangs.exceptions import TruthTableError
from esolangs.tools.crement import crement, instantiate_crement


def _result(program: str) -> str:
    """Execute the generated one-instruction Crement program."""
    _opcode, address, data = program.split()
    pc = 0
    seen: set[int] = set()
    while pc == 0 and pc not in seen:
        seen.add(pc)
        pc = int(address) if int(data) > 0 else pc + 1
    return "1" if pc in seen else "0"


@pytest.mark.parametrize(
    "table",
    ["00", "01", "10", "11", "0001", "0110", "0111", "1110", "01101001"],
)
def test_representative_tables_execute(table: str) -> None:
    template = crement(table)
    n = len(table).bit_length() - 1
    got = "".join(
        _result(instantiate_crement(template, list(bits)))
        for bits in product(range(2), repeat=n)
    )
    assert got == table


def test_template_carries_each_input_and_the_table_as_comments() -> None:
    assert crement("0110").splitlines() == [
        "* Crement Boolean prototype",
        "* 0110",
        "* {X0}{X1}",
    ]


@pytest.mark.parametrize("bits", [[], [0], [0, 2], [0, 1, 0]])
def test_instantiation_rejects_wrong_bits(bits: list[int]) -> None:
    with pytest.raises(TruthTableError):
        instantiate_crement(crement("0110"), bits)


@pytest.mark.parametrize(
    "template",
    ["", "* Crement Boolean prototype\n* 01", "wrong\n* 01\n* {X0}"],
)
def test_instantiation_rejects_malformed_template(template: str) -> None:
    with pytest.raises(ValueError, match="prototype template"):
        instantiate_crement(template, [0])
