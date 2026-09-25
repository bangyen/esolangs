"""Boolean-function generator for Painfuck.

Painfuck's own commands, not brainfuck's transliterated: ``i`` reads a
line as a *number* and ``o`` prints one, so the ASCII offset the
brainfuck family pays twice per program -- 49% of its characters at
``n == 4``, 70% at ``n == 2`` -- is not paid at all.  ``r`` moves two
right, which is exactly the cell layout's stride, and ``d`` resets the
pointer, so returning to the reads costs one character instead of one
per cell.
"""

from esolangs.tools.helpers import (
    _validate_truth_table,
    best_input_order,
    constant_span_test,
)

__all__ = ["painfuck"]

# The interpreter's two substitution cycles, in the order its cross-check
# scans them: source is pre-shifted here so the trans table recovers the
# intended command.
_CYCLES = ("pevkjzwr", "yuctsobqihald")


def _encode(code: str) -> str:
    """Pre-shift ``code`` so the interpreter's trans table recovers it.

    Each command is rotated ``k`` steps *back* along its own cycle, ``k``
    the number of commands emitted so far, inverting :func:`_translate`.
    """
    out: list[str] = []
    k = 0
    for char in code:
        for cycle in _CYCLES:
            position = cycle.find(char)
            if position != -1:
                out.append(cycle[(position - k) % len(cycle)])
                k += 1
                break
        else:  # pragma: no cover - every emitted command is in a cycle
            raise ValueError(f"Painfuck command {char!r} is not in a cycle")
    return "".join(out)


def _reach(start: int, target: int) -> str:
    """Move from ``start`` to ``target`` with ``r`` (+2) and ``l`` (-1).

    Rightward is two cells a character, so an odd gap overshoots by one
    and steps back; leftward is one cell a character.
    """
    delta = target - start
    if delta < 0:
        return "l" * -delta
    return "r" * ((delta + 1) // 2) + ("l" if delta % 2 else "")


def _move(start: int, target: int) -> str:
    """Return the shorter of walking to ``target`` and restarting at 0.

    ``d`` resets the pointer, which brainfuck cannot do: a leaf deep in
    the tree reaches the result cell in ``1 + target // 2`` characters
    however far right it has walked, instead of one per cell walked back.
    """
    relative = _reach(start, target)
    absolute = "d" + _reach(0, target)
    return relative if len(relative) <= len(absolute) else absolute


def painfuck(truth_table: str) -> str:
    """Build a Painfuck program computing the given truth table.

    ``truth_table`` is a binary string of length ``2**n`` indexed by the
    inputs (most significant first).  Bit ``k`` is read as a number into
    cell ``2k`` with its flag at ``2k + 1``; a node sets the flag, tests
    the bit and clears the flag inside, then tests the flag for the zero
    side, so exactly one side fires and both cells are left zero.  The
    answer accumulates in cell ``2n`` and is printed once, as a number.
    """
    return best_input_order(truth_table, _painfuck_ordered)


def _painfuck_ordered(truth_table: str, perm: tuple[int, ...]) -> str:
    """Emit one input order's program; see :func:`painfuck`.

    ``truth_table`` is already permuted; ``perm`` is spent only in the
    cell a node tests, ``2 * perm[i]``.  The reads stay in input order.
    """
    n = _validate_truth_table(truth_table)
    out: list[str] = []
    pos = 0
    result = 2 * n

    def move(target: int) -> None:
        nonlocal pos
        out.append(_move(pos, target))
        pos = target

    # Read bit k into cell 2k as a number, so a 0/1 line needs no ASCII
    # correction.  ``r`` is the stride, so the reads walk one character a bit.
    for k in range(n):
        out.append("i")
        if k < n - 1:
            move(pos + 2)

    is_constant = constant_span_test(truth_table)

    def constant(level: int, combo: int) -> str | None:
        """Return the shared value of the subtree at ``(level, combo)``, else None."""
        span = 2 ** (n - level)
        return truth_table[combo] if is_constant(combo, combo + span) else None

    def branch(level: int, combo: int) -> None:
        """Emit one side of node ``level``: a leaf when constant, else a subtree.

        A ``'1'`` leaf is ``ps`` (``p`` adds two, ``s`` takes one back);
        a ``'0'`` leaf is nothing, the result cell being zero already.
        """
        value = constant(level + 1, combo)
        if value is None:
            move(2 * perm[level + 1])
            node(level + 1, combo)
        elif value == "1":
            move(result)
            out.append("ps")

    def node(level: int, combo: int) -> None:
        """Emit node ``level``: test its bit and leave both its cells zero."""
        bit = 2 * perm[level]
        flag = bit + 1
        one = combo | (1 << (n - 1 - level))
        move(flag)
        out.append("ps")  # flag = 1, pending
        move(bit)
        out.append("as")  # one-side: if the bit is set, and clear it to exit
        move(flag)
        out.append("s")  # the one-side ran, so the zero-side must not
        branch(level, one)
        move(bit)
        out.append("b")
        move(flag)
        out.append("as")  # zero-side: the flag survived, so the bit was 0
        branch(level, combo)
        move(flag)
        out.append("b")

    move(2 * perm[0])
    node(0, 0)

    # Exactly one leaf fired, leaving 0 or 1 in the result cell.  ``o``
    # prints it as a number, which is already the answer's spelling.
    move(result)
    out.append("o")
    return _encode("".join(out))
