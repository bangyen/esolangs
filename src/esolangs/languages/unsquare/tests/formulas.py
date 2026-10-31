"""Unsquare's ledger bounds, in the branched reads ``d = max(0, (n - 3) // 2)``.

A loop of 12 or 14 cells costs 3 a cell (a run of c costs at most 3c, equal
only at 12 and 14), so a leaf of ``S = T / 2**d`` cells pushes in 3 each and
pops in 1.  Every row pays 79 a pop read, 82 a branch read, 27 for the tail;
S = 12a + 14b needs S >= 64 (S = 16, 32 reach 3S - 2 only), hence past n = 7.
"""


def _depth(n: int) -> int:
    return max(0, (n - 3) // 2)


def _chars(n: int, _: str = "") -> int:
    d = _depth(n)
    return 2**n + 2 ** (n - d) + 16 * 2**d + 10 * (n - d) + 10


def _commands(n: int, _: str = "") -> int:
    return 4 * 2 ** (n - _depth(n)) + 79 * n + 3 * _depth(n) + 26


def _bits(n: int, program: str) -> int:
    length = len(program)
    return (
        2 ** (n - _depth(n))
        + 12
        + (_depth(n) + 1) * length.bit_length()
        + max(0, length - 33).bit_length()
        + 2 * n.bit_length()
    )


FORMULAS = {
    "scaling": (_chars, frozenset(range(2, 10)), tuple(range(2, 10))),
    "execution": (_commands, True, (8, 9)),
    "workspace": (_bits, False, (3, 6, 7)),
}
