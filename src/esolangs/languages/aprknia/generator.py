"""Aprknia Boolean program generator: a decision tree of positive loops.

Each node reads an ASCII bit and keeps its parity above the quotient 24.
Its one arm leaves two zeros; popping the upper zero exposes zero after
that arm or quotient 24 when it was skipped. The second loop runs only
on the zero arm. A child known to end on zero needs no extra zero reset.
Leaves print 0 or 1 as an integer with selector 2.
Lower stack garbage is retained: each piece supplies its own operands.

Size:
    O(T) in the tree's nodes; n=4 parity: 305 chars.
    Root constants: 4n + 5/6 chars and commands.

Decisions:
    Leaves print with selector 2, not 1: the integer 0 or 1 costs at most
    the 9-command build, against building 48 or 49 from ones for a byte.
    Opposite bottom leaves print the final bit directly, inverting for 10.
    Only the final read may print: ignored suffix inputs must come first.
    The quotient guard saves 16.88/17.04% at n=7/8, with expected random limit
    17.0585%; its extra retained sign bit raises the workspace coefficient
    from 32 to 34 ([ablations.garbage_guard_20261103]).
    Constant spans and ignored inputs read with ``11*,``: the 0 that
    ``11*`` leaves on top is the selector, so no parity is needed.
"""

from functools import cache

from esolangs.generation.helpers import _validate_truth_table, subtree_ids

#: ``11*`` pushes 2, 0, 1, 1, 0.  Its top 0 is a read selector (``_SKIP``);
#: ``!!!`` leaves 2, 0 so ``~*`` after the read is byte mod 2, the bit.
#: ``_EXIT`` provides a zero loop exit only when its child has no known zero.
#: One-arm ``11*~*`` leaves two zeros; popping one selects the zero arm.
_SKIP = "11*,"
_READ = "11*!!!,~*"
_EXIT = "11*"
_LEAF = {"0": "11*!!!~,", "1": "11*~*!!!,"}


def aprknia(truth_table: str) -> str:
    """Build an Aprknia program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    if truth_table.count(truth_table[0]) == len(truth_table):
        # The final read leaves 2, 0, 1, 1 below its byte: reuse the selector.
        return _SKIP * n + ("!!!~," if truth_table[0] == "0" else "!!~!~,")
    ids = subtree_ids(truth_table)
    pieces: list[str] = []

    @cache
    def zero_exit(depth: int, block: int) -> bool:
        key = ids[depth][block]
        if key < 2:
            return key == 0
        if depth == n - 1:
            return False
        zero, one = ids[depth + 1][2 * block : 2 * block + 2]
        return zero_exit(depth + 1, 2 * block) if zero == one else True

    def emit(depth: int, block: int) -> None:
        key = ids[depth][block]
        if key < 2:
            pieces.append(_SKIP * (n - depth) + _LEAF[str(key)])
        elif depth == n - 1:
            # Only the final read may print; ignored suffixes come first.
            invert = "1~*!!!" if truth_table[2 * block] == "1" else ""
            pieces.append(_READ + invert + "11*!!!!,")
        elif ids[depth + 1][2 * block] == ids[depth + 1][2 * block + 1]:
            pieces.append(_SKIP)
            emit(depth + 1, 2 * block)
        else:
            pieces.append(_READ + "[")
            emit(depth + 1, 2 * block + 1)
            pieces.append("11*~*]![")
            emit(depth + 1, 2 * block)
            # All fragments append above their entry stack. Ancestor tails
            # start fresh values, so the reset's lower garbage is never read.
            pieces.append("]" if zero_exit(depth + 1, 2 * block) else _EXIT + "]")

    emit(0, 0)
    return "".join(pieces)
