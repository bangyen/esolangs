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

    gates = [gate(depth) for depth in range(n)]
    # The input-embed convention needs every flip's span to be the same
    # content pair.  Only the setter run changes with a bit, and a level whose
    # minority sits at an odd branch position takes the reversed pair, so the
    # spans agree exactly when every orientation does.  Mixed orientations are
    # the positional decoder's job.  An even level has no minority and takes
    # either pair (its branches swap under the reversed one), so it follows
    # the odd levels: AND is OR with every input negated, not a mixed chain.
    odd = {
        o
        for values, o in zip(gates, _orientations(gates), strict=True)
        if sum(values) % 2
    }
    if len(odd) > 1:
        return None
    even = odd.pop() if odd else "0"

    def shaped(depth: int) -> list[int]:
        values = gate(depth)
        if even == "1" and sum(values) % 2 == 0:
            values = [values[1], values[0], values[3], values[2]]
        return values

    # A residual's label is its position in its level, so reversing a
    # two-residual level complements the level above (the toggle that
    # follows a majority-one or constant-one level) and leaves every
    # orientation alone.  Top down, each level above gets the labelling
    # that spares its toggle: OR is AND's chain with its states exchanged.
    for depth in range(n):
        values = shaped(depth)
        spare = values[0] if sum(values) % 2 == 0 else int(sum(values) > 2)
        if spare and len(levels[depth + 1]) == 2:
            levels[depth + 1].reverse()
    gates = [shaped(depth) for depth in range(n)]
    return _emit(gates, levels[-1][0], even)


def _orientations(gates: list[list[int]]) -> list[str]:
    """Return the setter orientation each level's guarded update carries."""
    out: list[str] = []
    for values in gates:
        if sum(values) % 2 == 0:
            out.append("0")
        else:
            out.append(str(values.index(1 - int(sum(values) > 2)) & 1))
    return out


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
    """Emit a level whose update is the minority branch's guarded setter."""
    majority = int(sum(values) > 2)
    minority = values.index(1 - majority)
    emitter.seek()
    if minority < 2:
        emitter.parts.append("[x<")
    # The restoring read leaves bit 7 unchanged, with pointer 6 for a
    # one and 7 for a zero. The setter therefore computes a & !b.
    emitter.parts.append(_READS[1] + _MINIFUCK_INPUT + "<" * 9)
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


def _emit(gates: list[list[int]], bias: int, even: str = "0") -> str:
    """Keep the state in bit 7; a guarded setter clears it only when active.

    ``even`` is the orientation an even level carries (its branches already
    swapped when it is ``"1"``).
    """
    walk = _emit_unframed(gates, bias)
    header = "".join(
        o if sum(values) % 2 else even
        for values, o in zip(gates, _orientations(gates), strict=True)
    )
    return "g" + header + "g" + walk + "."


def state_setters(template: str, n: int) -> tuple[tuple[str, str], ...] | None:
    """Decode the inert orientation header, including after wrapping."""
    if not template.startswith("g"):
        return None
    header = []
    for char in template:
        if not char.isspace():
            header.append(char)
        if len(header) == n + 2:
            break
    if (
        len(header) != n + 2
        or header[-1] != "g"
        or any(char not in "01" for char in header[1:-1])
    ):
        return None
    return tuple(PAIR[::-1] if char == "1" else PAIR for char in header[1:-1])
