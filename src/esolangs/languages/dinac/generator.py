"""DINAC Boolean program generator: a flat scan over the rows.

Each input is read once into a variable named by its height (``b0`` last).
The scan ORs the rarer answer's matching prefixes into ``a`` with ``o``;
``n`` conjoins tests. Empty blocks emit nothing, full blocks fold their
prefix once, and singleton blocks inline the remaining conjunction.
Other prefixes use one reusable flag per height, declared on first use.
Only essential inputs get a height; ignored inputs go into a scratch
variable. A constant table reads and prints without a scan.
No branch nests, so indentation cannot add a log T factor.

Size:
    Linear in T: at most 40T + 18n + 120 characters; names are indexed by
    height, so the T/2**h references to height h cost O(1) on average
    (sum of T * len(h) / 2**h); n=4 parity: 578 chars.
    Constants use 5n+15 chars, n+3 steps and 56+bl(n+2)+bl(n) written bits.

Decisions:
    A nested IF/ELSE tree costs 4 spaces of indent per level on every leaf,
    T log T characters; a function per subtree needs a name per subtree,
    again log T each.  The scan has neither.
"""

from bisect import bisect_right

from esolangs.generation.helpers import (
    _validate_truth_table,
    essential_inputs,
    read_at,
)
from esolangs.generation.lookup import prefix_counts

__all__ = ["dinac"]

_PRELUDE = (
    "DEF/00 n a:00 b:00",
    "    IF a",
    "        GIVE ~~b",
    "    ELSE",
    "        GIVE 00",
    "DEF/00 o a:00 b:00",
    "    IF a",
    "        GIVE 01",
    "    ELSE",
    "        GIVE ~~b",
)


def dinac(truth_table: str) -> str:
    """Build a DINAC program printing ``truth_table[row]`` for the inputs."""
    n = _validate_truth_table(truth_table)
    # Scan the rarer answer's rows and invert the print; the OR lines are the
    # only part that depends on the table, so the rarer side is the shorter
    # build (ties scan the 1-rows).
    # Ignored inputs are read into one scratch variable and left out of the
    # scan; a constant table prints its answer with no scan at all.
    keep = essential_inputs(truth_table, n)
    if not keep:
        return "\n".join([*_reads(n, keep), f"OUT '{truth_table[0]}"])
    table = read_at(truth_table, keep, n)
    mark = "1" if 2 * table.count("1") <= len(table) else "0"
    return _scan(table, mark, _reads(n, keep))


def _reads(n: int, keep: list[int]) -> list[str]:
    """Read every input in order: kept ones into ``b<height>``, the rest into ``x``."""
    lines = ["SET x:\\0"] if len(keep) < n else []
    for i in range(n):
        if i in keep:
            h = len(keep) - 1 - keep.index(i)
            lines += [f"SET b{h}:\\0", f"IN b{h}"]
        else:
            lines.append("IN x")
    return lines


def _test(parent: str | None, height: int, bit: int) -> str:
    """Conjoin the next input test with its prefix, if there is one."""
    test = f"b{height}='{bit}"
    return test if parent is None else f"n({parent},{test})"


def _scan(truth_table: str, mark: str, reads: list[str]) -> str:
    """Fold full blocks and singleton conjunctions; flag only mixed prefixes."""
    lines = [*_PRELUDE, *reads, "SET a:00"]
    counts = prefix_counts(truth_table, mark)
    declared: set[int] = set()

    def visit(lo: int, hi: int, parent: str | None) -> None:
        count = counts[hi] - counts[lo]
        if not count:
            return
        height = (hi - lo).bit_length() - 1
        if count == hi - lo or count == 1:
            if count == 1:
                # The first prefix increment identifies the sole matching row.
                row = bisect_right(counts, counts[lo], lo, hi + 1) - 1
                for h in range(height - 1, -1, -1):
                    parent = _test(parent, h, row >> h & 1)
            assert parent is not None
            lines.append(f"a . o(a,{parent})")
            return
        if parent is not None:
            flag = f"f{height}"
            lines.append(
                f"SET {flag}:{parent}"
                if height not in declared
                else f"{flag} . {parent}"
            )
            declared.add(height)
            parent = flag
        mid = (lo + hi) // 2
        visit(lo, mid, _test(parent, height - 1, 0))
        visit(mid, hi, _test(parent, height - 1, 1))

    visit(0, len(truth_table), None)
    lines += ["IF a", f"    OUT '{mark}", "ELSE", f"    OUT '{1 - int(mark)}"]
    return "\n".join(lines)
