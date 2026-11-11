"""AddSubJump's emitted characters: P, the packed decoder; R, shared residuals."""

from tests.support.witness_tables import split_residuals as _tests

#: Packed decoder tail: (branch start, positive target, zero target) and the
#: plain jumps (index -> target), relative to the first of its 53 instructions.
_BRANCHES = ((0, 6, 19), (9, 0, 15), (26, 32, 42), (33, 39, 41), (43, 49, 51))
_JUMPS = {18: 0, 23: 24, 40: 26, 41: 42, 50: 24}
_TAIL = 53


def _packed(n: int, _: str = "") -> int:
    """Packed full-input decoder: 2n+57 words, seven names, T/n chunks.

    Count each operand's digits independently: one-digit hot cells, named
    addresses, five reusable jumps and the patched chunk-pointer operand.
    The data words hold bias 48(T-1), INDEX=0 and OUT=48. Chunk digit maxima
    are attained by the same tables as before; sharing choices are unchanged.
    """
    start = 2 * n + 4
    ins = start + _TAIL
    base = 4 * ins
    target = {t: t + 1 for t in range(_TAIL - 1)} | _JUMPS
    for b, pos, zero in _BRANCHES:
        target |= {b + 1: b + 3, b + 3: pos, b + 5: zero}
    reads = 7 * n + 3 + sum(len(str(4 * j)) for j in range(4, start + 1))
    jumps = sum(3 * (len(str(4 * (start + b + 1) + 2)) - 1) for b, _, _ in _BRANCHES)
    pointer = len(str(4 * (start + 20) + 1)) - 1
    named = {0: 1, 1: 3, 2: 4, 3: 10, 4: 6, 5: 4, 6: 4, 7: 1}
    operands = 160 + jumps + pointer
    operands += sum(
        count * (len(str(base + offset)) - 1) for offset, count in named.items()
    )
    targets = sum(len(str(4 * (start + u))) for u in target.values()) + 2
    chunks = -(-(1 << n) // n)
    last = (1 << n) - (chunks - 1) * n
    data = 13 + len(str(48 * ((1 << n) - 1))) + 5 + 2 * len(str(n))
    data += (chunks - 1) * len(str((1 << n) - 1)) + len(str((1 << last) - 1))
    return 4 * ins + 7 + chunks - 1 + reads + operands + targets + data


def _shared(n: int, _: str) -> int:
    """Shared residuals: 4 + 4n + 5K instructions, K distinct split residuals.

    Each residual is emitted once (a split is 4 instructions, a constant leaf
    1); every other reference to it is one jump, 1 + K - leaves of them.  The
    gotos and trampolines name cells 6 and 7 (one digit), so only a split's
    branch, the three code targets and the reads carry w-digit addresses.
    """
    k = _tests(n)
    ins = 4 + 4 * n + 5 * k
    names = n + 1
    cells = 4 * ins + names
    w = len(str(cells))
    digits = (
        5 + 12  # the entry jump and the two data words
        + n * (10 * w + 7)  # four instructions to read and scale a bit
        + k * (6 * w + 10)  # branch, goto and two trampolines
        + (k + 1) * max(6, w + 3)  # leaf prints and jumps to a seen residual
        + names  # the zero-valued bit cells
    )  # fmt: skip
    return cells - 1 + digits


# Past n = 5 the packed decoder is the worst; below, min(P, _shared) is only a
# upper bound; exactness below n=6 is not claimed.
def scaling_terms(n: int, p: str) -> dict[str, int]:
    """The shorter build is at most either one; from n = 6 R exceeds P."""
    return {"P": _packed(n, p), "R": _shared(n, p)}
