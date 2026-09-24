"""Boolean-function generator for Dimensional.

Dimensional's own pointer, not brainfuck's tape: ``>k`` steps along
*dimension* ``k``, so every input sits one step from the origin whatever
its index, where a linear tape pays ``2k`` to reach the ``k``-th.  ``d``
reads a line as a decimal number, so a 0/1 line needs no ASCII
correction, and ``=30`` sets the answer cell to ``'0'`` from a literal
instead of counting up to it.
"""

from esolangs.tools.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    best_input_order,
    constant_span_test,
)

__all__ = ["dimensional", "dimensional_tree"]

#: One cell: the coordinate of each dimension the pointer has left at zero.
type _Cell = tuple[tuple[int, int], ...]

#: The answer cell, at the origin -- the one cell no input move touches.
_RESULT: _Cell = ()


def _bit(dim: int) -> _Cell:
    """Return the cell holding input ``dim``, one step along its dimension."""
    return ((dim, 1),)


def _flag(dim: int) -> _Cell:
    """Return input ``dim``'s flag cell, two steps along its dimension."""
    return ((dim, 2),)


def _path(start: _Cell, target: _Cell) -> str:
    """Return the moves taking the pointer from ``start`` to ``target``.

    One ``>k``/``<k`` per unit step, so a move costs ``O(1)`` in the
    dimension index rather than one character per cell of a linear walk.
    The dimension is always spelled out: a bare ``>`` would take its
    dimension from the cell's value.
    """
    here = dict(start)
    there = dict(target)
    out: list[str] = []
    for dim in sorted(here.keys() | there.keys()):
        delta = there.get(dim, 0) - here.get(dim, 0)
        step = f">{dim}" if delta > 0 else f"<{dim}"
        out.append(step * abs(delta))
    return "".join(out)


def dimensional(truth_table: str) -> str:
    """Build a Dimensional program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first).  Dimensional has no halt command, so
    this is :func:`dimensional_tree`.
    """
    return dimensional_tree(truth_table)


def dimensional_tree(truth_table: str) -> str:
    """Build a decision-tree Dimensional program for the given truth table.

    Input ``k`` is read as a number into the cell one step along dimension
    ``k``, with its flag two steps along the same dimension; the answer
    cell is the origin, which no input move reaches.  A node sets the
    flag, tests the bit and clears the flag inside, then tests the flag
    for the zero side, so exactly one side fires and both cells are left
    zero.
    """
    return best_input_order(truth_table, _dimensional_ordered)


def _dimensional_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit one input order's program; see :func:`dimensional_tree`.

    ``truth_table`` is already permuted; ``perm`` is spent only in the
    dimension a node tests.  The reads stay in input order.
    """
    n = _validate_truth_table(truth_table)
    out: list[str] = []
    pos: _Cell = _RESULT

    def move(target: _Cell) -> None:
        nonlocal pos
        out.append(_path(pos, target))
        pos = target

    # The answer is a character, so the offset is one two-digit literal
    # here rather than 48 increments below the tree.  A '1' leaf adds one.
    out.append(f"={_ASCII_ZERO:02x}")

    for k in range(n):
        move(_bit(k))
        out.append("d")  # read a line as a number: a 0/1 line is already 0/1

    is_constant = constant_span_test(truth_table)

    def constant(level: int, combo: int) -> str | None:
        """Return the shared value of the subtree at ``(level, combo)``, else None."""
        span = 2 ** (n - level)
        return truth_table[combo] if is_constant(combo, combo + span) else None

    def branch(level: int, combo: int) -> None:
        """Emit one side of node ``level``: a leaf when constant, else a subtree."""
        value = constant(level + 1, combo)
        if value is None:
            move(_bit(perm[level + 1]))
            node(level + 1, combo)
        elif value == "1":
            move(_RESULT)
            out.append("+")

    def node(level: int, combo: int) -> None:
        """Emit node ``level``: test its bit and leave both its cells zero."""
        dim = perm[level]
        one = combo | (1 << (n - 1 - level))
        move(_flag(dim))
        out.append("+")  # flag = 1, pending
        move(_bit(dim))
        out.append("[-")  # one-side: if the bit is set, and clear it to exit
        move(_flag(dim))
        out.append("-")  # the one-side ran, so the zero-side must not
        branch(level, one)
        move(_bit(dim))
        out.append("]")
        move(_flag(dim))
        out.append("[-")  # zero-side: the flag survived, so the bit was 0
        branch(level, combo)
        move(_flag(dim))
        out.append("]")

    move(_bit(perm[0]))
    node(0, 0)

    move(_RESULT)
    out.append(".")
    return "".join(out)
