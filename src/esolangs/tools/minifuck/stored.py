"""Shared residuals stored once on a scratch-separated binary tape."""

from esolangs.tools.helpers import (
    _validate_truth_table,
    essential_inputs,
    read_at,
    subtree_ids,
)
from esolangs.tools.minifuck.pool import _READS
from esolangs.tools.minifuck.sim import _MINIFUCK_INPUT, PAIR
from esolangs.tools.minifuck.states import _emit

# Two double flips preserve the crossed cell and cancel both neighbor carries.
_RIGHT = "[x<[x<[x<[x"
_FIRST = 12
_STRIDE = 5


class _Plan:
    """Price constant words and repetitions before allocating their text."""

    def __init__(self) -> None:
        self.words: list[tuple[str, int]] = []
        self.size = 0

    def write(self, word: str, count: int = 1) -> None:
        if count < 0:
            raise ValueError("negative repetition")
        if count:
            self.words.append((word, count))
            self.size += len(word) * count

    def shift(self, distance: int) -> None:
        self.write(_RIGHT if distance >= 0 else "<", abs(distance))

    def seek(self, cell: int) -> None:
        self.shift(cell)

    def invert(self, cell: int) -> None:
        self.seek(cell - 1)
        self.write("[x<")
        self.write("<", cell)

    def copy(self, control: int, target: int) -> None:
        """XOR the control into the target, preserving the control."""
        if control == target:
            raise ValueError("control and target must be distinct")
        self.seek(control - 1)
        self.write(_READS[1])
        self.shift(target - control)
        self.write(PAIR[1])
        self.write("<", target + 2)

    def conjunction(self, left: int, right: int, target: int) -> None:
        """XOR the AND into the target, preserving both controls."""
        if target in (left, right):
            raise ValueError("controls and target must be distinct")
        if left == right:
            self.copy(left, target)
            return
        # Clear left+1: an inactive right must read a known-zero guard.
        # Three scratch cells contain every carry; the next logical cell is +5.
        self.seek(left)
        self.write(_READS[1] + PAIR[1])
        self.write("<", left + 3)
        self.seek(right - 1)
        self.write(_READS[1])
        self.shift(left - right)
        self.write(_READS[1])
        # Offsets are 0 for two ones, 1 for left=0/right=1, 2 for right=0.
        self.shift(target - left)
        self.write(PAIR[1])
        self.write("<", target + 3)

    def render(self, budget: int | None) -> str | None:
        if budget is not None and self.size > budget:
            return None
        return "".join(word * count for word, count in self.words)


def plan(truth_table: str) -> _Plan:
    """Plan every residual once; exact text pricing takes O(T) space and work."""
    n = _validate_truth_table(truth_table)
    kept = essential_inputs(truth_table, n)
    table = read_at(truth_table, kept, n)
    result = _Plan()
    # The empty byte emitter leaves ASCII 0 immediately before its final dot.
    result.write(_emit([], 1)[2:-1] + "<" * 8)
    inputs = {original: _FIRST + _STRIDE * i for i, original in enumerate(kept)}
    for original in range(n):
        cell = inputs.get(original, 9)
        result.seek(cell - 1)
        result.write(_MINIFUCK_INPUT)
        result.write("<", cell + 1)

    refs: dict[tuple[int, int], int] = {}
    allocated = len(kept)

    def resolve(depth: int, node: int) -> int:
        return node if node < 2 else refs[depth, node]

    if kept:
        ids = subtree_ids(table)
        for depth in range(len(kept) - 1, -1, -1):
            selector = inputs[kept[depth]]
            for place, node in enumerate(ids[depth]):
                key = (depth, node)
                if node < 2 or key in refs:
                    continue
                zero = resolve(depth + 1, ids[depth + 1][2 * place])
                one = resolve(depth + 1, ids[depth + 1][2 * place + 1])
                if zero == one:
                    refs[key] = zero
                    continue
                if (zero, one) == (0, 1):
                    refs[key] = selector
                    continue
                target = _FIRST + _STRIDE * allocated
                allocated += 1
                refs[key] = target
                if (zero, one) == (1, 0):
                    result.copy(selector, target)
                    result.invert(target)
                elif zero == 0:
                    result.conjunction(selector, one, target)
                elif one == 0:
                    result.invert(selector)
                    result.conjunction(selector, zero, target)
                    result.invert(selector)
                elif zero == 1:
                    result.invert(target)
                    result.copy(selector, target)
                    result.conjunction(selector, one, target)
                elif one == 1:
                    result.copy(selector, target)
                    result.invert(selector)
                    result.conjunction(selector, zero, target)
                    result.invert(selector)
                else:
                    # Disjoint guarded terms combine by XOR; no OR gadget needed.
                    result.invert(selector)
                    result.conjunction(selector, zero, target)
                    result.invert(selector)
                    result.conjunction(selector, one, target)
        root = resolve(0, ids[0][0])
    else:
        root = int(table)
    if root < 2:
        if root:
            result.invert(7)
    else:
        result.copy(root, 7)
    result.seek(6)
    result.write("[x<.")
    return result


def stored(truth_table: str, budget: int) -> str | None:
    """Emit shared residuals only within the caller's linear-size text budget."""
    return plan(truth_table).render(budget)
