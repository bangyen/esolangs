"""Occurrence masks with charged validation, range folding and layout work.

Empty/full ranges give constants; mixed ranges split and hash-cons in the
dense fold's postorder. Shared budgets admit O(T) work before it happens.
"""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Sequence

from esolangs.languages.circuit_diagram.generator import (
    _Builder,
    _Dag,
    _finish_fold,
    _note_mux,
)
from esolangs.languages.circuit_diagram.generator.layout import _Layout, _resolve_order


class _SparseWork:
    """A shared, bounded work counter for sparse mask folding.

    :meth:`spend` charges work before it happens and reports whether the
    total is still within ``limit``.  A caller shares one instance across
    every mask, so the batch rather than each mask is bounded.
    """

    __slots__ = ("limit", "used")

    def __init__(self, limit: int) -> None:
        """Start a counter that admits ``limit`` units of work."""
        self.limit = limit
        self.used = 0

    def spend(self, cost: int) -> bool:
        """Charge ``cost`` and return whether the budget still holds."""
        self.used += cost
        return self.used <= self.limit


class _MaskFolder:
    """Fold a sparse prefix mask bottom-up, hash-consing each mixed range."""

    __slots__ = (
        "comparisons",
        "needed",
        "nodes",
        "ops",
        "positions",
        "prefix",
        "reads",
        "work",
    )

    def __init__(self, positions: list[int], prefix: int, work: _SparseWork) -> None:
        """Prepare state for ``positions`` over ``prefix`` inputs."""
        self.positions = positions
        self.prefix = prefix
        self.work = work
        # Worst-case comparisons of one bisect over the sorted positions.
        self.comparisons = max(1, len(positions).bit_length())
        self.ops: list[tuple[int, int, int, int]] = []
        self.needed: set[int] = set()
        self.reads: dict[int, int] = {}
        self.nodes: dict[tuple[int, int, int], int] = {}

    def build(self, k: int, lo: int, index: int, count: int) -> int | None:
        """Fold the ``2**k`` rows at ``lo`` holding ``count`` ones.

        ``index`` is ``positions``' first slot at or after ``lo``, so the
        midpoint split costs one bisect.  Returns ``None`` once the shared
        budget is exhausted, before the range is examined further.
        """
        if not self.work.spend(1):
            return None
        if count == 0:
            return 0
        size = 1 << k
        if count == size:
            return 1
        if not self.work.spend(self.comparisons):
            return None
        middle = lo + (size >> 1)
        split = bisect_left(self.positions, middle)
        left = split - index
        zero = self.build(k - 1, lo, index, left)
        if zero is None:
            return None
        one = self.build(k - 1, middle, split, count - left)
        if one is None:
            return None
        if zero == one:
            return zero
        level = k - 1
        key = (level, zero, one)
        node = self.nodes.get(key)
        if node is None:
            node = len(self.nodes) + 2
            self.nodes[key] = node
            self.ops.append((level, zero, one, node))
            _note_mux(self.needed, self.reads, self.prefix - 1 - level, zero, one)
        return node


def _validated_rows(positions: Sequence[int], prefix: int) -> list[int]:
    """Return the mask's rows after checking they sort and fit the prefix."""
    rows = list(positions)
    size = 1 << prefix
    for index, row in enumerate(rows):
        if not 0 <= row < size or (index and row <= rows[index - 1]):
            raise ValueError(
                "mask positions must be sorted, unique rows in [0, 2**prefix)"
            )
    return rows


def _sparse_mask_dag(
    positions: Sequence[int], prefix: int, work: _SparseWork
) -> _Dag | None:
    """Return :func:`_dag`'s ``(ops, root, needed, reads)`` for a sparse mask.

    ``positions`` are the sorted, unique rows the mask sets, each below
    ``2**prefix``.  The result is the dense fold's DAG exactly, without
    building the ``2**prefix`` mask, or ``None`` once ``work`` is spent.
    """
    if prefix < 1:
        raise ValueError("a sparse mask needs at least one prefix input")
    if not work.spend(2 * len(positions)):
        return None
    rows = _validated_rows(positions, prefix)
    folder = _MaskFolder(rows, prefix, work)
    root = folder.build(prefix, 0, 0, len(rows))
    if root is None:
        return None
    return _Dag(folder.ops, root, folder.needed, folder.reads)


def sparse_mask_model(
    positions: Sequence[int],
    prefix: int,
    *,
    input_order: Sequence[int] | None = None,
    port_inputs: int | None = None,
    work: _SparseWork,
) -> _Layout | None:
    """Build the folded circuit for a sparse prefix mask, or ``None`` over budget.

    Every one of the ``prefix`` mask inputs keeps an input port in read
    order; ``input_order`` names the original port each fold level reads and
    ``port_inputs`` may add unused ports.  A constant mask folds to one
    self-fed gate over the first rail, as the dense build does.
    """
    dag = _sparse_mask_dag(positions, prefix, work)
    if dag is None:
        return None
    order, port_inputs = _resolve_order(input_order, prefix, port_inputs, "fold")
    if not work.spend((len(dag.ops) + port_inputs) ** 2):
        return None
    # Unbanded folds make O(nodes+ports) taps; each interval guard scans at
    # most that many runs. Fenwick column work fits the same quadratic bound.
    builder = _Builder()
    ports = [builder.input_bus() for _ in range(port_inputs)]
    rails = [ports[order[level]] for level in range(prefix)]
    selectors = builder.selectors(rails, dag.needed)
    builder.band_start = builder.next_column
    return _finish_fold(builder, selectors, dag)
