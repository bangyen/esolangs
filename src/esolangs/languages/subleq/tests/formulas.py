"""Subleq's emitted characters: the shorter of packed decoder and hoisted tree."""


def _tests(n: int) -> int:
    """Most distinct split residuals: differing halves at each depth."""
    return sum(
        min(2**d, 2 ** (2 ** (n - d)) - 2 ** (2 ** (n - d - 1))) for d in range(n)
    )


#: Decode-part code addresses past the 8n read instructions: 44 branch targets
#: and the self-modified load (instruction 14).
_CODE = (
    13, 2, 3, 4, 5, 7, 0, 8, 9, 10, 11, 12, 0, 14, 15, 16, 17, 18, 19, 20, 21, 22,
    32, 24, 25, 30, 27, 28, 29, 22, 31, 32, 33, 40, 35, 36, 37, 38, 39, 20, 41, 42,
    43, 44, 14,
)  # fmt: skip


def _packed(n: int, _: str) -> int:
    """Packed decoder, exact: 8n + 45 instructions, 18 named cells, ceil(T/n) chunks.

    Reads are 8 instructions each, the decode 45; operands are 15n + 88 named
    cells (n + 2 are -1), 8n read targets 3t, the _CODE addresses 3(8n + k).
    Named values are 22 + 2 len(n) characters.  The longest chunk is all ones:
    -(2^w - 1), w = n or T mod n for the last; row 0 clear costs no digit.
    Equals the decoder on 0 followed by ones, n = 2..14.
    """
    code = 8 * n + 45
    width = len(str(3 * code + 17))
    full, rest = divmod(1 << n, n)
    return (
        3 * code + 17 + -(-(1 << n) // n)  # separators between cells
        + sum(len(str(3 * t)) for t in range(1, 8 * n + 1))
        + sum(len(str(3 * (8 * n + k))) for k in _CODE)
        + (15 * n + 88) * width + 2 * (n + 2)
        + 22 + 2 * len(str(n))
        + full * (1 + len(str((1 << n) - 1)))
        + (1 + len(str((1 << rest) - 1)) if rest else 0)
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
    """The shorter build is at most either one; at n = 9 a hashed table ships P.

    Witness (`_subleq_packed_worst` in test_execution_formulas): every chunk's top
    k rows one (k = 3; 6 at n = 10, where 896 has fewer digits than 1023), so
    each chunk keeps its top digit count, and the other rows a multiplicative
    hash, so the tree loses to P: n = 9..14 measured 1683, 2111, 2709, 3735,
    5563, 10069 = P.
    """
    return min(_packed(n, p), _tree(n, p))


FORMULAS = {"scaling": (_chars, frozenset(range(9, 15)), tuple(range(2, 15)))}
