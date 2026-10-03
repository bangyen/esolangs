"""Classes of a group's triples that no ``p p p`` fold can tell apart.

    uv run python scripts/malbolge17/fold_classes.py

For each residue, two admissible triples are merged when
``crazy(crazy(crazy(a, v0), v1), v2)`` has the same low five trits for all
243 low constants ``a`` (the high trits never see a plain operand).  Prints
the fewest classes over the 94 residues: 272, so a stateless fold decoder
must map 272 classes onto all 256 answer vectors at its worst residue.
"""

from __future__ import annotations

from esolangs.interpreters.other.malbolge import _crazy
from esolangs.tools.malbolge.core import _char_for

OPS = "ji*p</vo"


def main() -> None:
    """Print the fewest and most fold classes over the residues."""
    counts = []
    for h in range(94):
        cells = [[_char_for(op, h + c) for op in OPS] for c in range(3)]
        keys = {
            tuple(_crazy(_crazy(_crazy(a, v0), v1), v2) % 243 for a in range(243))
            for v0 in cells[0]
            for v1 in cells[1]
            for v2 in cells[2]
        }
        counts.append(len(keys))
    print(f"fold classes per residue: min {min(counts)}, max {max(counts)}")


if __name__ == "__main__":
    main()
