"""bitwise_cyclic_tag generator tests."""

import pytest

import esolangs
from esolangs.generation.helpers import TEMPLATE_CHAR, fill_runs
from esolangs.languages import generators as boolean
from esolangs.languages.bitwise_cyclic_tag.generator import PAIR as BCT_PAIR
from esolangs.languages.bitwise_cyclic_tag.interpreter import (
    _Machine as BctMachine,
)
from esolangs.languages.bitwise_cyclic_tag.interpreter import run as run_bct
from esolangs.runtime._evaluate import _evaluate
from esolangs.runtime.io import ScriptedIO
from tests.generators.reader_support import _TABLES
from tests.support.witness_tables import parity as _parity
from tests.support.witness_tables import row_bits as _bits


def _bct_program(table: str, row: int) -> str:
    """Return the instantiated BCT source for one row."""
    n = len(table).bit_length() - 1
    template = boolean.bitwise_cyclic_tag(table)
    return fill_runs(template, TEMPLATE_CHAR, [BCT_PAIR] * n, _bits(row, n))


def _bct_answer(table: str, row: int) -> str:
    """Return the bit the generated BCT program's last deletion consumed."""
    io = ScriptedIO("")
    run_bct(_bct_program(table, row), io)
    return io.getvalue()


def test_bitwise_cyclic_tag_answers_every_row() -> None:
    """Every program's last deletion is its table's bit, and a 1 answer must
    not run on into the rows below it (no cascade)."""
    for table in _TABLES:
        n = len(table).bit_length() - 1
        for row in range(2**n):
            assert _bct_answer(table, row) == table[row], (table, row)
    assert _bct_answer("1000", 0) == "1"
    assert _bct_answer("1" + "0" * 15, 0) == "1"


def test_bitwise_cyclic_tag_spells_the_table_at_a_fixed_rate() -> None:
    """Size is exactly ``13T/2 + 2n + 3`` when every input matters, else less."""
    for n in (1, 2, 3, 4, 8):
        rows = 2**n
        size = 13 * rows // 2 + 2 * n + 3
        assert len(boolean.bitwise_cyclic_tag(_parity(n))) == size
        assert len(boolean.bitwise_cyclic_tag("0" * rows)) < size


def test_bitwise_cyclic_tag_walks_forward_in_a_fixed_number_of_steps() -> None:
    """Linear in the table, wrapping only to eat a 0 answer, ending on its row."""
    for n in (1, 2, 3, 6):
        rows, table, counts = 2**n, _parity(n), []
        for row in range(rows):
            machine = BctMachine(_bct_program(table, row), ScriptedIO(""))
            previous, steps = -1, 0
            while not machine.halted:
                # A 0 answer left in the queue is eaten by the first delete
                # after the wrap; a 1 never survives its cell.
                assert machine.head > previous or machine.live == "0", (n, row)
                previous = machine.head
                machine.step()
                steps += 1
            counts.append(steps)
        assert max(counts) <= 19 * rows // 4 + n + 2, (n, counts)
        assert counts == sorted(counts), (n, counts)


@pytest.mark.parametrize("n", [1, 3, 8])
@pytest.mark.parametrize("bit", ["0", "1"])
def test_constant_deletes_inputs_and_literal_answer(n, bit) -> None:
    table = bit * (1 << n)
    template = esolangs.generate("Bitwise Cyclic Tag", table)
    assert template == "0," + "$" * n + bit
    assert len(template) == n + 3
    for options in ({}, {"width": 1}, {"balance": True}):
        program = esolangs.generate("Bitwise Cyclic Tag", table, **options)
        assert _evaluate("Bitwise Cyclic Tag", program, inputs=n) == table
    for row in (0, (1 << n) - 1):
        io = ScriptedIO("")
        machine = BctMachine(_bct_program(table, row), io)
        for _ in range(n + 1):
            assert not machine.halted
            machine.step()
        assert machine.halted
        assert (machine.read, machine.answer, machine.program) == (n + 1, bit, "0")
        machine.step()
        assert io.getvalue() == bit
