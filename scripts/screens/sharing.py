"""Screen every boolean generator for what sharing equal subtrees could save.

A table's Shannon tree splits on input 0, then input 1, and so on in name
order; its nodes are the non-constant subtables at each level (a constant
subtable is a leaf).  Merging the equal ones *within a level* gives a
quasi-reduced decision diagram: no merging across levels, and a node whose
two halves agree still counts.  ``(tree - distinct) / tree`` is the share
of nodes a construction that emitted each subtree once would not repeat,
and it depends on no generator.

Each generator is weighted by what a node costs it: the slope of its
program length on parity, whose tree has every node non-constant and none
folded, from n=3 (7 nodes) to n=5 (31).  A figure is
``sum(duplicated nodes) * per-node cost / sum(program length)`` over the
tables -- all 256 at n=3, and a seeded sample at n=5, since the share of
repeated subtrees grows with n.

Every figure is an upper bound: it charges nothing for the jump, call or
stored subroutine a share costs, and assumes a repeated subtree costs a
generator what an average node of parity does.
"""

import argparse
import random
import sys
from collections.abc import Callable
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _budget import completed, options, price, setup, supervise
from _build import TABLES, chosen, size_cases, sizes

#: Parity at the two arities the per-node slope is taken between.
PARITY = {3: "01101001", 5: "01101001100101101001011001101001"}


def _nodes(table: str) -> tuple[int, int]:
    """Return (tree nodes, distinct nodes per level) for one table."""
    tree = distinct = 0
    width = len(table)
    while width > 1:
        level = [table[i : i + width] for i in range(0, len(table), width)]
        live = [sub for sub in level if len(set(sub)) > 1]
        tree += len(live)
        distinct += len(set(live))
        width //= 2
    return tree, distinct


def _tree_size(inputs: int) -> int:
    return (1 << inputs) - 1


def sample(count: int, seed: int) -> list[str]:
    """Return ``count`` distinct seeded random five-input tables."""
    rng = random.Random(seed)
    found: set[str] = set()
    while len(found) < count:
        found.add(format(rng.getrandbits(32), "032b"))
    return sorted(found)


def share(tables: list[str]) -> float:
    """Return the generator-independent share of repeated tree nodes, in %."""
    counts = [_nodes(table) for table in tables]
    tree = sum(t for t, _d in counts)
    return 100 * (1 - sum(d for _t, d in counts) / tree)


def per_node(name: str, gen: Callable[[str], object]) -> float | None:
    """Return the source units one tree node costs, from parity at n=3 and 5."""
    built = sizes(name, gen, list(PARITY.values()), scope="parity")
    small, large = built[PARITY[3]], built[PARITY[5]]
    if small is None or large is None:
        return None
    return (large - small) / (_tree_size(5) - _tree_size(3))


def bound(built: dict[str, int | None], cost: float) -> float | None:
    """Return the upside %, over the tables the generator built."""
    saved = total = 0.0
    for table, size in built.items():
        if size is None:
            continue
        tree, distinct = _nodes(table)
        saved += (tree - distinct) * cost
        total += size
    return 100 * saved / total if total else None


def screen(
    name: str, gen: Callable[[str], object], five: list[str]
) -> tuple[float, float | None, float | None, float] | None:
    """Return (cost per node, n=3 %, n=5 %, seconds), or None if unmeasurable."""
    start = perf_counter()
    cost = per_node(name, gen)
    if cost is None:
        for tables, scope in ((TABLES, "three"), (five, "five")):
            for identifier in size_cases(name, tables, scope):
                completed("skipped", case_id=identifier, language=name)
        return None
    three = bound(sizes(name, gen, TABLES, scope="three"), cost)
    at_five = bound(sizes(name, gen, five, scope="five"), cost)
    return cost, three, at_five, perf_counter() - start


def _cell(value: float | None) -> str:
    return f"{value:>8.1f}" if value is not None else f"{'-':>8}"


def main() -> None:
    """Screen the registry and print one row per language, best n=5 first."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("languages", nargs="*", help="registry names (default all)")
    parser.add_argument("--sample", type=int, default=200, help="n=5 tables")
    parser.add_argument("--seed", type=int, default=0, help="n=5 sample seed")
    options(parser)
    args = parser.parse_args()
    if not 1 <= args.sample <= 2**32:
        parser.error("--sample must be between 1 and 2**32")
    if args.sample + 258 > args.max_cases:
        parser.error("screen exceeds --max-cases")
    languages = list(chosen(args.languages))
    plan = {
        "tables": len(languages) * (2 + len(TABLES) + args.sample),
        "work_bound": len(languages) * (8 + 32 + len(TABLES) * 8 + args.sample * 32),
        "work_unit": "truth_table_bits",
    }
    price(parser, args, plan)
    if args.dry_run:
        supervise(parser, args, Path(__file__), plan)
        return
    prepared = setup(
        args,
        "sharing",
        {
            "count": args.sample,
            "seed": args.seed,
            "languages": [name for name, _gen in languages],
        },
    )
    five = prepared["tables"]
    plan["case_ids"] = prepared["case_ids"]
    if not supervise(parser, args, Path(__file__), plan):
        return
    print(f"repeated nodes: n=3 {share(TABLES):.1f}%, n=5 {share(five):.1f}%")
    rows = []
    for key, gen in languages:
        result = screen(key, gen, five)
        if result is not None:
            rows.append((key, *result))
    rows.sort(key=lambda row: (-(row[3] or 0), row[0]))
    print(f"{'language':<32}{'c/node':>8}{'n=3%':>8}{'n=5%':>8}{'sec':>7}")
    for key, cost, three, at_five, elapsed in rows:
        print(f"{key:<32}{cost:>8.1f}{_cell(three)}{_cell(at_five)}{elapsed:>7.1f}")


if __name__ == "__main__":
    main()
