"""bitwise_cyclic_tag generator tests."""

import pytest

from esolangs import tools as boolean
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.queue_based.bitwise_cyclic_tag import (
    _Machine as BctMachine,
)
from esolangs.interpreters.queue_based.bitwise_cyclic_tag import (
    run as run_bct,
)
from esolangs.tools.bitwise_cyclic_tag import PAIR as BCT_PAIR
from esolangs.tools.helpers import TEMPLATE_CHAR, fill_runs
from tests.tools.reader_support import _TABLES, _bits


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
    for table in _TABLES:
        n = len(table).bit_length() - 1
        for row in range(2**n):
            assert _bct_answer(table, row) == table[row], (table, row)


@pytest.mark.slow
def test_bitwise_cyclic_tag_answers_every_table_to_three_inputs() -> None:
    for n in (1, 2, 3):
        for value in range(2 ** (2**n)):
            table = bin(value)[2:].zfill(2**n)
            for row in range(2**n):
                assert _bct_answer(table, row) == table[row], (table, row)


def test_bitwise_cyclic_tag_spells_the_table_at_a_fixed_rate() -> None:
    """Size is exactly ``8T + 2n + 1``, not merely ``O(T)``.

    Four bits of program per row for the table, four more per row for the
    walk that addresses it, and the data-string's ``n`` inputs, sentinel and
    separator.  Exact rather than bounded because the construction has no
    table-dependent choices at all: a folded table emits the same length as
    parity does, which is the trade for having no branch to fold into.
    """
    for n in (1, 2, 3, 4, 8):
        rows = 2**n
        sizes = {
            len(boolean.bitwise_cyclic_tag(table))
            for table in ("0" * rows, "1" * rows, ("01" * rows)[:rows])
        }
        assert sizes == {8 * rows + 2 * n + 1}, n


def test_bitwise_cyclic_tag_runs_in_a_fixed_number_of_steps() -> None:
    """The walk is linear in the table and ends on the row it addressed.

    ``5T + n`` at the last row and fewer below it, since the walk stops as
    soon as it arrives: the step count *is* the address, which is the whole
    construction.  A regression that made the pointer traverse the table
    more than once would show here and nowhere else -- the answers would
    still be right.
    """
    for n in (1, 2, 3, 6):
        rows = 2**n
        table = ("01" * rows)[:rows]
        counts = []
        for row in range(rows):
            machine = BctMachine(_bct_program(table, row), ScriptedIO(""))
            steps = 0
            while not machine.halted:
                machine.step()
                steps += 1
            counts.append(steps)
        assert max(counts) == 5 * rows + n, (n, counts)
        assert counts == sorted(counts), (n, counts)
        assert counts[-1] - counts[0] == 3 * (rows - 1), (n, counts)


def test_bitwise_cyclic_tag_never_wraps_its_program() -> None:
    """The cyclic schedule is unused: the pointer only ever moves forward.

    That is what makes the emission loop-less.  The interpreter's wrap is
    real and covered by its own tests; this asserts the *generator* never
    needs it, which is the property a step-count bound rests on.
    """
    table = "01101001"
    for row in range(8):
        machine = BctMachine(_bct_program(table, row), ScriptedIO(""))
        previous = -1
        while not machine.halted:
            assert machine.head > previous, (row, machine.head, previous)
            previous = machine.head
            machine.step()


def test_bitwise_cyclic_tag_does_not_cascade_a_one() -> None:
    """A 1 answer must not run on into the rows below it.

    The readout appends the answer to the data-string, so the cell that
    produced it has to consume it too -- otherwise the next row's ``1x``
    reads it and a 1 walks down the table until it meets a 0, returning that
    instead.  Row 0 of ``1000`` is the case: a 1 with nothing but 0s after
    it, so a cascade would answer 0 and every other row would still pass.
    """
    assert _bct_answer("1000", 0) == "1"
    assert _bct_answer("1" + "0" * 15, 0) == "1"
