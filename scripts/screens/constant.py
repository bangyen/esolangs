"""Screen every boolean generator for what folding constant subtables could save.

A table's Shannon tree splits on input 0, then input 1, and so on in name
order; a constant subtable is a leaf that a folding construction emits once.
A construction that tested through it instead would emit every subtable down
to the rows.  For each *maximal* constant subtable of ``2**k`` rows that is
``2**k - 1`` nodes, and ``nodes / program length`` is the share of a build
that folding removes -- the complement of :mod:`sharing`, which counts
non-constant repeated nodes.

Each generator is weighted by what a node costs it: the slope of its program
length on parity, as in :mod:`sharing`.  Every figure is an upper bound: it
charges nothing for the branch a folder drops, and assumes a folded constant
costs a generator what an average parity node does.
"""

from pathlib import Path

from _model import PARITY, run, sample

__all__ = ["PARITY", "main", "sample"]


def _nodes(table: str) -> int:
    """Return the nodes inside every maximal constant subtable, parents first."""
    total = 0
    width = len(table)
    parents: list[bool] = []
    first = True
    while width > 1:
        subtables = [table[i : i + width] for i in range(0, len(table), width)]
        constant = [len(set(sub)) == 1 for sub in subtables]
        for index, is_constant in enumerate(constant):
            if is_constant and (first or not parents[index // 2]):
                total += width - 1
        parents = constant
        first = False
        width //= 2
    return total


def main() -> None:
    """Screen the registry and print one row per language, best n=5 first."""
    run(_nodes, "constant", "constant nodes", Path(__file__))


if __name__ == "__main__":
    main()
