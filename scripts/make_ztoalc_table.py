"""Regenerate the precomputed ZTOALC start table.

Computes, for every text length reachable within the search limit, the
Collatz start whose trajectory is long enough and has the smallest maximum
visited value, and writes the mapping to ztoalc_starts.py.

Usage: python scripts/make_ztoalc_table.py
"""

from array import array
from pathlib import Path

LIMIT = 1_000_000
OUT = Path(__file__).resolve().parent.parent / "src/esolangs/tools/ztoalc_starts.py"


def collatz_lengths(limit):
    lengths = array("H", [0]) * (limit + 1)
    lengths[1] = 0

    for start in range(2, limit + 1):
        if lengths[start]:
            continue

        path = []
        value = start
        while value > 1 and (value > limit or not lengths[value]):
            path.append(value)
            value = value // 2 if value % 2 == 0 else 3 * value + 1

        length = lengths[value] if value <= limit else 0
        for value in reversed(path):
            length += 1
            if value <= limit:
                lengths[value] = length

    return lengths


def best_starts(lengths):
    best: dict = {}
    for start in range(2, len(lengths)):
        running = 0
        value = start
        for n in range(1, lengths[start] + 1):
            running = max(running, value)
            entry = best.get(n)
            if entry is None or running < entry[0]:
                best[n] = (running, start)
            value = value // 2 if value % 2 == 0 else 3 * value + 1
    return {n: start for n, (size, start) in best.items()}


def write_module(starts):
    lines = [
        '"""Precomputed best Collatz start for each text length."""',
        "",
        "STARTS = {",
    ]
    for n in sorted(starts):
        lines.append(f"    {n}: {starts[n]},")
    lines.append("}")
    OUT.write_text("\n".join(lines) + "\n")
    print(f"wrote {OUT} with {len(starts)} entries")


if __name__ == "__main__":
    write_module(best_starts(collatz_lengths(LIMIT)))
