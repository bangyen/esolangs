"""Affine bases and dual constraints for the Vandevelo cover."""

from __future__ import annotations

from esolangs.languages.vandevelo._peel import _points


def _echelon(dirs: list[int], n: int) -> list[int]:
    """Reduced-echelon basis of the constraint space of ``span(dirs)``.

    Reduced elimination keeps each dual to one free coordinate plus bits on
    the ``len(dirs)`` pivots, so no vector is wider than ``dim + 1``.  Only
    the completion step of :func:`_constraints` needs it.
    """
    pivots: dict[int, int] = {}
    for row in dirs:
        cur = row
        for bit, prow in pivots.items():
            if cur >> bit & 1:
                cur ^= prow
        if not cur:  # pragma: no cover - the peel only keeps independent dirs
            # A dependent direction would reduce to zero and take the pivot
            # key to -1, quietly corrupting the dual basis and so the guard.
            raise AssertionError("dependent direction reached elimination")
        hi = cur.bit_length() - 1
        for bit in pivots:
            if pivots[bit] >> hi & 1:
                pivots[bit] ^= cur
        pivots[hi] = cur
    duals = []
    for free in (b for b in range(n) if b not in pivots):
        w = 1 << free
        for bit, prow in pivots.items():
            if prow >> free & 1:
                w ^= 1 << bit
        duals.append(w)
    return duals


def _constraints(base: int, dirs: list[int], n: int) -> list[tuple[int, int]]:
    """Dual constraints pinning ``base + span(dirs)``: ``(parity, value)``.

    A constraint is a set of inputs whose ``dirs``-columns (the vector of
    the set's bits across the directions) sum to zero, and any basis of
    those sets pins the cube.  This one is built from short relations:
    inputs are scanned in order and kept in a *core* while no one-to-four
    of the core's columns sum to zero; every other input's column is, by
    maximality, a sum of at most three core columns, giving it a relation
    of weight at most four that no other relation shares its bit with.
    The core's pairwise column sums are distinct and nonzero in
    ``2**dim - 1`` values, so it holds at most ``1 + 2**((dim + 1) / 2)``
    inputs, and the ``|core| - dim`` relations still missing come from
    the reduced-echelon basis, each at most ``dim + 1`` wide.

    A cube's constraints therefore weigh at most
    ``4 * n + (dim + 1) * (1 + 2**((dim + 1) / 2))`` in total, against
    ``(n - dim) * (dim + 1)`` for the echelon basis alone, which is what
    the module docstring's O(T) upkeep bound sums.
    """
    dim = len(dirs)
    cols = [sum((v >> j & 1) << i for i, v in enumerate(dirs)) for j in range(n)]
    # Keep pair sums rather than materializing every triple. Querying a
    # triple against each core column yields the first witness in that order.
    witnesses: dict[int, int] = {}
    pairs: dict[int, int] = {}
    core: list[int] = []
    duals: list[int] = []

    def rank(inputs: int) -> tuple[int, int, list[int]]:
        # Witnesses order by last input, then width, then the earlier
        # inputs in ascending order.
        return inputs.bit_length(), inputs.bit_count(), _points(inputs)

    for j, col in enumerate(cols):
        if col == 0:
            duals.append(1 << j)
            continue
        witness = witnesses.get(col)
        if witness is None:
            witness = pairs.get(col)
            for c in core:
                # Witnesses rank by their last input first. The ascending
                # core cannot improve a witness once it passes that input.
                if witness is not None and c >= witness.bit_length():
                    break
                pair = pairs.get(col ^ cols[c])
                if pair is not None and not pair & (1 << c):
                    triple = pair | (1 << c)
                    if witness is None or rank(triple) < rank(witness):
                        witness = triple
        if witness is not None:
            # A later core input cannot precede this witness's last input,
            # so repeats keep the first witness without another core scan.
            witnesses[col] = witness
            duals.append(witness | (1 << j))
        else:
            for c in core:
                pairs[col ^ cols[c]] = (1 << j) | (1 << c)
            witnesses[col] = 1 << j
            core.append(j)
    # A short relation's leading bit is its own input -- the core inputs it
    # sums are all earlier -- so the relations are independent as they
    # stand.  Complete to a basis from the echelon duals, keeping each only
    # when it is independent of what came before.
    reduced = {w.bit_length() - 1: w for w in duals}
    for w in _echelon(dirs, n):
        cur = w
        while cur and (cur.bit_length() - 1) in reduced:
            cur ^= reduced[cur.bit_length() - 1]
        if cur:
            reduced[cur.bit_length() - 1] = cur
            duals.append(w)
    if len(duals) != n - dim:  # pragma: no cover - a basis has n - dim rows
        raise AssertionError("constraint basis has the wrong rank")
    return [(w, (w & base).bit_count() % 2) for w in duals]


def _affine_coset(table: str, ones: set[int]) -> tuple[int, list[int]] | None:
    """Return a basis for an affine 1-set, with O(T) membership work."""
    size = len(ones)
    if not size or size & (size - 1):
        return None
    base = min(ones)
    points = {base}
    dirs = []
    for row, entry in enumerate(table):
        if entry == "0" or row in points:
            continue
        direction = row ^ base
        extension = {point ^ direction for point in points}
        if len(points) * 2 > size or any(table[point] != "1" for point in extension):
            return None
        points.update(extension)
        dirs.append(direction)
    return base, dirs
