"""Decleq Boolean program generator: a shared decision tree over the inputs.

Branches on each essential input (48/49 made 1/2 by 47 passes of a loop that
decrements every essential cell once per pass; zero decrements to 0 and jumps,
one falls through) down to single
entries. A zero edge to a constant goes straight to its print gadget; a one
edge falls into a jump. Equal subtrees are emitted once, which collapses
the low levels (only 4 distinct 2-row subtrees exist, 16 at the next level).
All n inputs are read; only essential ones are normalized. Strict majority
and fixed thresholds 3..6 give each shared node a fall-through parent
([ablations.fallthrough_owner_families_20261102]); other tables keep DFS order.

Size:
    O(T) cells, O(n) steps: one three-cell branch per distinct subtree,
    at most one three-cell jump per node; n=10 random 1847: 3,496 chars.
    Constants: n+2 commands; n=8: 93 chars.
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
from esolangs.languages.decleq.proof_formulas import workspace
from esolangs.registry._certification import CertificationSpec
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

__all__ = ["decleq"]


# Fixed low-memory layout. Cells 0-2 hold the entry instruction ``0 0 code``;
# every unconditional decrement targets cell 0, whose value never triggers a
# branch. Cells 3-14 hold two print gadgets, each a ``-2 K next`` decrement pair
# followed by a ``0 0 END`` terminator; a constant subtree reaches a gadget by
# jumping to its address (11110000 needs one branch).
# Cells 15-16 hold the print constants; cells 17 onward hold the per-input
# read cells.
_OUT_ZERO = 3  # print-"0" gadget: ``-2 k48 6``
_HALT = 6  # halt: ``0 0 END`` of the first gadget, jumping one past memory
_OUT_ONE = 9  # print-"1" gadget: ``-2 k49 12``
_K48 = 15  # constant 48 (ASCII "0"), the print-"0" gadget's operand
_K49 = 16  # constant 49 (ASCII "1"), the print-"1" gadget's operand
_READ_BASE = 17  # input i is read at ``_READ_BASE + i``


def decleq(truth_table: str) -> str:
    """Return a Decleq program for a binary, MSB-first ``2**n`` truth table."""
    n = _validate_truth_table(truth_table)
    if truth_table == truth_table[0] * len(truth_table):
        digit, scratch, zero, end = 3 * n + 6, 3 * n + 7, 3 * n + 8, 3 * n + 9
        cells = [v for i in range(n) for v in (-1, scratch, 3 * i + 3)]
        # Full triples keep I/O fall-through and jump-to-c readings identical.
        cells += [-2, digit, 3 * n + 3, zero, zero, end, 48 + int(truth_table[0]), 0, 0]
        return " ".join(map(str, cells))
    essential = essential_inputs(truth_table, n)
    # Routing only essential inputs drops ignored levels. All inputs are read;
    # only essential ones pay normalization. The historical full-routing race
    # remains rejected ([ablations.routing_race_figures]).
    reduced = read_at(truth_table, essential, n)
    builder = _OwnerBuilder if _owner_family(truth_table, n) else _CodeBuilder
    return builder(reduced, n, essential).build()


def _owner_family(table: str, n: int) -> bool:
    """Recognize strict majority and fixed thresholds 3..6, or their negations."""
    profile: list[str | None] = [None] * (n + 1)
    for row, bit in enumerate(table):
        weight = row.bit_count()
        if profile[weight] not in (None, bit):
            return False
        profile[weight] = bit
    threshold = next((i for i, bit in enumerate(profile) if bit != profile[0]), n + 1)
    return (
        threshold <= n
        and (3 <= threshold <= 6 or threshold == n // 2 + 1)
        and all(bit == profile[-1] for bit in profile[threshold:])
    )


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
        self.counter = _READ_BASE + n  # the pass counter, after the read cells
        self.code = -(-(self.counter + 1) // 3) * 3
        self.mem: list[int] = []
        self.ends = [_HALT + 2, _HALT + 8]  # the two END operands, patched last
        # A constant prints at the root and never looks an id up.
        self.ids = subtree_ids(truth_table) if self.m else []
        self.done: dict[tuple[int, int], int] = {}

    def build(self) -> str:
        """Emit the full program and return it as a space-separated string."""
        self.mem = [0, 0, self.code, -2, _K48, 6, 0, 0, 0, -2, _K49, 12, 0, 0, 0]
        pad = self.code - self.counter - 1
        self.mem += [_ASCII_ZERO, _ASCII_ONE] + [0] * (self.counter - _READ_BASE)
        self.mem += [47] + [0] * pad
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
        # These decrements never reach 0: target 0.  I/O targets the next
        # instruction, so SUBBIG's jump-to-c reading runs the same program.
        for rc in self.read_cells:
            self.emit(-1, rc, self.pc() + 3)
        if not self.routes:
            return
        # 47 passes over the essential cells (48/49 -> 1/2), counted down in a
        # cell of 47 that exits the loop on reaching 0.
        top = self.pc()
        for i in self.routes:
            self.emit(self.read_cells[i], self.read_cells[i], 0)
        self.emit(self.counter, self.counter, self.pc() + 6)
        self.emit(0, 0, top)

    def earlier(self, level: int, row: int) -> int | None:
        """Return a constant gadget or an equal subtree already emitted, if any."""
        if self.is_constant(row, row + 2 ** (self.m - level)):
            # [ablations.constant_zero_side_target_20261102]: the skipped
            # jump only decremented negative cell0. Gadgets need that sign,
            # fixed ASCII constants and all reads done.
            return _OUT_ONE if self.truth_table[row] == "1" else _OUT_ZERO
        return self.done.get((level, self.ids[level][row >> (self.m - level)]))

    def node(self, level: int, row: int) -> None:
        """Emit the decision tree at ``level`` covering ``row``'s span."""
        width = 2 ** (self.m - level)
        if (copy := self.earlier(level, row)) is not None:
            self.emit(0, 0, copy)
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


type _Node = tuple[int, int]
type _Target = _Node | int


class _OwnerBuilder(_CodeBuilder):
    """Emit chains owned by one-edge parents for the admitted named families."""

    def node(self, level: int, row: int) -> None:
        """Give each nonconstant node one fall-through parent, if it has one."""
        assert (level, row) == (0, 0)
        graph: dict[_Node, tuple[_Target, _Target]] = {}
        order: list[_Node] = []
        one_children: set[_Node] = set()

        def target(level: int, row: int) -> _Target:
            width = 1 << (self.m - level)
            if self.is_constant(row, row + width):
                return _OUT_ONE if self.truth_table[row] == "1" else _OUT_ZERO
            key = (level, self.ids[level][row >> (self.m - level)])
            if key in graph:
                return key
            order.append(key)
            one = target(level + 1, row + width // 2)
            zero = target(level + 1, row)
            graph[key] = zero, one
            if isinstance(one, tuple):
                one_children.add(one)
            return key

        target(0, 0)
        addresses: dict[_Node, int] = {}
        fixups: list[tuple[int, _Node]] = []
        # Decrementing the required count is injective: each nonconstant
        # one-child has one parent, so these chains are disjoint.
        for chain_start in (key for key in order if key not in one_children):
            key = chain_start
            while True:
                addresses[key] = self.pc()
                zero, one = graph[key]
                rc = self.read_cells[self.routes[key[0]]]
                branch = self.pc()
                self.emit(rc, rc, zero if isinstance(zero, int) else 0)
                if isinstance(zero, tuple):
                    fixups.append((branch + 2, zero))
                if isinstance(one, int):
                    self.emit(0, 0, one)
                    break
                key = one
        for address, key in fixups:
            self.mem[address] = addresses[key]


LANGUAGE = Language(
    "Decleq",
    RuntimeSpec("decleq", category="register_based"),
    boolean=decleq,
    contract=BooleanContract(
        input_shape="char_stream",
    ),
    wrap=wrap_grid,
    certification=CertificationSpec(proof_workspace=(workspace, True, (1, 2, 3, 4))),
)
