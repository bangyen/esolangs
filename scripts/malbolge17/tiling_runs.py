"""Contiguous free space left by the six-slab digit-local tilings.

    uv run --no-project --with numpy python scripts/malbolge17/tiling_runs.py

A tiling fixes one trit ``z`` and pairs four of the other nine into digits
with a missing value each; groups are the words with every digit normal
(``z`` any), or with exactly one digit on its missing value and ``z != 0``.
That is the 16,384-group layout of "Seventeen: what a build would need".  Code
has to run in table-free cells, so this reports the free cells lying in runs
of at least 100 and 200, maximised over every choice of ``z``, the cell-index
trit and the 105 pairings, with missing values (0, 0) or (2, 2).
"""

from __future__ import annotations

import itertools
from collections.abc import Iterator
from typing import Any

import numpy as np  # type: ignore[import-not-found]

W = 59049
TRITS = np.stack([(np.arange(W) // 3**k) % 3 for k in range(10)])


def pairings(xs: list[int]) -> Iterator[list[tuple[int, int]]]:
    """Yield every way to split ``xs`` into pairs."""
    if not xs:
        yield []
        return
    for i in range(1, len(xs)):
        for rest in pairings(xs[1:i] + xs[i + 1 :]):
            yield [(xs[0], xs[i]), *rest]


def runs(
    z: int, pairs: list[tuple[int, int]], miss: tuple[tuple[int, int], ...]
) -> tuple[int, int, int]:
    """Return free cells in runs >= 100, >= 200, and the longest run."""
    missing = np.zeros(W, dtype=np.int8)
    for (i, j), (mi, mj) in zip(pairs, miss, strict=True):
        missing += (TRITS[i] == mi) & (TRITS[j] == mj)
    free = ~((missing == 0) | ((TRITS[z] != 0) & (missing == 1)))
    edges = np.diff(np.concatenate([[0], free.astype(np.int8), [0]]))
    lengths = np.where(edges == -1)[0] - np.where(edges == 1)[0]
    return (
        int(lengths[lengths >= 100].sum()),
        int(lengths[lengths >= 200].sum()),
        int(lengths.max()),
    )


def main() -> None:
    """Print the best tiling for contiguous code space."""
    best: tuple[Any, ...] = (0,)
    for z in range(10):
        for cell in range(10):
            if cell == z:
                continue
            rest = [t for t in range(10) if t not in (z, cell)]
            for pairs in pairings(rest):
                for miss in itertools.product([(0, 0), (2, 2)], repeat=4):
                    result = runs(z, pairs, miss)
                    if result[1] > best[0]:
                        best = (result[1], result, z, cell, pairs, miss)
    print("free cells in runs >= 200:", best[0], "(>= 100, >= 200, longest):", best[1])
    print("z, cell-index trit, digits, missing:", best[2:])


if __name__ == "__main__":
    main()
