"""Executed command and snapshot-bit bounds."""

from esolangs.runtime._digits import digit_limit_for


def _digits(n: int) -> int:
    """Decimal digits of 2^T; the cap lifts for the 0.3T of them past n = 13."""
    with digit_limit_for(1 << n):
        return len(str(1 << (1 << n)))


def execution(n: int, _: str) -> int:
    """One command a character: 17 an input, a 19-letter frame, ``F…F``.

    The minimal lift has at most ``d + 1`` digits, ``d`` those of 2^T; the
    value 10^(d-1) - 1 needs all of them.
    """
    return 17 * n + 20 + _digits(n)


def _lift_bits(n: int) -> int:
    """Bit length of the largest lift with d + 1 digits, d those of 2^T.

    v lifts below d + 1 digits iff a band [10^j, 2·10^j), j < d, holds a
    member of v's class mod 2^T; else the lift is 10^d + (v - 10^d) mod 2^T.
    The largest is the valid residue cyclically nearest below 10^d mod 2^T.
    """
    span = 1 << (1 << n)
    d = _digits(n)
    covered: list[tuple[int, int]] = []
    for j in range(d):
        lo = 10**j % span
        hi = lo + 10**j
        covered += [(lo, hi)] if hi <= span else [(lo, span), (0, hi - span)]
    top = 10**d % span
    v = top - 1
    for _ in range(len(covered) * 2 + 2):
        if v < 0:
            v = span - 1
        hit = next((lo for lo, hi in covered if lo <= v < hi), None)
        if hit is None:
            return int(10**d + (v - top) % span).bit_length()
        v = hit - 1
    raise AssertionError("no valid residue")


def workspace(n: int, _: str) -> int:
    """Peak written bits: the frame text, the stack, the two read counters.

    The frame peaks at the literal's last digit, 8 bits a program character;
    the stack at the last read (T + 14) or the tail's ``[λ, 2, λ]``.
    """
    bl = int.bit_length
    t = 1 << n
    d = _digits(n)
    return (
        16 * d
        + 136 * n
        + 195
        + bl(17 * n + d + 5)
        + max(t + 14, 2 * _lift_bits(n) + 2)
        + bl(2 * n)
        + bl(n)
    )
