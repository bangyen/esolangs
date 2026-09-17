"""The Minifuck embed and the pool the endgame prints through.

Every route embeds each input once with :func:`_embed` and prints through
cells 0..7, the *pool*; the embed, pool codes, column derivation and
endgame are shared here.
"""

from functools import cache

from esolangs.tools.minifuck_sim import _clamp, _Joint, _runs, _Sim, _walk_to

# First embedded bit; the pool is cells 0..7, plus room for the walk-in.
_BASE = 16

# Between embedded bits (a plain ``[x`` run correlates the prefix-XORs).
# The first two leave 126 distinct columns vs 252 for all five; the last
# three carry 118 of the 120 tables they miss.  Only the first two are scanned.
_SEPS = ("[x<[x", "[x[x[x", "[<[<[", "[[[[[", "[x[<[")
_SEP = _SEPS[0]

# Widening this multiplies every search's cost; the plan reaches the rest.
_SCAN_SEPS = _SEPS[:2]

# Reach of the bits and their working area, for sizing windows.
_SPAN = 6

# ASCII '0' (0b00110000) or '1' (0b00110001): cells 0..6 fixed, cell 7 answer.
_POOL = (0, 0, 1, 1, 0, 0, 0)

# ``.`` reads ``tape[:8]`` as one byte.  The same 8 is the ``_endgame``
# floor, the rewind guard and :data:`_PROBE_WALK_OUT`; the sculpting loop
# starting one past the guard is what makes the rewind bound tight.
_POOL_WIDTH = len(_POOL) + 1

# ``[<`` lands at ``(acc-1) + v``, ``[x<[<`` at ``(acc-1) + NOT v``; the
# digit is ``NOT(v XOR cell7)``, so read polarity is what makes a table
# and its complement both printable.
_READS = ("[<", "[x<[<")


# Complements the bit a setter just wrote.  The ``x`` absorbs the cascade's
# skip flag, or the gadget eats the template's next instruction: ``<[``
# passed a tape+pointer probe and printed 0 of 12 on the real interpreter.
_FLIP = "<[x"


def _embed(
    n: int,
    settle: int = 0,
    sep: str = _SEP,
    flips: int = 0,
) -> _Joint:
    """Emit the embed: each input's run once, separated by :data:`_SEP`.

    ``settle`` re-crosses the region for a different column set.  ``flips``
    complements inputs as they land (a derivation coordinate; the pass that
    varied it is gone).  Setters stay in name order (the slot-order invariant).
    """
    j = _Joint(n)
    _walk_to(j, _BASE - 1)
    for i in range(n):
        j.emit_setter(i)
        if (flips >> i) & 1:
            j.emit(_FLIP)
        j.emit("[x")
        if i + 1 < n:
            j.emit(sep)
    for _ in range(settle):
        _clamp(j)
        _walk_to(j, _BASE - 1)
    return j


# Pool codes carry a mark right, then park the pointer behind it.  Tried in
# order; similar-looking strings diverge on the live pool state.
def _step(carry: int = 1, backs: int = 1, *, odd: bool = True) -> str:
    """One step of a pool code: carry a mark right, then walk the pointer back.

    ``k`` brackets carry a mark ``ceil(k / 2)`` and leave a skip when ``k``
    is odd, so a carry of ``c`` is ``2 * c - 1`` with the skip and ``2 * c``
    without; the ``<`` run sets how far behind the mark the pointer ends.
    """
    return "[" * (2 * carry - odd) + "<" * backs


# ``(steps, core, {step: (backs, odd)})``; a default step carries one
# cell, the core two.  Measured not to compress: moving a core strands
# 22 / 18 / 6 tables for plans 3 / 4 / 5 and slot order pins plan 2's.
_PLANS: tuple[tuple[int, int, dict[int, tuple[int, bool]]], ...] = (
    (2, 0, {1: (4, True)}),
    (4, 1, {}),
    (5, 2, {}),
    (5, 3, {0: (2, True)}),
    (5, 3, {2: (2, True), 4: (3, False)}),
)


def _render(steps: int, core: int, overrides: dict[int, tuple[int, bool]]) -> str:
    """Spell one plan out as a pool code."""
    codes = []
    for i in range(steps):
        backs, odd = overrides.get(i, (1, True))
        codes.append(_step(carry=2 if i == core else 1, backs=backs, odd=odd))
    return "".join(codes)


_POOL_CODES = tuple(_render(*plan) for plan in _PLANS)


def _pool_reaches(j: _Joint, code: str, cell7: int, walk_out: int) -> bool:
    """Whether ``code`` leaves the pool correct once walked out.

    Judged *after* the walk to the accumulator, which crosses the pool.
    """
    target = (*_POOL, cell7)
    probe = [m.copy() for m in j.ms]
    for char in code:
        for m in probe:
            m.exec(char)
    if any(m.dead or m.skip for m in probe):
        return False
    if len({m.ptr for m in probe}) != 1:
        return False
    steps = walk_out - probe[0].ptr
    if steps < 0:
        return False
    for _ in range(steps):
        for char in "[x":
            for m in probe:
                m.exec(char)
    for cell in range(_POOL_WIDTH):
        col = {m.cell(cell) for m in probe}
        if len(col) != 1 or probe[0].cell(cell) != target[cell]:
            return False
    return True


# The verdict is invariant in the walk out (9..39), so the key omits it.
_PROBE_WALK_OUT = _POOL_WIDTH + 1

#: Cells 0 to ``_POOL_WIDTH - 1``: the window a pool verdict depends on.
_POOL_MASK = (1 << _POOL_WIDTH) - 1


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


def _complement(column: tuple[int, ...]) -> tuple[int, ...]:
    """Flip every row of a column."""
    return tuple(1 - bit for bit in column)


# Keyed by ``(template, accumulator, orientation)``; a dict since ``None``
# is a real answer.  ``_derived_plans.cache_clear`` empties it too (tests
# count ``_find_pool`` sites, which a warm cache cuts to seventeen).
_PRINTED_COLUMNS: dict[tuple[str, int, int], tuple[int, ...] | None] = {}
_MISSING = object()


def _printed_column(j: _Joint, acc: int, cell7: int) -> tuple[int, ...] | None:
    """Return what the ``'[x<[<'`` read prints here, without printing it.

    After the pool code and walk to ``acc - 1`` the read reports ``ptr + 1``,
    complemented for ``'[<'``.  Checked against :func:`_endgame` over 15600
    columns; ``None`` on the two conditions it raises on.  Memoised on the
    template: 12612 distinct triples at n=3 however many tables are asked.
    """
    key = (j.template(), acc, cell7)
    hit = _PRINTED_COLUMNS.get(key, _MISSING)
    if hit is not _MISSING:
        return hit  # type: ignore[return-value]
    column = _derive_column(j, acc, cell7)
    _PRINTED_COLUMNS[key] = column
    return column


def _derive_column(j: _Joint, acc: int, cell7: int) -> tuple[int, ...] | None:
    """Return the column :func:`_printed_column` memoises, derived fresh.

    For :func:`_try_print`, whose fresh template per sculpted build would
    never hit the memo.
    """
    code = _find_pool(j, cell7, acc - 1)
    if code is None:
        return None
    probe = j.fork()
    probe.emit(code)
    try:
        _walk_to(probe, acc - 1)
    except ValueError:  # pragma: no cover - not observed, not unreachable
        # ``_find_pool`` ignores ``walk_out``; 1740 real stagings, no failure.
        return None
    return tuple(probe.col(probe.ms[0].ptr + 1))


def _confirm(
    j: _Joint, acc: int, read: str, cell7: int, column: tuple[int, ...]
) -> bool:
    """Whether the endgame really prints ``column`` here.

    Nothing is recorded on the algebra alone.  :func:`_endgame`'s
    input-independence assertion is a bug in the pair, not a miss, and propagates.
    """
    probe = j.fork()
    try:
        _endgame(probe, acc, read, cell7)
    except ValueError:  # pragma: no cover - not observed (268 confirmations, n=2,3)
        # Kept: an endgame that cannot run is the disagreement this exists for.
        return False
    printed = probe.printed()
    if any(len(digit) != 1 for digit in printed):
        return False
    return tuple(int(digit) for digit in printed) == column


def _try_print(j: _Joint, truth_table: str, acc: int) -> _Joint | None:
    """Emit the endgame that prints the table at ``acc``, or None.

    Read and orientation are computed from :func:`_derive_column` (the reads
    differ only in polarity), in the old trial order; the output is still
    compared against the table (15600 columns checked, corpus byte-identical).
    """
    if acc < _POOL_WIDTH:
        # Mirrors ``_endgame``'s floor.  Not a dead guard: ``_degenerate``
        # probes every cell and the constant-one column sits at cell 1.
        return None
    want = list(truth_table)
    derived: dict[int, tuple[int, ...] | None] = {}
    for read in _READS:
        for cell7 in (0, 1):
            if cell7 not in derived:
                derived[cell7] = _derive_column(j, acc, cell7)
            column = derived[cell7]
            if column is None:
                continue
            digits = column if read == _READS[1] else _complement(column)
            if list(map(str, digits)) != want:
                continue
            probe = j.fork()
            try:
                _endgame(probe, acc, read, cell7)
            except ValueError:  # pragma: no cover - not observed
                # The endgame refuses on the same two conditions the
                # derivation declined on; a raise here is a derivation bug.
                continue
            if probe.printed() != want:  # pragma: no cover - the acceptance
                # Never observed, but "seen to print" is the standard.
                continue
            return probe
    return None
