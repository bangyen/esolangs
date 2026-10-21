"""Decleq Boolean program generator: a shared decision tree over the inputs.

Branches on each essential input (48/49 made 1/2 by decrement-and-branch in 47
steps; zero decrements to 0 and jumps, one falls through) down to single
entries.  A width-1 span is constant, so the bottom of the tree is one jump to
a shared print gadget, and an equal subtree is emitted once, which collapses
the low levels (only 4 distinct 2-row subtrees exist, 16 at the next level).
All n inputs are read; only essential ones pay the normalization.

Size:
    O(T) cells, O(n) steps: one three-cell branch per distinct subtree,
    one three-cell jump per entry reached; n=10 random 1847: 7,587 chars.
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
from esolangs.languages.decleq.proof_formulas import execution, workspace
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language

__all__ = ["decleq"]


# Fixed low-memory layout. Cells 0-2 hold the entry instruction ``0 0 code``;
# every unconditional decrement targets cell 0, whose value never triggers a
# branch. Cells 3-14 hold two print gadgets, each a ``-2 K 0`` decrement pair
# followed by a ``0 0 END`` terminator; a constant subtree reaches a gadget by
# jumping to its address (11110000 needs one branch).
# Cells 15-16 hold the print constants; cells 17 onward hold the per-input
# read cells.
_OUT_ZERO = 3  # print-"0" gadget: ``-2 k48 0``
_HALT = 6  # halt: ``0 0 END`` of the first gadget, jumping one past memory
_OUT_ONE = 9  # print-"1" gadget: ``-2 k49 0``
_K48 = 15  # constant 48 (ASCII "0"), the print-"0" gadget's operand
_K49 = 16  # constant 49 (ASCII "1"), the print-"1" gadget's operand
_READ_BASE = 17  # input i is read at ``_READ_BASE + i``


def decleq(truth_table: str) -> str:
    """Return a Decleq program for a binary, MSB-first ``2**n`` truth table."""
    n = _validate_truth_table(truth_table)
    essential = essential_inputs(truth_table, n)
    # Routing only the essential inputs drops an ignored one's level and the
    # subtree it doubles.  Racing it against the full routing (which can keep a
    # constant half: 0100010011111111 is 1763 vs 1371) saved 0.1-0.2% on tables
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
        self.mem += [_ASCII_ZERO, _ASCII_ONE] + [0] * pad
        self._emit_preamble()
        self.node(0, 0)
        # Deriving END from the cell count keeps it out of wrap_grid's way:
        # every other operand is an address below it, so END is the widest
        # operand in the program, and _cell_width drops an outlier only at
        # twice the next width.
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
    proof_execution=(execution, False, (3, 6)),
    proof_workspace=(workspace, False, (3, 4)),
)
