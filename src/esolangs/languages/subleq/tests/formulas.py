"""Subleq's emitted characters: the shorter of packed decoder and hoisted tree."""


def _tests(n: int) -> int:
    """Most distinct split residuals: differing halves at each depth."""
    return sum(
        min(2**d, 2 ** (2 ** (n - d)) - 2 ** (2 ** (n - d - 1))) for d in range(n)
    )


def _packed(n: int, _: str) -> int:
    """Packed decoder: 8n + 45 instructions, 18 named cells, ceil(T/n) chunks.

    An instruction cell is a code address (<= 3I), a named cell (<= 3I + 17)
    or -1, so at most w digits; a chunk is at most -(2^n - 1); the named cells
    are 22 characters, 2 more per extra digit of n.
    """
    code = 8 * n + 45
    chunks = -(-(1 << n) // n)
    width = len(str(3 * code + 17))
    cells = 3 * code + 18 + chunks
    return (
        cells - 1
        + width * 3 * code
        + 22 + 2 * (len(str(n)) - 1)
        + chunks * (1 + len(str((1 << n) - 1)))
    )  # fmt: skip


def _tree(n: int, _: str) -> int:
    """Hoisted tree: n reads of 3 instructions, K tests, at most K - 1 jumps, 2 leaves.

    A test is 3, 7 + input, address; a zero edge to a placed subtree is the
    jump 0 0 address (the first zero edge is never placed); a leaf is an out and
    a halt.  Every address is at most that of the instruction past the last.
    """
    k = _tests(n)
    base = 7 + n
    top = len(str(base + 3 * (n + 2 * k + 3 + 2 * n)))
    reads = sum(
        4 + 3 * len(str(7 + i)) + sum(len(str(base + 9 * i + d)) for d in (3, 6, 9))
        for i in range(n)
    )
    cells = base + 9 * n + 3 * (2 * k + 3)
    return (
        cells - 1
        + 10 + len(str(base)) + n  # entry jump, constants, the n bit cells
        + reads
        + k * (1 + len(str(6 + n)) + top)  # tests
        + (k - 1) * (2 + top)  # jumps
        + 2 * (7 + top)  # out and halt, two leaves
    )  # fmt: skip


def _chars(n: int, p: str) -> int:
    """The shorter build is at most either one."""
    return min(_packed(n, p), _tree(n, p))


FORMULAS = {"scaling": (_chars, False, tuple(range(2, 10)))}
