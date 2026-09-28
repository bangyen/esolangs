"""Screen every boolean generator for input-reordering upside at n=3.

For each registry language with a boolean generator: build all 256
three-input tables once, then report ``100 * (1 - sum(min)/sum(identity))``
where ``min`` is the shortest build over the 6 input orders.  The n=3
table space is closed under input permutation, so the permuted builds are
lookups, not builds.  This metric reproduces the deleted ledger's verified
figures exactly (dig 19.5, flowchart 16.2, modulous 16.4, arrowqueue 7.2).
Run from the repository root: ``python scripts/screens/input_reorder.py``.

Premise, checked by execution: the program built for
``permute_truth_table(t, p)``, fed input ``k`` = bit ``p[k]`` of the row,
prints ``t[row]`` -- 288 runs over polynomial and brainfuck via the
suite's runners, all 6 orders, every row of three tables.

A figure bounds what wiring an order search could buy; it is not a
shipped saving, and for an already-wired generator it is residual the
search cannot reach from inside the fixed input convention.  The verdict
classes live in ``docs/roadmap.md``.
"""

import sys
from collections.abc import Callable
from itertools import permutations
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _build import TABLES, generators, sizes

from esolangs.tools.helpers import permute_truth_table

PERMS = list(permutations(range(3)))


def screen(gen: Callable[[str], object]) -> tuple[float, int, float] | None:
    """Return (upside %, tables improved, seconds), or None if all rejected."""
    start = perf_counter()
    built_sizes = sizes(gen, TABLES)
    elapsed = perf_counter() - start
    built = [t for t in TABLES if built_sizes[t] is not None]
    if not built:
        return None
    identity_total = best_total = improved = 0
    for table in built:
        identity = built_sizes[table]
        assert identity is not None
        shortest = min(
            size
            for perm in PERMS
            if (size := built_sizes[permute_truth_table(table, perm)]) is not None
        )
        identity_total += identity
        best_total += shortest
        improved += shortest < identity
    return 100 * (1 - best_total / identity_total), improved, elapsed


def main() -> None:
    """Screen the registry and print one row per language, best first."""
    rows = []
    for key, gen in generators():
        result = screen(gen)
        if result is None:
            continue
        rows.append((key, getattr(gen, "__name__", key), *result))
    rows.sort(key=lambda row: (-row[2], row[0]))
    print(f"{'language':<32}{'generator':<32}{'upside%':>8}{'impr':>6}{'sec':>7}")
    for key, name, upside, improved, elapsed in rows:
        print(f"{key:<32}{name:<32}{upside:>8.1f}{improved:>6}{elapsed:>7.1f}")


if __name__ == "__main__":
    main()
