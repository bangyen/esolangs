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

from pathlib import Path

from _model import PARITY, run, sample

__all__ = ["PARITY", "main", "sample"]


def _nodes(table: str) -> int:
    """Return the repeated nodes: non-constant subtables less the distinct ones."""
    tree = distinct = 0
    width = len(table)
    while width > 1:
        level = [table[i : i + width] for i in range(0, len(table), width)]
        live = [sub for sub in level if len(set(sub)) > 1]
        tree += len(live)
        distinct += len(set(live))
        width //= 2
    return tree - distinct


def main() -> None:
    """Screen the registry and print one row per language, best n=5 first."""
    run(_nodes, "sharing", "repeated nodes", Path(__file__))


if __name__ == "__main__":
    main()
