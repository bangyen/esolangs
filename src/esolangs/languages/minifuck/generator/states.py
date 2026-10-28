"""Two-residual Minifuck diagrams, accumulated in output bit 7."""

from esolangs.generation.helpers import _validate_truth_table, subtree_ids
from esolangs.languages.minifuck.generator.pool import _READS
from esolangs.languages.minifuck.generator.sim import _MINIFUCK_INPUT, PAIR


def two_state(truth_table: str) -> str | None:
    """Emit an input-order diagram with at most two residuals per level."""
    n = _validate_truth_table(truth_table)
    ids = subtree_ids(truth_table)
    levels: list[list[int]] = []
    for level in ids:
        states: list[int] = []
        for node in level:
            if node not in states:
                states.append(node)
                if len(states) > 2:
                    return None
        levels.append(states)

    def gate(depth: int) -> list[int]:
        children = {node: state for state, node in enumerate(levels[depth + 1])}
        branches: dict[int, list[int]] = {}
        for place, node in enumerate(ids[depth]):
            if node not in branches:
                branches[node] = [
                    children[ids[depth + 1][2 * place + bit]] for bit in (0, 1)
                ]
        parents = levels[depth]
        return branches[parents[0]] + branches[parents[-1]]

    # A residual's label is its position in its level, so reversing a
    # two-residual level complements the level above and leaves every
    # minority position's parity alone.  Top down, each level gets the
    # labelling that spares the toggle after the level above: OR is AND's
    # chain with its states exchanged.
    for depth in range(n):
        values = gate(depth)
        spare = values[0] if sum(values) % 2 == 0 else int(sum(values) > 2)
        if spare and len(levels[depth + 1]) == 2:
            levels[depth + 1].reverse()
    return _emit([gate(depth) for depth in range(n)], levels[-1][0])


class _StateEmitter:
    """Emit one two-state diagram while mirroring the cells below bit 7.

    ``lower`` tracks cells 0..6 and ``parts`` collects the program text.
    Crossing a cell flips it; a flip that clears a lower cell carries into
    the cell above, and a carry out of cell 6 is the caller's to handle.
    """

    def __init__(self) -> None:
        self.lower = [0] * 7
        self.parts: list[str] = []

    def flip(self, cell: int) -> int:
        """Cross ``cell`` once; return the carry out of cell 6, else 0."""
        self.parts.append("[x")
        self.lower[cell] ^= 1
        if self.lower[cell]:
            return 0
        if cell < 6:
            self.lower[cell + 1] ^= 1
            return 0
        return 1

    def seek(self) -> None:
        """Cross cells 1..6, opening a run when the carry escapes cell 6."""
        carry = 0
        for cell in range(1, 7):
            carry ^= self.flip(cell)
        if carry:
            self.parts.append("[x<")

    def toggle(self) -> None:
        """Seek, then flip the state in bit 7 with a guarded setter."""
        self.seek()
        self.parts.append("[x<" + "<" * 7)


def _emit_even_level(emitter: _StateEmitter, values: list[int]) -> None:
    """Emit a level whose four branches XOR to a constant state update."""
    constant = values[0]
    left, right = values[0] ^ values[2], values[0] ^ values[1]
    if not left:
        emitter.seek()
        emitter.parts.append(_READS[1] + PAIR[1] + "<" * 8)
    emitter.seek()
    if right:
        emitter.parts.append(_MINIFUCK_INPUT + "<" * 8)
    else:
        # Two flips cross bit 7 without changing it; setters land at 9.
        emitter.parts.append("[x<[x[x" + _MINIFUCK_INPUT + "<" * 10)
    if constant:
        emitter.toggle()


def _emit_odd_level(emitter: _StateEmitter, values: list[int]) -> None:
    """Emit a level whose update is the minority branch's guarded setter.

    A minority at input 0 spells the setter then ``[``; at input 1 it is
    read through ``[<[x<`` first, so no table swaps the setter pair.  A
    minority under the last residual first flips bit 7 (``[x<``).  Each form
    equals the old restoring read plus setter on every tape a level can meet
    (scratch cells 8-11 and cell 6 free), checked over all of them.
    """
    majority = int(sum(values) > 2)
    minority = values.index(1 - majority)
    emitter.seek()
    form = "[<[x<" + _MINIFUCK_INPUT if minority % 2 else _MINIFUCK_INPUT + "["
    emitter.parts.append("[x<" * (minority >= 2) + form + "<" * 9)
    if majority:
        emitter.toggle()


def _finish_diagram(emitter: _StateEmitter, bias: int) -> None:
    """Walk the lower cells into the print frame the final dot expects."""
    carry = 0
    for cell in range(1, 7):
        carry ^= emitter.flip(cell)
        if emitter.lower[cell] != int(cell in (2, 3)):
            emitter.parts.append("<")
            carry ^= emitter.flip(cell)
    # Dot flips bit 7 before printing the byte.
    if carry ^ bias ^ 1:
        emitter.parts.append("[x<")


def _emit_unframed(gates: list[list[int]], bias: int) -> str:
    """Return the diagram's walk text, without its header or final dot."""
    emitter = _StateEmitter()
    for values in gates:
        if sum(values) % 2 == 0:
            _emit_even_level(emitter, values)
        else:
            _emit_odd_level(emitter, values)
    _finish_diagram(emitter, bias)
    return "".join(emitter.parts)


def _emit(gates: list[list[int]], bias: int) -> str:
    """Keep the state in bit 7; a guarded setter clears it only when active."""
    return _emit_unframed(gates, bias) + "."
