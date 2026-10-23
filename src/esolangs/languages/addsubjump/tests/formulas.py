"""AddSubJump's emitted characters: the shorter of packed and shared residuals."""


def _tests(n: int) -> int:
    """Most distinct split residuals: differing halves at each depth."""
    return sum(
        min(2**d, 2 ** (2 ** (n - d)) - 2 ** (2 ** (n - d - 1))) for d in range(n)
    )


def _packed(n: int, _: str) -> int:
    """Packed decoder: 5n + 53 instructions of 4 cells, 14 named cells, T/n chunks.

    An instruction cell is a code address (<= 4I) or a named cell (<= 4I + 13),
    so at most w digits; the named cells are 16 characters, 2 more per extra
    digit of n; a chunk is at most 2^n - 1; n + 2 signs (a -1 a read, -1 and -8).
    """
    code = 5 * n + 53
    chunks = -(-(1 << n) // n)
    width = len(str(4 * code + 13))
    return (
        4 * code + 14 + chunks - 1
        + width * 4 * code
        + n + 2
        + 16 + 2 * (len(str(n)) - 1)
        + chunks * len(str((1 << n) - 1))
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


def _chars(n: int, p: str) -> int:
    """The shorter build is at most either one."""
    return min(_packed(n, p), _shared(n, p))


FORMULAS = {"scaling": (_chars, False, tuple(range(2, 10)))}
