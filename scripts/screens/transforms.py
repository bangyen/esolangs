"""Screen every boolean generator for symmetry and pruning upside at n=3.

Each generator builds all 256
three-input tables (and all 16 two-input ones) once, and every column is a
lookup over those sizes.  A percentage is ``100 * (1 - sum(min)/sum(own))``
where ``min`` is the shortest build over the transformed tables:

``order``
    The 6 input orders; ``impr`` counts tables with a smaller reordered build.
``outneg``
    The table or its complement -- build ``not f`` and invert the answer.
``inpol``
    Any of the 8 input-polarity flips -- swap an input's 0 and 1 arms.
``npn``
    Any complement, flip and input order together (96 candidates), so the
    excess over ``order`` is what polarity and negation add.
``ignored``
    For three-input tables with exactly two essential inputs, the mean
    source units over the two-input build of their projection: what reading
    an input the function ignores costs (Line and Piet paid this once).

Every figure is an upper bound.  It charges nothing for the transform --
the inverter a negated build needs, or a polarity flip that a uniform
``(zero, one)`` fill pair forbids (``docs/limitations.md``) -- and the
``ignored`` column includes the read itself, which the interface keeps.
"""

import argparse
import sys
from collections.abc import Callable
from itertools import permutations
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _budget import options, supervise
from _build import PAIRS, TABLES, chosen, sizes

from esolangs.tools.helpers import (
    essential_inputs,
    permute_truth_table,
    read_at,
)

PERMS = list(permutations(range(3)))


def _negate(table: str) -> str:
    return table.translate(str.maketrans("01", "10"))


def _flip(table: str, mask: int) -> str:
    """Return the table with the inputs set in ``mask`` inverted."""
    return "".join(table[row ^ mask] for row in range(len(table)))


Row = tuple[float, int, float, float, float, float, float]


def screen(name: str, gen: Callable[[str], object]) -> Row | None:
    """Return (order %, improved, outneg %, inpol %, npn %, ignored, seconds)."""
    start = perf_counter()
    built_sizes = sizes(name, gen, TABLES)
    pairs = sizes(name, gen, PAIRS)
    elapsed = perf_counter() - start
    built = [t for t in TABLES if built_sizes[t] is not None]
    if not built:
        return None
    own = sum(built_sizes[t] or 0 for t in built)

    def upside(candidates: object) -> float:
        assert callable(candidates)
        best = 0
        for table in built:
            found = [s for c in candidates(table) if (s := built_sizes[c]) is not None]
            best += min(found, default=built_sizes[table] or 0)
        return 100 * (1 - best / own)

    reordered = {
        table: min(
            size
            for perm in PERMS
            if (size := built_sizes[permute_truth_table(table, perm)]) is not None
        )
        for table in built
    }
    order = 100 * (1 - sum(reordered.values()) / own)
    improved = sum(reordered[t] < (built_sizes[t] or 0) for t in built)
    outneg = upside(lambda t: [t, _negate(t)])
    inpol = upside(lambda t: [_flip(t, mask) for mask in range(8)])
    npn = upside(
        lambda t: [
            _flip(permute_truth_table(u, perm), mask)
            for u in (t, _negate(t))
            for perm in PERMS
            for mask in range(8)
        ]
    )
    extra = []
    for table in built:
        essential = essential_inputs(table, 3)
        if len(essential) == 2:
            projected = pairs[read_at(table, essential, 3)]
            if projected is not None:
                extra.append((built_sizes[table] or 0) - projected)
    ignored = sum(extra) / len(extra) if extra else float("nan")
    return order, improved, outneg, inpol, npn, ignored, elapsed


def main() -> None:
    """Screen the registry and print one row per language, best NPN first."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("languages", nargs="*")
    options(parser)
    args = parser.parse_args()
    languages = list(chosen(args.languages))
    plan = {
        "tables": len(languages) * (len(PAIRS) + len(TABLES)),
        "work_bound": len(languages) * (len(PAIRS) * 4 + len(TABLES) * 8),
        "work_unit": "truth_table_bits",
    }
    if not supervise(parser, args, Path(__file__), plan):
        return
    rows = []
    for key, gen in languages:
        result = screen(key, gen)
        if result is None:
            continue
        rows.append((key, *result))
    rows.sort(key=lambda row: (-row[5], row[0]))
    print(
        f"{'language':<32}{'order%':>8}{'impr':>6}{'outneg%':>8}{'inpol%':>8}{'npn%':>7}"
        f"{'ignored':>9}{'sec':>6}"
    )
    for key, order, improved, outneg, inpol, npn, ignored, elapsed in rows:
        print(
            f"{key:<32}{order:>8.1f}{improved:>6}{outneg:>8.1f}{inpol:>8.1f}{npn:>7.1f}"
            f"{ignored:>9.1f}{elapsed:>6.1f}"
        )


if __name__ == "__main__":
    main()
