"""Boolean generator for decleq."""

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.tools.helpers import (
    _ASCII_ONE,
    _ASCII_ZERO,
    _validate_truth_table,
    constant_span_test,
    essential_inputs,
    read_at,
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
    essential = essential_inputs(truth_table, n)
    # Routing only the essential inputs drops an ignored one's level and the
    # leaves it doubles, but it can move the leaf depth off a constant half
    # the full routing exploits (0100010011111111: 1345 -> 1371), so both run.
    return min(
        _decleq_build(read_at(truth_table, essential, n), n, essential, essential),
        _decleq_build(truth_table, n, list(range(n)), essential),
        key=len,
    )


def _decleq_build(
    truth_table: str, n: int, routes: list[int], normalized: list[int]
) -> str:
    """Build over ``truth_table``, the table read at the inputs ``routes`` names.

    All ``n`` inputs are read; only the ``normalized`` ones pay the chain, and
    only they are counted, so an ignored input left in ``routes`` is a level
    whose sides are equal and share one subtree.
    """
    m = len(routes)
    # The table depth: the fewest low inputs whose lookup pays for the
    # tree above it, ``2**k >= 2 n``, and never more inputs than there are.
    k = min(m, (2 * n - 1).bit_length())
    span = 2**k

    is_constant = constant_span_test(truth_table)

    # Fixed low addresses; a leaf reaches a gadget by ``0 0 gadget``.
    out_zero, halt, out_one = 3, 6, 9
    k48, k49, counter = 15, 16, 17
    read_cells = list(range(18, 18 + n))
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

    # A read falls through and these decrements never reach 0: target 0.
    for rc in read_cells:
        emit(-1, rc, 0)
    for i in normalized:
        for _ in range(47):
            emit(read_cells[i], read_cells[i], 0)

    # Index: the low ``k`` inputs, each one taking its weight off the
    # counter.  A zero (1) decrements to 0 and jumps the run; a one (2)
    # falls into it.
    for j in range(m - k, m):
        if routes[j] not in normalized:
            continue
        rc = read_cells[routes[j]]
        weight = 2 ** (m - 1 - j)
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

    # A constant prints at the root and never looks an id up.
    ids = subtree_ids(truth_table) if m else []
    done: dict[tuple[int, int], int] = {}

    def earlier(level: int, row: int) -> int | None:
        """Address of an equal non-constant subtree already emitted, if any."""
        if is_constant(row, row + 2 ** (m - level)):
            return None
        return done.get((level, ids[level][row >> (m - level)]))

    def node(level: int, row: int) -> None:
        width = 2 ** (m - level)
        if (copy := earlier(level, row)) is not None:
            emit(0, 0, copy)
            return
        if is_constant(row, row + width):
            emit(0, 0, out_one if truth_table[row] == "1" else out_zero)
            return
        done[level, ids[level][row >> (m - level)]] = pc()
        if level == m - k:
            leaf(row)
            return
        rc = read_cells[routes[level]]
        emit(rc, rc, 0)
        branch = pc() - 3
        node(level + 1, row + width // 2)
        target = earlier(level + 1, row)
        if target is None:
            target = pc()
            node(level + 1, row)
        mem[branch + 2] = target

    node(0, 0)

    # Deriving END from the cell count keeps it out of wrap_grid's way: a
    # leaf's table-top operand is within ``2**k + 8`` of it, so the two
    # differ by at most one digit, and _cell_width drops an outlier only at
    # twice the next width.
    for addr in ends:
        mem[addr] = len(mem)
    return " ".join(map(str, mem))


LANGUAGE = Language(
    "Decleq",
    "register_based.decleq",
    boolean=decleq,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
