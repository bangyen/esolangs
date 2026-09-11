"""Screen every boolean generator for input-reordering upside at n=3.

For each registry language with a boolean generator: build all 256
three-input tables once, then report ``100 * (1 - sum(min)/sum(identity))``
where ``min`` is the shortest build over the 6 input orders.  The n=3
table space is closed under input permutation, so the permuted builds are
lookups, not builds.  This metric reproduces the deleted ledger's verified
figures exactly (dig 19.8, flowchart 17.1, modulous 16.4, arrowqueue 12.4).

Premise, checked by execution 2026-09: the program built for
``permute_truth_table(t, p)``, fed input ``k`` = bit ``p[k]`` of the row,
prints ``t[row]`` -- 288 runs over polynomial and brainfuck via the
suite's runners, all 6 orders, every row of three tables.

A figure bounds what wiring an order search could buy; it is not a
shipped saving, and for an already-wired generator it is residual the
search cannot reach from inside the fixed input convention.  The verdict
classes live in ``docs/roadmap.md``.
"""

from itertools import permutations
from time import perf_counter

from esolangs.registry import LANGUAGES
from esolangs.tools.boolean.helpers import permute_truth_table

TABLES = [format(i, "08b") for i in range(256)]
PERMS = list(permutations(range(3)))


def screen(gen: object) -> tuple[float, int, float] | None:
    """Return (upside %, tables improved, seconds), or None if all rejected.

    ``ValueError`` marks an arity a generator does not cover and skips the
    table; anything else is a real failure and propagates.
    """
    assert callable(gen)
    sizes: dict[str, int | None] = {}
    start = perf_counter()
    for table in TABLES:
        try:
            sizes[table] = len(str(gen(table)))
        except ValueError:
            sizes[table] = None
    elapsed = perf_counter() - start
    built = [t for t in TABLES if sizes[t] is not None]
    if not built:
        return None
    identity_total = best_total = improved = 0
    for table in built:
        identity = sizes[table]
        assert identity is not None
        shortest = min(
            size
            for perm in PERMS
            if (size := sizes[permute_truth_table(table, perm)]) is not None
        )
        identity_total += identity
        best_total += shortest
        improved += shortest < identity
    return 100 * (1 - best_total / identity_total), improved, elapsed


def main() -> None:
    """Screen the registry and print one row per language, best first."""
    rows = []
    for key, lang in sorted(LANGUAGES.items()):
        if lang.boolean is None:
            continue
        result = screen(lang.boolean)
        if result is None:
            continue
        rows.append((key, lang.boolean.__name__, *result))
    rows.sort(key=lambda row: (-row[2], row[0]))
    print(f"{'language':<32}{'generator':<32}{'upside%':>8}{'impr':>6}{'sec':>7}")
    for key, name, upside, improved, elapsed in rows:
        print(f"{key:<32}{name:<32}{upside:>8.1f}{improved:>6}{elapsed:>7.1f}")


if __name__ == "__main__":
    main()
