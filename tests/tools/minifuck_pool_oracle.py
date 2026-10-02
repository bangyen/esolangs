"""Retired Minifuck pool solver retained as a differential test oracle."""

from functools import cache

from esolangs.tools.minifuck.pool import (
    _POOL,
    _POOL_CODES,
    _POOL_MASK,
    _POOL_WIDTH,
    _PROBE_WALK_OUT,
)
from esolangs.tools.minifuck.sim import _Joint, _runs, _Sim, _walk_to

#: Rightmost pointer at which the window is the whole key (at 3 codes reach
#: above cell 7; 3 of 300 verdicts changed).  Every build site has pointer
#: 0 (1956 of 1956 at n=2,3); beyond is refused, not guessed.
_POOL_PTR_MAX = 2


def _pool_code_for_row(
    codes: tuple[str, ...], low: int, ptr: int, cell7: int, *, skip: bool
) -> tuple[int, int] | None:
    """Return the pool code this row admits and where it leaves it, or None.

    The pointer comes back because a pool must be read from one place
    (:func:`_find_pool` compares them).  The verdict depends only on cells
    0..7, the pointer and a pending skip (400 windows x six upper
    randomisations: no change), composed with :meth:`_Sim.run_walk`'s closed
    form.  At the origin at most one code answers (512 keys: 36 singletons);
    across the derived domain 4 keys admit two, settled by index order.
    """
    for index, code in enumerate(codes):
        probe = _Sim(_POOL_WIDTH + _PROBE_WALK_OUT + _POOL_PTR_MAX + 4)
        probe.tape = low
        probe.ptr = ptr
        probe.skip = skip
        probe.apply(_runs(code))
        # Neither fires over the domain's 7680 runs; a breach is a change to
        # the pool, and ``continue`` would silently drop the code.
        if probe.dead or probe.skip:  # pragma: no cover - see above
            raise AssertionError(f"pool code {code!r} left a row unrunnable")
        steps = _PROBE_WALK_OUT - probe.ptr
        if steps < 0:  # pragma: no cover - see above
            raise AssertionError(f"pool code {code!r} ended past the walk out")
        landed = probe.ptr
        probe.run_walk(steps)
        target = (*_POOL, cell7)
        if all(probe.cell(cell) == target[cell] for cell in range(_POOL_WIDTH)):
            return index, landed
    return None


@cache
def _pool_slice(
    codes: tuple[str, ...], ptr: int, *, skip: bool
) -> dict[tuple[int, int], tuple[int, int]]:
    """Derive the verdict for every window byte at one ``(pointer, skip)``.

    Exhaustive over the 256 bytes and both orientations, a slice at a time:
    builds ask only at the origin with no skip (1956 of 1956 sites at n=2,3),
    and whole-domain derivation cost 57ms against a 0.2ms build.  Keyed on
    the code list because the codes are ablated.
    """
    return {
        (low, cell7): answer
        for low in range(1 << _POOL_WIDTH)
        for cell7 in (0, 1)
        if (answer := _pool_code_for_row(codes, low, ptr, cell7, skip=skip)) is not None
    }


def _find_pool(j: _Joint, cell7: int, walk_out: int) -> str | None:
    """Return the pool code for this orientation, or None if none fits.

    Each row names its code (:data:`_POOL_CODE_OF`) and the joint's verdict is
    the AND (40000 checks against :func:`_pool_reaches`).  Row uniformity is
    not required: rows differing at cells 5 and 6 are accepted by the code
    both name.  ``walk_out`` is invariant (9..39) and kept for the callers.
    """
    del walk_out

    codes = tuple(_POOL_CODES)

    def answer_for(row: _Sim) -> tuple[int, int] | None:
        """Which code this row names, and where that code leaves it."""
        if row.dead or row.ptr > _POOL_PTR_MAX:
            return None
        rows = _pool_slice(codes, row.ptr, skip=row.skip)
        return rows.get((row.tape & _POOL_MASK, cell7))

    chosen = answer_for(j.ms[0])
    if chosen is None:
        return None
    for row in j.ms[1:]:
        # Same code *and* same landing cell.
        if answer_for(row) != chosen:
            return None
    return codes[chosen[0]]


def _endgame(j: _Joint, acc: int, read: str, cell7: int) -> None:
    """Set the pool, relay ``acc`` into the pointer, and print one digit.

    The walk back is measured from the read's *entry*: a constant-1 column
    puts the pointer's minimum one cell further right.
    """
    if acc < _POOL_WIDTH:
        raise ValueError("accumulator must sit past the pool")
    code = _find_pool(j, cell7, acc - 1)
    if code is None:
        raise ValueError("no pool pattern for this orientation")
    j.emit(code)
    _walk_to(j, acc - 1)
    j.emit(read)
    j.emit("<" * (acc - (_POOL_WIDTH - 1)))
    # ``_find_pool``'s check, restated on what was emitted.  AssertionError on
    # purpose: ``_try_print`` swallows ValueError, and disagreement is a bug.
    for cell in range(_POOL_WIDTH):
        if len(set(j.col(cell))) != 1:
            raise AssertionError(f"pool cell {cell} is input-dependent")
    j.emit("[x.")
