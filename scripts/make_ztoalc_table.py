"""Regenerate the precomputed ZTOALC start table.

Computes, for every text length reachable within the search limit, the
Collatz start whose trajectory is long enough and has the smallest maximum
visited value, and writes the mapping to ztoalc_starts.py.

Usage: python scripts/make_ztoalc_table.py
"""

from pathlib import Path

from esolangs.tools._ztoalc import _ZTOALC_TABLE_LIMIT, _collatz_length_table

OUT = Path(__file__).resolve().parent.parent / "src/esolangs/tools/ztoalc_starts.py"


def best_starts(lengths: list[int]) -> dict[int, int]:
    """Choose the smallest-peak start for each trajectory length."""
    best: dict[int, tuple[int, int]] = {}
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


def write_module(starts: dict[int, int]) -> None:
    """Write the ``ztoalc_starts`` Python module to stdout."""
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
    write_module(best_starts(_collatz_length_table(_ZTOALC_TABLE_LIMIT)))
