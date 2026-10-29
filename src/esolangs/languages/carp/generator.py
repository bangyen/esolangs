"""CARP Boolean program generator: a shared decision diagram over the inputs.

Each input is read in order: an essential one into its own register (0 or 1),
an ignored one into the next essential register (overwritten) or, past the
last, into r15 (then cleared).  ``DEC rX L`` branches: zero falls through to
the 0-subtree, one decrements and jumps to line ``L``.  CARP has no
unconditional jump, so a register held at 15 (``INC r15 L`` at 15 always
jumps) supplies one for shared and constant subtrees.  Constants end in a
shared print gadget.

Size:
    O(T) lines: at most 2T + n + 20, one ``DEC`` per distinct non-constant
    subtree and at most one jump each, plus a 15-line constant and two
    gadgets; n=4 parity: 359 chars, n=8 parity: 519 chars.

Raises:
    GeneratorCapError: more than fourteen inputs (registers r1..r14).
"""

from __future__ import annotations

from esolangs.exceptions import GeneratorCapError
from esolangs.generation.helpers import (
    _validate_truth_table,
    constant_span_test,
    essential_inputs,
    read_at,
    subtree_ids,
)
from esolangs.registry._language import Language
from esolangs.runtime.source_hints import with_hint

MAX_INPUTS = 14
_K = 15  # register held at 15: ``INC r15 L`` is a jump to L


def carp(truth_table: str) -> str:
    """Build a CARP program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    if n > MAX_INPUTS:
        raise with_hint(
            GeneratorCapError("CARP has 15 registers: at most fourteen inputs"),
            "r15 holds the jump constant; inputs take r1..r14",
        )
    essential = essential_inputs(truth_table, n)
    if not essential:
        # Every input is still read, into a register the answer then clears.
        reads = ["INP r1 0"] * n + ["CLR r1 0"]
        if truth_table[0] == "1":
            reads.append("INC r1 0")
        return "\n".join([*reads, "OUT r1 0"])
    return _Builder(read_at(truth_table, essential, n), essential, n).build()


class _Builder:
    """Emits the diagram as a list of ``[op, register, line]`` instructions."""

    def __init__(self, table: str, essential: list[int], n: int) -> None:
        self.table = table
        self.m = len(essential)
        self.is_constant = constant_span_test(table)
        self.ids = subtree_ids(table)
        self.essential = essential
        self.n = n
        self.code: list[list[object]] = []
        self.done: dict[tuple[int, int], int] = {}
        # Lines whose operand is a gadget, patched once the gadgets are placed.
        self.to_one: list[int] = []
        self.to_zero: list[int] = []

    def line(self) -> int:
        """Return the 1-based line of the next instruction."""
        return len(self.code) + 1

    def emit(self, op: str, reg: int, line: int) -> int:
        self.code.append([op, reg, line])
        return len(self.code) - 1

    def build(self) -> str:
        # Input i goes to the register of the first essential input at or
        # after it; those past the last essential go to r15, then cleared.
        slot = 0
        for i in range(self.n):
            self.emit("INP", slot + 1 if slot < self.m else _K, 0)
            if slot < self.m and i == self.essential[slot]:
                slot += 1
        if self.essential[-1] < self.n - 1:
            self.emit("CLR", _K, 0)
        for _ in range(15):
            self.emit("INC", _K, 0)
        self.node(0, 0)
        one = self.line()
        for op, reg in (("CLR", _K), ("INC", _K), ("OUT", _K), ("DEC", _K)):
            self.emit(op, reg, 0)
        zero = self.line()
        self.emit("CLR", _K, 0)
        self.emit("OUT", _K, 0)
        for at in self.to_one:
            self.code[at][2] = one
        for at in self.to_zero:
            self.code[at][2] = zero
        return "\n".join(f"{op} r{reg} {line}" for op, reg, line in self.code)

    def reference(self, level: int, row: int, at: int, *, jump: bool) -> bool:
        """Point instruction ``at`` (or a new jump) at a known subtree.

        Returns whether the span was known; otherwise nothing is emitted.
        """
        width = 2 ** (self.m - level)
        if self.is_constant(row, row + width):
            where = self.to_one if self.table[row] == "1" else self.to_zero
            line = 0
        else:
            line = self.done.get((level, self.ids[level][row >> (self.m - level)]), -1)
            if line < 0:
                return False
            where = None
        if jump:
            at = self.emit("INC", _K, line)
        if where is not None:
            where.append(at)
        else:
            self.code[at][2] = line
        return True

    def node(self, level: int, row: int) -> None:
        """Emit the subtree of ``level`` covering ``row``'s span, here."""
        if self.reference(level, row, 0, jump=True):
            return
        self.done[level, self.ids[level][row >> (self.m - level)]] = self.line()
        branch = self.emit("DEC", level + 1, 0)
        half = 2 ** (self.m - level) // 2
        self.node(level + 1, row)
        if not self.reference(level + 1, row + half, branch, jump=False):
            self.code[branch][2] = self.line()
            self.node(level + 1, row + half)


LANGUAGE = Language(
    "CARP",
    "carp",
    category="register_based",
    boolean=carp,
    generator_max_inputs=MAX_INPUTS,
    empty_program="a program needs at least one instruction",
    no_wrap="a line break ends an instruction",
)
