"""AddSubJump's emitted characters: P, the packed decoder; R, shared residuals."""


def _tests(n: int) -> int:
    """Most distinct split residuals: differing halves at each depth."""
    return sum(
        min(2**d, 2 ** (2 ** (n - d)) - 2 ** (2 ** (n - d - 1))) for d in range(n)
    )


#: Packed decoder tail: (branch start, positive target, zero target) and the
#: plain jumps (index -> target), relative to the first of its 53 instructions.
_BRANCHES = ((0, 6, 19), (9, 0, 15), (26, 32, 42), (33, 39, 41), (43, 49, 51))
_JUMPS = {18: 0, 23: 24, 40: 26, 41: 42, 50: 24}
_TAIL = 53


def _packed(n: int, _: str = "") -> int:
    """Packed decoder, exact: 5n + 53 instructions, 14 named cells, T/n chunks.

    Spaces: one fewer than the cells.  Digits: every named operand is 4I + k
    (I instructions, k < 14) so one width w; -1 (n + 1 times) and -8 are two
    characters; each ``c`` is 4 times its target (reads fall through, the
    tail follows ``_BRANCHES`` and ``_JUMPS``); each branch names its own
    ``c`` + 2 three times; the chunk pointer is 4(tail + 20) + 1.  Named
    values total 14 + 2 digits of n (N and COUNT); a chunk is at most
    2^n - 1, the last one 2^(T - n(C - 1)) - 1.  Exact for n <= 36, where
    4I + 14 keeps the width of 4I.  Equals the generator's all-ones build,
    the widest chunks, at n = 2..14.
    """
    start = 5 * n
    ins = start + _TAIL
    width = len(str(4 * ins + 14))
    target = {t: t + 1 for t in range(_TAIL - 1)} | _JUMPS
    for b, pos, zero in _BRANCHES:
        target |= {b + 1: b + 3, b + 3: pos, b + 5: zero}
    code = sum(len(str(4 * j)) for j in range(1, start + 1))
    code += sum(len(str(4 * (start + u))) for u in target.values())
    code += sum(3 * len(str(4 * (start + b + 1) + 2)) for b, _p, _z in _BRANCHES)
    code += len(str(4 * (start + 20) + 1))
    chunks = -(-(1 << n) // n)
    last = (1 << n) - (chunks - 1) * n
    return (
        4 * ins + 14 + chunks - 1
        + width * (3 * ins - n - 17) + 2 * (n + 1) + 2 + code
        + 14 + 2 * len(str(n))
        + (chunks - 1) * len(str((1 << n) - 1)) + len(str((1 << last) - 1))
    )  # fmt: skip


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
# bound (never reached), so those arities are not listed.
def _chars(n: int, p: str) -> int:
    """The shorter build is at most either one; from n = 6 R exceeds P."""
    return min(_packed(n, p), _shared(n, p))


FORMULAS = {"scaling": (_chars, frozenset(range(6, 10)), tuple(range(2, 10)))}
