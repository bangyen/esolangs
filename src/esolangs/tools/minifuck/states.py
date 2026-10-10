"""Two-residual Minifuck diagrams, accumulated in output bit 7."""

from esolangs.tools.helpers import _validate_truth_table, subtree_ids
from esolangs.tools.minifuck.pool import _READS
from esolangs.tools.minifuck.sim import _MINIFUCK_INPUT, PAIR


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
    gates: list[list[int]] = []
    for depth in range(n):
        children = {node: state for state, node in enumerate(levels[depth + 1])}
        branches: dict[int, list[int]] = {}
        for place, node in enumerate(ids[depth]):
            if node not in branches:
                branches[node] = [
                    children[ids[depth + 1][2 * place + bit]] for bit in (0, 1)
                ]
        parents = levels[depth]
        gates.append(branches[parents[0]] + branches[parents[-1]])
    bias = levels[-1][0]
    return _emit(gates, bias)


def _emit(gates: list[list[int]], bias: int) -> str:
    """Keep the state in bit 7; a guarded setter clears it only when active."""
    lower = [0] * 7
    parts: list[str] = []
    orientations: list[str] = []

    def flip(cell: int) -> int:
        parts.append("[x")
        lower[cell] ^= 1
        if lower[cell]:
            return 0
        if cell < 6:
            lower[cell + 1] ^= 1
            return 0
        return 1

    def seek() -> None:
        carry = 0
        for cell in range(1, 7):
            carry ^= flip(cell)
        if carry:
            parts.append("[x<")

    def toggle() -> None:
        seek()
        parts.append("[x<" + "<" * 7)

    for values in gates:
        if sum(values) % 2 == 0:
            constant = values[0]
            left, right = values[0] ^ values[2], values[0] ^ values[1]
            if not left:
                seek()
                parts.append(_READS[1] + PAIR[1] + "<" * 8)
            seek()
            if right:
                parts.append(_MINIFUCK_INPUT + "<" * 8)
            else:
                # Two flips cross bit 7 without changing it; setters land at 9.
                parts.append("[x<[x[x" + _MINIFUCK_INPUT + "<" * 10)
            orientations.append("0")
            if constant:
                toggle()
        else:
            majority = int(sum(values) > 2)
            minority = values.index(1 - majority)
            seek()
            if minority < 2:
                parts.append("[x<")
            # The restoring read leaves bit 7 unchanged, with pointer 6 for a
            # one and 7 for a zero. The setter therefore computes a & !b.
            parts.append(_READS[1] + _MINIFUCK_INPUT + "<" * 9)
            orientations.append(str(minority & 1))
            if majority:
                toggle()

    carry = 0
    for cell in range(1, 7):
        carry ^= flip(cell)
        if lower[cell] != int(cell in (2, 3)):
            parts.append("<")
            carry ^= flip(cell)
    # Dot flips bit 7 before printing the byte.
    if carry ^ bias ^ 1:
        parts.append("[x<")
    parts.append(".")
    return "g" + "".join(orientations) + "g" + "".join(parts)


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
