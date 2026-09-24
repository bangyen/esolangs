"""Boolean-function generator for 3D Brainfuck.

The array is three-dimensional, so the construction spends one axis each
instead of interleaving everything on one line: inputs along x, their
flags one step up y, the answer one step along z.  Every move is then a
single character where a linear tape pays two -- a flag is off the row
rather than beside it, and a leaf reaches the answer in one step.

3D Brainfuck has no numeric port, so it cannot drop the ASCII offset the
way Painfuck and Dimensional do; it folds it instead, building 48 once on
the scratch axis and subtracting it from every input in one loop.  The
layout alone was worth 2% -- a flag was already one step away on a linear
tape -- and the fold is what pays.  Folding is not itself a 3D trick and
would shrink :func:`~esolangs.tools.tape.brainfuck` too.
"""

from esolangs.tools.helpers import (
    _ASCII_ZERO,
    _validate_truth_table,
    best_input_order,
    constant_span_test,
)

__all__ = ["three_d_brainfuck"]

#: An array cell, ``(x, y, z)``.
type _Cell = tuple[int, int, int]

#: The move commands per axis, positive then negative.  ``>``/``<`` are the
#: generation-pointer commands and do not move the array at all.
_AXES = (("n", "s"), ("u", "d"), ("e", "w"))


def _path(start: _Cell, target: _Cell) -> str:
    """Return the array moves taking the pointer from ``start`` to ``target``."""
    out: list[str] = []
    for axis, (plus, minus) in enumerate(_AXES):
        delta = target[axis] - start[axis]
        out.append((plus if delta > 0 else minus) * abs(delta))
    return "".join(out)


def three_d_brainfuck(truth_table: str) -> str:
    """Build a 3D Brainfuck program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first).  Input ``k`` is read into ``(k, 0,
    0)`` and its flag sits at ``(k, 1, 0)``; a node sets the flag, tests
    the bit and clears the flag inside, then tests the flag for the zero
    side, so exactly one side fires and both cells are left zero.  The
    answer cell is one step along z from the last input tested, which is
    where every full-depth leaf ends up.
    """
    return best_input_order(truth_table, _three_d_ordered)


def _three_d_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit one input order's program; see :func:`three_d_brainfuck`.

    ``truth_table`` is already permuted; ``perm`` is spent only in the
    cell a node tests.  The reads stay in input order.
    """
    n = _validate_truth_table(truth_table)
    out: list[str] = []
    pos: _Cell = (0, 0, 0)
    # Beside the deepest test, so a full-depth leaf pays one move for it.
    result: _Cell = (perm[n - 1], 0, 1)

    def move(target: _Cell) -> None:
        nonlocal pos
        out.append(_path(pos, target))
        pos = target

    # 48 is built once on the scratch axis and subtracted from every input by
    # one loop, instead of a 48-character run per input: the offset was 49% of
    # the program at n == 4 and 70% at n == 2.  The third axis is what makes it
    # cheap -- the counter and the multiplier sit off the input row and its
    # flag plane, so the loop body walks the row and nothing else.
    multiplier: _Cell = (0, 1, 1)
    counter: _Cell = (0, 0, -1)
    span, step = 6, _ASCII_ZERO // 6

    move(multiplier)
    out.append("+" * span)
    out.append("[-")
    move(counter)
    out.append("+" * step)
    move(result)  # the answer cell carries its own offset from the same loop
    out.append("+" * step)
    move(multiplier)
    out.append("]")

    for k in range(n):
        move((k, 0, 0))
        out.append(",")

    move(counter)
    out.append("[-")
    for k in range(n):
        move((k, 0, 0))
        out.append("-")
    move(counter)
    out.append("]")

    is_constant = constant_span_test(truth_table)

    def constant(level: int, combo: int) -> str | None:
        """Return the shared value of the subtree at ``(level, combo)``, else None."""
        span = 2 ** (n - level)
        return truth_table[combo] if is_constant(combo, combo + span) else None

    def branch(level: int, combo: int) -> None:
        """Emit one side of node ``level``: a leaf when constant, else a subtree."""
        value = constant(level + 1, combo)
        if value is None:
            move((perm[level + 1], 0, 0))
            node(level + 1, combo)
        elif value == "1":
            move(result)
            out.append("+")

    def node(level: int, combo: int) -> None:
        """Emit node ``level``: test its bit and leave both its cells zero."""
        bit: _Cell = (perm[level], 0, 0)
        flag: _Cell = (perm[level], 1, 0)
        one = combo | (1 << (n - 1 - level))
        move(flag)
        out.append("+")  # flag = 1, pending
        move(bit)
        out.append("[-")  # one-side: if the bit is set, and clear it to exit
        move(flag)
        out.append("-")  # the one-side ran, so the zero-side must not
        branch(level, one)
        move(bit)
        out.append("]")
        move(flag)
        out.append("[-")  # zero-side: the flag survived, so the bit was 0
        branch(level, combo)
        move(flag)
        out.append("]")

    move((perm[0], 0, 0))
    node(0, 0)

    # Exactly one leaf fired, so the offset is paid once, here.
    # Exactly one leaf fired, and the answer cell already holds the offset,
    # so a '1' leaf's single ``+`` has made it the right character.
    move(result)
    out.append(".")
    return "".join(out)
