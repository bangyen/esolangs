"""Boolean-function generators for Dimensional.

:func:`dimensional` returns whichever of two constructions is shorter: the
survivor walk (:func:`_dimensional_survivor`), which leaves exactly one
live cell holding the table entry and wins on sparse tables, or the
decision tree (:func:`dimensional_tree`), which wins on dense ones.
:class:`_Dimensional` accumulates the program for the survivor walk.
"""

from esolangs.tools.boolean.helpers import (
    _ASCII_ZERO,
    _maybe_complement,
    _validate_truth_table,
    decision_tree_program,
)
from esolangs.tools.wrap import shortest

__all__ = ["dimensional", "dimensional_tree"]


class _Dimensional:
    """Emits Dimensional code on dimension 0 with a fixed cell layout.

    A bare ``>``/``<`` takes its dimension from the current cell's value
    (usually nonzero mid-program), so every move is pinned with an explicit
    ``>0``/``<0``.

    Cells: 0 = result, 1..n = inputs (0/1), n+1..2n = NOT of each input,
    2n+1 = survivor, then four shared scratch cells (a, b, c, d).
    """

    def __init__(self, n: int) -> None:
        self.n = n
        self.code: list[str] = []
        self.ptr = 0
        self.inputs = list(range(1, n + 1))
        self.nots = list(range(n + 1, 2 * n + 1))
        self.survivor = 2 * n + 1
        self.a, self.b, self.c, self.d = (2 * n + 2, 2 * n + 3, 2 * n + 4, 2 * n + 5)

    def move(self, dst: int) -> None:
        delta = dst - self.ptr
        self.code.append(">0" * delta if delta >= 0 else "<0" * -delta)
        self.ptr = dst

    def zero(self, cell: int) -> None:
        self.move(cell)
        self.code.append("[-]")

    def copy(self, src: int, dst: int) -> None:
        """Copy ``src`` to ``dst`` preserving ``src`` (scratch a, b, c)."""
        self.zero(self.a)
        self.zero(self.b)
        self.zero(self.c)
        self.move(src)
        self.code.append("[")
        self.move(self.a)
        self.code.append("+")
        self.move(self.b)
        self.code.append("+")
        self.move(src)
        self.code.append("-]")
        self.move(self.a)
        self.code.append("[")
        self.move(src)
        self.code.append("+")
        self.move(self.a)
        self.code.append("-]")
        self.move(self.b)
        self.code.append("[")
        self.move(dst)
        self.code.append("+")
        self.move(self.b)
        self.code.append("-]")
        self.move(dst)

    def kill_survivor(self) -> None:
        """Survivor *= (scratch c == 0); consumes c."""
        self.move(self.c)
        self.code.append("[")
        self.move(self.survivor)
        self.code.append("[-]")
        self.move(self.c)
        self.code.append("-]")


def dimensional(truth_table: str) -> str:
    """Build a Dimensional program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    Dimensional is brainfuck on a multidimensional tape and has no halt
    command, so a decision tree cannot rely on halting at the leaf.  Two
    generators exist with complementary strengths, and ``dimensional``
    returns the shorter of the two for the given table:

    - the survivor evaluator: each input is read and normalized to 0/1, the
      NOT of each bit is precomputed, and every row whose table entry is one
      is tested by a survivor cell (``S``), summed into the result cell, and
      printed as ``48 + sum`` (or ``49 - sum`` when the table's zeros are
      cheaper).  Best for sparse tables — an AND-8 is ~4.4K characters.
    - :func:`dimensional_tree`: a decision tree sharing the bit tests.
      Best for dense tables — XOR-8 is ~8x smaller than the survivor.
    """
    return shortest(_dimensional_survivor(truth_table), dimensional_tree(truth_table))


def _dimensional_survivor(truth_table: str) -> str:
    """Build the survivor-cell evaluator for the given truth table."""
    n = _validate_truth_table(truth_table)
    table, use_complement = _maybe_complement(truth_table)

    cell = _Dimensional(n)
    for i in cell.inputs:
        cell.move(i)
        cell.code.append(",")
        cell.code.append("-" * _ASCII_ZERO)
    for i in range(n):
        cell.copy(cell.inputs[i], cell.c)
        cell.zero(cell.d)
        cell.code.append("+")
        cell.move(cell.c)
        cell.code.append("[")
        cell.move(cell.d)
        cell.code.append("-")
        cell.move(cell.c)
        cell.code.append("-]")
        cell.copy(cell.d, cell.nots[i])
    cell.zero(0)
    for row, ch in enumerate(table):
        if ch == "0":
            continue
        cell.move(cell.survivor)
        cell.code.append("[-]+")
        for i in range(n):
            bit = (row >> (n - 1 - i)) & 1
            cell.copy(cell.nots[i] if bit else cell.inputs[i], cell.c)
            cell.kill_survivor()
        cell.move(cell.survivor)
        cell.code.append("[")
        cell.move(0)
        cell.code.append("+")
        cell.move(cell.survivor)
        cell.code.append("-]")
    cell.move(0)
    if use_complement:
        cell.zero(cell.a)
        cell.code.append("+")
        cell.move(0)
        cell.code.append("[")
        cell.move(cell.a)
        cell.code.append("-")
        cell.move(0)
        cell.code.append("-]")
        cell.zero(0)
        cell.code.append("+" * _ASCII_ZERO)
        cell.move(cell.a)
        cell.code.append("[")
        cell.move(0)
        cell.code.append("+")
        cell.move(cell.a)
        cell.code.append("-]")
        cell.move(0)
    else:
        cell.code.append("+" * _ASCII_ZERO)
    cell.code.append(".")
    return "".join(cell.code)


def dimensional_tree(truth_table: str) -> str:
    """Build a decision-tree Dimensional program for the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first); the table length implies ``n``.

    The construction is :func:`decision_tree_program`, shared with
    :func:`bf_tree`; every move is pinned ``>0``/``<0`` because a bare move
    would take the cell value as the dimension.  The tree is O(2**n)
    characters and wins on dense tables; the survivor evaluator
    (:func:`_dimensional_survivor`) wins on sparse ones.
    """
    return decision_tree_program(truth_table, ">0", "<0")
