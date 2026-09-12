r"""Sieve the ZTOALC L slot-capacity record under the line ceiling."""

import sys
from array import array

from esolangs.tools.boolean.ztoalc_l import _MAX_LINES


def sieve(cap: int) -> tuple[int, int]:
    r"""Return ``(record capacity, its smallest start)`` for starts <= cap."""
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
    r"""Print the record and check it against the committed claim."""
    record, start = sieve(_MAX_LINES)
    print(f"record capacity under {_MAX_LINES}: {record} (start {start})")
    if record != 395:
        print("[FAIL] the 395 cited in ztoalc_l.py and limitations.md is stale")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
