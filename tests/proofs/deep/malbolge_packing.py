"""Certify the seventeen-input Malbolge storage map.

Run:  just proofs   (or python tests/proofs/deep/malbolge_packing.py)

Three cyclic trit translates of the fourteen-bit positional address give
three source cells per eight-row block.  Most are disjoint; a collision pair
shares all three.  The pair key is four base-7 digits, and ``private_orbit``
maps its rank without a lookup table into one unused three-cell orbit.
"""

from __future__ import annotations

from collections import defaultdict

from esolangs.tools._malbolge_digits import _readouts

BAND = "verify"
COST = 0.5

_WORDS = 3**10
_KEY_DIGITS = (
    (0, 1, 4, 5, 6, 7, 8),
    (1, 2, 3, 5, 6, 7, 8),
    (0, 1, 3, 4, 5, 6, 8),
    (0, 1, 4, 5, 6, 7, 8),
)
_BOX_B_DIGIT = (0, 1, 2, 3, 4, 5, 6, 8)


def _translate(value: int, amount: int) -> int:
    """Add ``amount`` modulo three to every trit of ``value``."""
    result = 0
    for place in (3**index for index in range(10)):
        result += (((value // place) % 3 + amount) % 3) * place
    return result


def _orbit(value: int) -> tuple[int, int, int]:
    return tuple(sorted(_translate(value, amount) for amount in range(3)))


def _digits(value: int) -> tuple[int, ...]:
    return tuple((value // 9**index) % 9 for index in range(5))


def _word(digits: list[int]) -> int:
    return sum(digit * 9**index for index, digit in enumerate(digits))


def _rank(orbit: tuple[int, int, int]) -> int:
    """Return the base-7 rank of one positional collision pair."""
    digits = _digits(next(value for value in orbit if _digits(value)[4] == 2))
    return sum(
        allowed.index(digits[index]) * 7**index
        for index, allowed in enumerate(_KEY_DIGITS)
    )


def _private_orbit(rank: int) -> tuple[int, int, int]:
    """Return the free orbit for collision-pair ``rank``, without a table."""
    if rank < 2 * 9**3:
        quotient = rank
        digits = [7, quotient % 9]
        quotient //= 9
        digits.append(quotient % 9)
        quotient //= 9
        digits.append(quotient % 9)
        quotient //= 9
        digits.append((4, 6)[quotient])
    else:
        quotient = rank - 2 * 9**3
        digits = [_BOX_B_DIGIT[quotient % 8], 8]
        quotient //= 8
        digits.append(quotient % 9)
        quotient //= 9
        digits.append(quotient % 9)
        quotient //= 9
        digits.append((4, 6)[quotient])
    return _orbit(_word(digits))


def main() -> int:
    """Check every block, collision pair, and private orbit."""
    owners: defaultdict[tuple[int, int, int], list[int]] = defaultdict(list)
    for row, readout in enumerate(_readouts(15)):
        owners[_orbit(readout)].append(row)

    counts: defaultdict[int, int] = defaultdict(int)
    for rows in owners.values():
        counts[len(rows)] += 1
    assert dict(counts) == {1: 11_582, 2: 2_401}

    occupied = set(owners)
    collision_orbits = {orbit for orbit, rows in owners.items() if len(rows) == 2}
    ranks = {_rank(orbit) for orbit in collision_orbits}
    assert ranks == set(range(7**4))

    private = {_private_orbit(rank) for rank in ranks}
    assert len(private) == 7**4
    assert private.isdisjoint(occupied)
    assert len({cell for orbit in private for cell in orbit}) == 3 * 7**4

    print(
        "Malbolge packing: 11,582 private blocks, 2,401 collision pairs, "
        "2,401 distinct free private orbits"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
