"""Boolean generator for decleq."""

from itertools import pairwise

from esolangs.tools.helpers import (
    _ASCII_ONE,
    _ASCII_ZERO,
    _validate_truth_table,
    essential_inputs,
    subtree_ids,
)

__all__ = ["decleq"]


def decleq(truth_table: str) -> str:
    """Return a Decleq program for a binary, MSB-first ``2**n`` truth table.

    Decrement-and-branch normalizes bytes 48/49 to 1/2 in 47 steps; zero
    then decrements to 0 and jumps, while one falls through. All n inputs
    are read, but only essential inputs pay that normalization cost.

    A full tree's T-1 distinct absolute targets cost Theta(T log T) digits.
    Stop k levels short, 2**k >= 2n: each leaf indexes a 2**k-cell table.
    A counter starts at 2**k; low one-bits subtract their weights using
    2**k-1 unrolled decrements. A leaf adjusts its output address by that
    counter and prints the selected 48/49. T three-character table cells
    plus at most T/(2n) O(n)-digit branches give O(T) size, O(n) execution.
    Constant subtrees use shared print gadgets; 11110000 needs one branch.
    A subtree that repeats an earlier one at its level is not emitted again:
    a zero side branches to the copy, a one side jumps to it in one
    instruction, so the program is never longer than the plain tree.

    Cell 0 jumps over two ``-2 K 0; 0 0 END`` gadgets, constants 48/49,
    the counter and read cells. Code starts at the next multiple of three;
    cell 0 supplies every unconditional decrement and END is one past memory.
    """
    n = _validate_truth_table(truth_table)
    # The table depth: the fewest low inputs whose lookup pays for the
    # tree above it, ``2**k >= 2 n``, and never more inputs than there are.
    k = min(n, (2 * n - 1).bit_length())
    span = 2**k

    # ``changes[r]`` counts the value changes before row ``r``, so a run is
    # constant iff its two ends agree; a slice-and-set per node would cost
    # ``Theta(n T)`` over the tree.
    changes = [0]
    for previous, current in pairwise(truth_table):
        changes.append(changes[-1] + (previous != current))

    def constant(row: int, width: int) -> bool:
        """Whether the ``width`` rows starting at ``row`` all agree."""
        return changes[row] == changes[row + width - 1]

    # Only the inputs the table depends on need the normalization chain;
    # see the docstring for why an ignored one still reads but never routes.
    essential = set(essential_inputs(truth_table, n))

    # Fixed low addresses; a leaf reaches a gadget by ``0 0 gadget``.
    out_zero, halt, out_one = 3, 6, 9
    k48, k49, counter = 15, 16, 17
    read_cells = [18 + i for i in range(n)]
    # The code starts on a multiple of three so wrap_grid's columns are the
    # operand columns; at most two pad cells.
    code = -(-(18 + n) // 3) * 3

    mem: list[int] = [0, 0, code, -2, k48, 0, 0, 0, 0, -2, k49, 0, 0, 0, 0]
    mem += [_ASCII_ZERO, _ASCII_ONE, span] + [0] * (code - 18)
    ends = [halt + 2, halt + 8]  # the two END operands, patched last

    def emit(a: int, b: int, c: int) -> None:
        mem.extend([a, b, c])

    def pc() -> int:
        return len(mem)

    def patch(addr: int, c: int) -> None:
        mem[addr + 2] = c

    # A read falls through and these decrements never reach 0: target 0.
    for rc in read_cells:
        emit(-1, rc, 0)
    for i, rc in enumerate(read_cells):
        if i not in essential:
            continue
        for _ in range(47):
            emit(rc, rc, 0)

    # Index: the low ``k`` inputs, each one taking its weight off the
    # counter.  A zero (1) decrements to 0 and jumps the run; a one (2)
    # falls into it.
    for i in range(n - k, n):
        if i not in essential:
            continue
        rc = read_cells[i]
        weight = 2 ** (n - 1 - i)
        emit(rc, rc, pc() + 3 * (weight + 1))
        for _ in range(weight):
            emit(counter, counter, 0)

    def leaf(row: int) -> None:
        """Print row ``counter`` of the table at ``row``, then halt.

        ``counter`` holds ``2**k - index``; the loop runs it down and takes
        one off the output's address operand per pass but the last, so the
        operand ends ``index`` above the table's base.
        """
        loop = pc()
        out = loop + 9
        emit(counter, counter, out)
        emit(out + 1, out + 1, 0)
        emit(0, 0, loop)
        emit(-2, out + 6 + span - 1, 0)
        emit(0, 0, halt)
        mem.extend(_ASCII_ZERO + int(c) for c in truth_table[row : row + span])

    ids = subtree_ids(truth_table)
    done: dict[tuple[int, int], int] = {}

    def earlier(level: int, row: int) -> int | None:
        """Address of an equal non-constant subtree already emitted, if any."""
        if constant(row, 2 ** (n - level)):
            return None
        return done.get((level, ids[level][row >> (n - level)]))

    def node(level: int, row: int) -> None:
        width = 2 ** (n - level)
        if (copy := earlier(level, row)) is not None:
            emit(0, 0, copy)
            return
        if constant(row, width):
            emit(0, 0, out_one if truth_table[row] == "1" else out_zero)
            return
        done[level, ids[level][row >> (n - level)]] = pc()
        if level == n - k:
            leaf(row)
            return
        rc = read_cells[level]
        emit(rc, rc, 0)
        branch = pc() - 3
        node(level + 1, row + width // 2)
        target = earlier(level + 1, row)
        if target is None:
            target = pc()
            node(level + 1, row)
        patch(branch, target)

    node(0, 0)

    # Deriving END from the cell count keeps it out of wrap_grid's way: a
    # leaf's table-top operand is within ``2**k + 8`` of it, so the two
    # differ by at most one digit, and _cell_width drops an outlier only at
    # twice the next width.
    for addr in ends:
        mem[addr] = len(mem)
    return " ".join(map(str, mem))
