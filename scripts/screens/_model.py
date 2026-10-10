"""Shared plumbing for the constant- and repeated-node corpus screens.

Both screens measure the same thing -- a table's Shannon tree against what it
costs a generator -- and differ only in which nodes they count.  This module
holds the tree, the pricing, the per-node cost and the bounded CLI so neither
screen repeats it.
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

type NodeCount = Callable[[str], int]


def tree_size(inputs: int) -> int:
    """Return the nodes in a full Shannon tree over ``inputs`` inputs."""
    return (1 << inputs) - 1


def sample(count: int, seed: int) -> list[str]:
    """Return ``count`` distinct seeded random five-input tables."""
    rng = random.Random(seed)
    found: set[str] = set()
    while len(found) < count:
        found.add(format(rng.getrandbits(32), "032b"))
    return sorted(found)


def share(tables: list[str], nodes: NodeCount) -> float:
    """Return the generator-independent share of ``nodes`` per table, in %."""
    counted = sum(nodes(table) for table in tables)
    total = sum(tree_size(len(table).bit_length() - 1) for table in tables)
    return 100 * counted / total if total else 0.0


def per_node(name: str, gen: Callable[[str], object]) -> float | None:
    """Return the source units one tree node costs, from parity at n=3 and 5."""
    built = sizes(name, gen, list(PARITY.values()), scope="parity")
    small, large = built[PARITY[3]], built[PARITY[5]]
    if small is None or large is None:
        return None
    return (large - small) / (tree_size(5) - tree_size(3))


def bound(built: dict[str, int | None], cost: float, nodes: NodeCount) -> float | None:
    """Return the upside %, over the tables the generator built."""
    saved = total = 0.0
    for table, size in built.items():
        if size is None:
            continue
        saved += nodes(table) * cost
        total += size
    return 100 * saved / total if total else None


def screen(
    name: str, gen: Callable[[str], object], five: list[str], nodes: NodeCount
) -> tuple[float, float | None, float | None, float] | None:
    """Return (cost per node, n=3 %, n=5 %, seconds), or None if unmeasurable."""
    start = perf_counter()
    cost = per_node(name, gen)
    if cost is None:
        for tables, scope in ((TABLES, "three"), (five, "five")):
            for identifier in size_cases(name, tables, scope):
                completed("skipped", case_id=identifier, language=name)
        return None
    three = bound(sizes(name, gen, TABLES, scope="three"), cost, nodes)
    at_five = bound(sizes(name, gen, five, scope="five"), cost, nodes)
    return cost, three, at_five, perf_counter() - start


def _cell(value: float | None) -> str:
    return f"{value:>8.1f}" if value is not None else f"{'-':>8}"


def run(nodes: NodeCount, phase: str, label: str, path: Path) -> None:
    """Price, prepare and print one node-count screen over the registry."""
    parser = argparse.ArgumentParser(description=f"Screen {label} per generator.")
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
        supervise(parser, args, path, plan)
        return
    prepared = setup(
        args,
        phase,
        {
            "count": args.sample,
            "seed": args.seed,
            "languages": [name for name, _gen in languages],
        },
    )
    five = prepared["tables"]
    plan["case_ids"] = prepared["case_ids"]
    if not supervise(parser, args, path, plan):
        return
    print(f"{label}: n=3 {share(TABLES, nodes):.1f}%, n=5 {share(five, nodes):.1f}%")
    rows = []
    for key, gen in languages:
        result = screen(key, gen, five, nodes)
        if result is not None:
            rows.append((key, *result))
    rows.sort(key=lambda row: (-(row[3] or 0), row[0]))
    print(f"{'language':<32}{'c/node':>8}{'n=3%':>8}{'n=5%':>8}{'sec':>7}")
    for key, cost, three, at_five, elapsed in rows:
        print(f"{key:<32}{cost:>8.1f}{_cell(three)}{_cell(at_five)}{elapsed:>7.1f}")
