"""Unsquare's ledger bounds, in the branched reads ``d = max(0, (n - 3) // 2)``.

Past n = 5 a loop of 12 or 14 cells costs 3 a cell (a run of c costs at most
3c), so a leaf of ``T / 2**d`` cells pushes in 3 each and pops in 1.
"""


def _depth(n: int) -> int:
    return max(0, (n - 3) // 2)


def _chars(n: int, _: str = "") -> int:
    d = _depth(n)
    return 2**n + 2 ** (n - d) + 16 * 2**d + 10 * (n - d) + 10


def _commands(n: int, _: str = "") -> int:
    return 4 * 2 ** (n - _depth(n)) + 82 * n + 22


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
    "execution": (_commands, False, (6, 7, 8)),
    "workspace": (_bits, False, (3, 6, 7)),
}
