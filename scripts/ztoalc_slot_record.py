"""Sieve the ZTOALC L slot-capacity record under the line ceiling.

Capacity of a start is how many values at or below ``_MAX_LINES`` its
Collatz trajectory visits (the final 1 excluded) -- the number of command
slots the boolean generator's placement can use.  Any start's capacity
equals that of its first trajectory value under the ceiling, so sieving
every start up to the ceiling is exhaustive over *all* starts.

Backs the 395 record cited in ``esolangs.tools.boolean.ztoalc_l`` and
``docs/limitations.md``: the committed anchors offer 386, the best start
anywhere offers 395, so lifting n=11 (587 dense / 545 parity commands)
needs a higher ceiling, not a better anchor.

Exits nonzero if the sieve disagrees with the committed 395, so this is a
guard on a cited constant rather than a one-time measurement.

Usage:
    python scripts/ztoalc_slot_record.py          # 2.2s
"""

import sys
from array import array

from esolangs.tools.boolean.ztoalc_l import _MAX_LINES


def sieve(cap: int) -> tuple[int, int]:
    """Return ``(record capacity, its smallest start)`` for starts <= cap.

    ``f(w)`` counts values <= cap from ``w`` down to the first value below
    ``w`` (already sieved), walking each excursion once.
    """
    f = array("i", [0] * (cap + 1))
    f[2] = 1
    best, best_start = 1, 2
    for w in range(3, cap + 1):
        value, count = w, 0
        while value >= w:
            if value <= cap:
                count += 1
            value = value // 2 if value % 2 == 0 else 3 * value + 1
        f[w] = count + f[value]
        if f[w] > best:
            best, best_start = f[w], w
    return best, best_start


def main() -> int:
    """Print the record and check it against the committed claim."""
    record, start = sieve(_MAX_LINES)
    print(f"record capacity under {_MAX_LINES}: {record} (start {start})")
    if record != 395:
        print("[FAIL] the 395 cited in ztoalc_l.py and limitations.md is stale")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
