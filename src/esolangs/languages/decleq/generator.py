"""Decleq Boolean program generator: a decision tree over a counter-indexed table.

Branches on each essential input (48/49 made 1/2 by decrement-and-branch in 47
steps; zero decrements to 0 and jumps, one falls through) until ``k`` levels
remain, ``2**k >= 2n``; a leaf subtracts low inputs' weights from a counter
(starting at ``2**k``, via ``2**k-1`` unrolled decrements) and prints that cell
of a ``2**k`` table (a full tree: Theta(T log T) target digits, from T-1
distinct absolute targets).  All n inputs are read; only essential ones pay the
normalization.

Size:
    O(T) cells, O(n) steps, shared subtrees: T three-character table cells
    plus at most T/(2n) O(n)-digit branches; n=10 random 1847: 9,165 chars.
"""

from esolangs.generation.helpers import (
    _ASCII_ONE,
    _ASCII_ZERO,
    _validate_truth_table,
    constant_span_test,
    essential_inputs,
    read_at,
    subtree_ids,
)
from esolangs.generation.wrap import wrap_grid
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language

__all__ = ["decleq"]


# Fixed low-memory layout. Cells 0-2 hold the entry instruction ``0 0 code``;
# every unconditional decrement targets cell 0, whose value never triggers a
# branch. Cells 3-14 hold two print gadgets, each a ``-2 K 0`` decrement pair
# followed by a ``0 0 END`` terminator; a leaf reaches a gadget by jumping to
# its address; constant subtrees share them (11110000 needs one branch).
# Cells 15-17 hold the print constants and the table-index
# counter; cells 18 onward hold the per-input read cells.
_OUT_ZERO = 3  # print-"0" gadget: ``-2 k48 0``
_HALT = 6  # halt: ``0 0 END`` of the first gadget, jumping one past memory
_OUT_ONE = 9  # print-"1" gadget: ``-2 k49 0``
_K48 = 15  # constant 48 (ASCII "0"), the print-"0" gadget's operand
_K49 = 16  # constant 49 (ASCII "1"), the print-"1" gadget's operand
_COUNTER = 17  # table-index counter, initialized to ``2**k``
_READ_BASE = 18  # input i is read at ``_READ_BASE + i``


def decleq(truth_table: str) -> str:
    """Return a Decleq program for a binary, MSB-first ``2**n`` truth table."""
    n = _validate_truth_table(truth_table)
    essential = essential_inputs(truth_table, n)
    # Routing only the essential inputs drops an ignored one's level and the
    # leaves it doubles.  Racing it against the full routing (which can keep a
    # constant half: 0100010011111111 is 1345 vs 1371) saved 0.1-0.2% on tables
    # with 3 or 4 essential inputs at n=7..8, 0% elsewhere; not raced.
    # All n inputs are read either way; only the essential ones pay the chain.
    reduced = read_at(truth_table, essential, n)
    return _CodeBuilder(reduced, n, essential).build()


class _CodeBuilder:
    """Emits a decleq program into a cell list for one truth table.

    Owns the cell list and every piece of state the recursive tree emission
    mutates: the routing plan, the dedup map for repeated subtrees, and the
    END operands backpatched once emission finishes.  A subtree repeating an
    earlier one at its level is not emitted again: a zero side branches to
    the copy, a one side jumps to it in one instruction, so the program is
    never longer than the plain tree.
    """

    def __init__(self, truth_table: str, n: int, routes: list[int]) -> None:
        self.truth_table = truth_table
        self.routes = routes
        self.m = len(routes)
        # The table depth: the fewest low inputs whose lookup pays for the
        # tree above it, ``2**k >= 2 n``, and never more inputs than there are.
        self.k = min(self.m, (2 * n - 1).bit_length())
        self.span = 2**self.k
        self.is_constant = constant_span_test(truth_table)
        self.read_cells = list(range(_READ_BASE, _READ_BASE + n))
        # The code starts on a multiple of three so wrap_grid's columns are
        # the operand columns; at most two pad cells.
        self.code = -(-(_READ_BASE + n) // 3) * 3
        self.mem: list[int] = []
        self.ends = [_HALT + 2, _HALT + 8]  # the two END operands, patched last
        # A constant prints at the root and never looks an id up.
        self.ids = subtree_ids(truth_table) if self.m else []
        self.done: dict[tuple[int, int], int] = {}

    def build(self) -> str:
        """Emit the full program and return it as a space-separated string."""
        self.mem = [0, 0, self.code, -2, _K48, 0, 0, 0, 0, -2, _K49, 0, 0, 0, 0]
        pad = self.code - _READ_BASE
        self.mem += [_ASCII_ZERO, _ASCII_ONE, self.span] + [0] * pad
        self._emit_preamble()
        self.node(0, 0)
        # Deriving END from the cell count keeps it out of wrap_grid's way: a
        # leaf's table-top operand is within ``2**k + 8`` of it, so the two
        # differ by at most one digit, and _cell_width drops an outlier only
        # at twice the next width.
        for addr in self.ends:
            self.mem[addr] = len(self.mem)
        return " ".join(map(str, self.mem))

    def emit(self, a: int, b: int, c: int) -> None:
        """Append one ``a b c`` instruction to the cell list."""
        self.mem.extend([a, b, c])

    def pc(self) -> int:
        """Return the address of the next emitted instruction."""
        return len(self.mem)

    def _emit_preamble(self) -> None:
        # A read falls through and these decrements never reach 0: target 0.
        for rc in self.read_cells:
            self.emit(-1, rc, 0)
        for i in self.routes:
            for _ in range(47):
                self.emit(self.read_cells[i], self.read_cells[i], 0)
        # Index: the low ``k`` inputs, each one taking its weight off the
        # counter. A zero (1) decrements to 0 and jumps the run; a one (2)
        # falls into it.
        for j in range(self.m - self.k, self.m):
            rc = self.read_cells[self.routes[j]]
            weight = 2 ** (self.m - 1 - j)
            self.emit(rc, rc, self.pc() + 3 * (weight + 1))
            for _ in range(weight):
                self.emit(_COUNTER, _COUNTER, 0)

    def leaf(self, row: int) -> None:
        """Print row ``counter`` of the table at ``row``, then halt.

        ``counter`` holds ``2**k - index``; the loop runs it down and takes
        one off the output's address operand per pass but the last, so the
        operand ends ``index`` above the table's base.
        """
        loop = self.pc()
        out = loop + 9
        self.emit(_COUNTER, _COUNTER, out)
        self.emit(out + 1, out + 1, 0)
        self.emit(0, 0, loop)
        self.emit(-2, out + 6 + self.span - 1, 0)
        self.emit(0, 0, _HALT)
        table_row = self.truth_table[row : row + self.span]
        self.mem.extend(_ASCII_ZERO + int(c) for c in table_row)

    def earlier(self, level: int, row: int) -> int | None:
        """Address of an equal non-constant subtree already emitted, if any."""
        if self.is_constant(row, row + 2 ** (self.m - level)):
            return None
        return self.done.get((level, self.ids[level][row >> (self.m - level)]))

    def node(self, level: int, row: int) -> None:
        """Emit the decision tree at ``level`` covering ``row``'s span."""
        width = 2 ** (self.m - level)
        if (copy := self.earlier(level, row)) is not None:
            self.emit(0, 0, copy)
            return
        if self.is_constant(row, row + width):
            self.emit(0, 0, _OUT_ONE if self.truth_table[row] == "1" else _OUT_ZERO)
            return
        self.done[level, self.ids[level][row >> (self.m - level)]] = self.pc()
        if level == self.m - self.k:
            self.leaf(row)
            return
        rc = self.read_cells[self.routes[level]]
        self.emit(rc, rc, 0)
        branch = self.pc() - 3
        self.node(level + 1, row + width // 2)
        target = self.earlier(level + 1, row)
        if target is None:
            target = self.pc()
            self.node(level + 1, row)
        self.mem[branch + 2] = target


LANGUAGE = Language(
    "Decleq",
    "decleq",
    category="register_based",
    boolean=decleq,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    wrap=wrap_grid,
)
