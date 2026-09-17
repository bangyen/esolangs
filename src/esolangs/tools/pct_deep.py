"""The %^2^-1 deep-band route.

The construction that lifts the ceiling every other route runs into: ``e``
prints ``chr(acc & 0xFF)``, so a row only has to be *congruent* to the digit
rather than equal to it, and the weights are multiples of :data:`_BAND_UNIT`.
"""

from functools import cache
from itertools import chain

from esolangs.tools.pct_codes import (
    _BYTE_ONE,
    _BYTE_ZERO,
    _LIMIT,
    _affine_code,
    _apply,
    _even_width_for,
    _sub_code,
    _sub_of_width,
)
from esolangs.tools.pct_ladder import _header, _runs

#: The band construction's weights are multiples of this, so every row starts
#: congruent mod 256 and the residue of a band is decided by one translation.
_BAND_UNIT = 256

#: Where a band construction parks its survivors after each wipe: positive, so
#: the next stage's translate can still push them over the limit, and far enough
#: under it that parking itself never clamps.
_BAND_PARK = 2000


#: How far the deep band's weights range, in whole residue systems.  Six is
#: where the measured coverage stops improving at four inputs; the search is
#: over weightings rather than programs, so this bounds a derivation's input,
#: not a program space.
_DEEP_CAP = 6

#: Where the deep band parks its survivors between cuts.  Positive and under
#: the limit, so a later cut's translation can still carry them across it.
_DEEP_PARK = 2000


def _deep_values(n: int, units: tuple[int, ...], mask: int) -> list[int]:
    """Row values for a weighting, with ``mask`` naming the complemented inputs.

    A weight applies when input ``k`` differs from its mask bit, so ``mask``
    relabels which corner of the cube carries the largest sum.  With
    nonnegative weights alone the all-ones row is always on top and the
    all-zeros row always at the bottom, which fixes most of the run structure
    a table can present; complementing an input is free -- the setter's two
    branches swap -- and it is what frees the order.
    """
    return [
        sum(
            u * _BAND_UNIT * (((r >> (n - 1 - k)) & 1) ^ ((mask >> k) & 1))
            for k, u in enumerate(units)
        )
        for r in range(2**n)
    ]


def _deep_plan(truth_table: str, n: int, values: list[int]) -> str | None:
    """Derive a deep band's body for one value vector, or ``None``.

    The ladder is built by *subtraction*, so every row sits at ``-sum``:
    negative, where the over-3003 reset cannot fire however large the weights
    are.  That is the whole escape from a positive ladder's unit budget, which
    exists only because building upward makes every row sum sit under the
    limit at once.

    Rows may share a value provided they share a class.  A cut erases -- every
    row it wipes lands on zero together, whatever the gaps between them were --
    so only the boundaries *between* runs need a full residue system, and the
    span a table costs is set by its number of runs rather than by ``2**n``.

    **None of the refusals below fire from the caller.**  The deep band tests
    each weighting for *legality* -- that every collision it causes joins rows
    of one class -- and a legal weighting has never been seen to fail to
    schedule.  That is what lets the search test legality instead of running
    this planner per candidate (commit 0921f249, which measured 63274 legal
    weightings inside the span budget with zero refusals), and the call site
    already carries a ``pragma: no cover`` saying so.  Re-measured here:
    n=3 exhaustive, 254 tables, 170592 legal weightings, 0 refusals; n=4
    sampled, 200 tables, 26016 legal, 0 refusals.

    So the ``continue``/``break``/``return None`` arms are the planner's own
    contract for a caller that has *not* screened its input, and they stay
    for that reason -- a planner that silently returned a body for an illegal
    weighting would emit a program computing the wrong function.
    """
    rows = range(2**n)
    groups: dict[int, set[str]] = {}
    for row in rows:
        groups.setdefault(values[row], set()).add(truth_table[row])
    # Two rows sharing a value can never be told apart again, so a collision
    # across classes would emit a program computing the wrong function.
    if any(len(classes) > 1 for classes in groups.values()):
        return None

    order = sorted(rows, key=lambda r: values[r], reverse=True)
    anchor = order[-1]
    live = _BYTE_ONE if truth_table[anchor] == "1" else _BYTE_ZERO

    for prefix in range(2**n):
        if prefix and len({truth_table[r] for r in order[:prefix]}) > 1:
            break  # pragma: no cover - screened by legality
        rest = order[prefix:]
        if not rest:
            break  # pragma: no cover - screened by legality
        if max(values[r] for r in rest) - min(values[r] for r in rest) > _LIMIT:
            continue  # pragma: no cover - screened by legality
        high = _LIMIT - max(values[r] for r in rest)
        low = (_LIMIT - min(values[r] for r in order[:prefix]) + 1) if prefix else 0
        low = max(low, 0)
        if low > high:
            continue  # pragma: no cover - screened by legality
        drop = next(
            (
                d
                for d in range(low, min(high, low + _BAND_UNIT) + 1)
                if _sub_code(d) is not None
            ),
            None,
        )
        if drop is None:
            continue  # pragma: no cover - screened by legality
        body = _deep_body(truth_table, n, values, order, anchor, live, prefix, drop)
        # The first prefix that spells a drop spells a body too, so the
        # loop always returns on that pass rather than trying another.
        if body is not None:  # pragma: no branch
            return body
    return None  # pragma: no cover - screened by legality


def _deep_body(
    truth_table: str,
    n: int,
    values: list[int],
    order: list[int],
    anchor: int,
    live: int,
    prefix: int,
    drop: int,
) -> str | None:
    """Spell one deep-band schedule, or ``None`` if a stage will not close."""
    rows = range(2**n)
    dropped = _sub_code(drop) if drop else ""
    if dropped is None:  # pragma: no cover - the caller chose a spellable drop
        return None
    # The ladder subtracted, so one ``p`` turns the order positive; the rows
    # the drop carried past the limit are wiped by the next command's reset.
    body = dropped + "p"
    # Rows collapse onto their runs' values -- eleven for parity-10, never
    # more than the span budget allows -- so each code runs once per value,
    # not once per row.
    moved = {-v: _apply(-v, dropped + "p") for v in set(values)}
    current = {r: moved[-values[r]] for r in rows}
    if {r for r in rows if current[r] > _LIMIT} != set(order[:prefix]):
        return None  # pragma: no cover - screened by legality
    cleared = set(order[:prefix])
    for row in cleared:
        # Empty from the screened caller: a legal weighting is planned at
        # ``prefix == 0`` -- measured over every table at two and three
        # inputs, 1332 bodies, all of them prefix 0 -- so nothing is carried
        # past the limit and there is nothing to clear.  The loop is the
        # planner's own handling of a prefix a wider caller could ask for.
        current[row] = 0  # pragma: no cover - screened by legality

    live_order = [r for r in order if r not in cleared]
    cuts = [
        i
        for i in range(1, len(live_order))
        if truth_table[live_order[i]] != truth_table[live_order[i - 1]]
    ]
    for cut in cuts:
        wipe = [live_order[i] for i in range(cut) if live_order[i] not in cleared]
        keep = [live_order[i] for i in range(cut, len(live_order))]
        if not wipe or len({truth_table[r] for r in wipe}) > 1:
            return None  # pragma: no cover - screened by legality
        low = _LIMIT - min(current[r] for r in wipe) + 1
        high = _LIMIT - max(current[r] for r in keep)
        if low > high or low <= 0:
            return None  # pragma: no cover - screened by legality
        band = _BYTE_ONE if truth_table[wipe[0]] == "1" else _BYTE_ZERO
        # A wiped band thereafter takes the same translations as the survivors,
        # so the parking cancels from their gap and one congruence fixes the
        # cut: the translation is solved, not searched.
        wanted = (live - band - current[anchor]) % _BAND_UNIT
        up = low + ((wanted - low) % _BAND_UNIT)
        if up > high:
            return None  # pragma: no cover - screened by legality
        raise_code = _affine_code(1, up)
        if raise_code is None:
            return None  # pragma: no cover - screened by legality
        lifted = {v: _apply(v, raise_code + "s") for v in set(current.values())}
        raised = {r: lifted[v] for r, v in current.items()}
        down = _DEEP_PARK - max(raised.values())
        park = _affine_code(1, down)
        if park is None:
            return None  # pragma: no cover - screened by legality
        lowered = {v: _apply(v, park) for v in set(raised.values())}
        parked = {r: lowered[v] for r, v in raised.items()}
        if max(parked.values()) > _LIMIT:
            return None  # pragma: no cover - screened by legality
        body += raise_code + "s" + park
        current = parked
        cleared.update(wipe)

    base = (live - current[anchor]) % _BAND_UNIT
    # Nearest zero first: a shift is spelled one character per two units, so
    # taking the smallest keeps the program short.  An earlier version scanned
    # from -80 residue systems up and emitted the first that worked, which is a
    # ten-thousand-character run of ``s``.
    for shift in sorted((base + _BAND_UNIT * reps for reps in range(-8, 9)), key=abs):
        tail = _affine_code(1, shift)
        if tail is None:
            continue  # pragma: no cover - screened by legality
        shifted = {v: _apply(v, tail) for v in set(current.values())}
        printed = {r: shifted[v] for r, v in current.items()}
        # A band reaching here has a working shift among the seventeen, so
        # the first spellable tail prints and the loop returns.
        if all(  # pragma: no branch
            (printed[r] & 0xFF) == (_BYTE_ONE if truth_table[r] == "1" else _BYTE_ZERO)
            for r in rows
        ):
            return body + tail + "e"
    return None  # pragma: no cover - screened by legality


def _deep_setters(
    units: tuple[int, ...], mask: int
) -> tuple[tuple[str, str], ...] | None:
    """Spell one setter per input, both branches at a common width."""
    setters = []
    for index, unit in enumerate(units):
        amount = unit * _BAND_UNIT
        if amount == 0:
            setters.append(("", ""))
            continue
        width = _even_width_for(amount)
        if width is None:  # pragma: no cover - every multiple of 256 spells
            return None
        code = _sub_of_width(amount, width)
        if code is None:  # pragma: no cover - the width just spelled it
            return None
        hold = "p" * width
        # The hold branch is ``pp`` repeated, two negations composing to the
        # identity, so both branches run the same number of commands and no
        # program leaks its inputs through ``len()``.
        setters.append((hold, code) if not (mask >> index) & 1 else (code, hold))
    return tuple(setters)


@cache
def _deep_weightings(n: int, *, positive: bool = False) -> tuple[tuple[int, ...], ...]:
    """Return the unit vectors worth trying, cheapest span first.

    Ordered by the span they cost, then flattest, which is the order the
    emitted program's length follows.  Vectors whose span exceeds the limit
    are dropped rather than tried: a weighting is measured in whole residue
    systems, so ``sum(units) * 256`` has to fit under 3003 and a sum past
    ``3003 // 256 == 11`` cannot schedule whatever the table looks like.
    That is not a heuristic -- every weighting observed to fail while its
    collisions were legal failed exactly here, at sum 12, span 3072.

    The enumeration backtracks on the remaining sum budget rather than
    filtering ``(cap + 1) ** n`` products -- 282M walked tuples at ten
    inputs against the 343K that survive -- and the sort key is a total
    order, so generation order cannot show through: same set, same tuple.

    ``positive`` drops every vector with a zero unit *before* it is walked.
    The band's full screen skips those anyway, so the tested sequence is
    the same; what changes is the walk, 621K tuples at eleven inputs
    against the one all-ones vector the screened regime ever reaches.
    """
    budget = _LIMIT // _BAND_UNIT
    units = [0] * n
    by_sum: list[list[tuple[int, ...]]] = [[] for _ in range(budget + 1)]
    floor = 1 if positive else 0

    def fill(index: int, left: int) -> None:
        # Every later input still needs its floor, so the unit stops short.
        for unit in range(floor, min(_DEEP_CAP, left - floor * (n - 1 - index)) + 1):
            units[index] = unit
            if index + 1 == n:
                by_sum[budget - left + unit].append(tuple(units))
            else:
                fill(index + 1, left - unit)
        units[index] = 0

    fill(0, budget)
    by_sum[0].clear()  # the all-zero tuple, the one sum-0 composition
    for bucket in by_sum:
        bucket.sort(key=lambda u: (max(u), u))
    return tuple(chain.from_iterable(by_sum))


def _deep_band(truth_table: str, n: int) -> str | None:
    """Build a deep-band template, or ``None`` if no weighting schedules it.

    This is the band shape with the two restrictions that bounded it removed.
    A positive ladder caps its weights at ``3003 // 256 == 11`` units, because
    every row sum has to sit under the limit at once; four inputs would need
    ``2**4 - 1 == 15`` and there is no weighting at all.  Here the ladder is
    negative -- nothing resets below zero -- so the unit budget does not
    exist, and rows are allowed to collide when they share a class, which
    prices a table's span by its number of runs instead of by ``2**n``.
    Parity rides the popcount ladder, every weight one, and so costs ``n``
    units rather than ``2**n - 1``.

    Weightings are tried in order of the span they cost -- which is the sum of
    the units, since each is a multiple of 256 -- so the emitted program is the
    shortest this construction builds rather than the first that schedules.
    What is *tested* per weighting is legality rather than schedulability:
    a collision is survivable exactly when it joins rows of one class, and a
    weighting whose collisions are all legal has never failed to schedule
    (63274 checked inside the span budget, none refused).  So the planner
    runs once, at the end, instead of once per candidate -- and the budget
    itself is derived rather than tuned, since every legal weighting observed
    to fail did so with ``sum(units) * 256`` past the limit.
    Ties go to the *flattest* weighting first, largest unit smallest: a table's
    span is set by its number of runs, and an even weighting is what collapses
    rows into runs.  Parity is the extreme case, built by the popcount ladder
    with every unit one, and ordering by ``max`` is what finds it immediately
    rather than after every degenerate weighting that ignores an input.

    Above four inputs the enumeration is **screened** rather than run.  Its
    own budget says why: keeping all rows distinct needs a span of
    ``(2**n - 1) * 256``, which is 3840 at four inputs -- close enough to
    the 3003 limit that enough weightings survive -- but 7936 at five, so
    every weighting there collides some rows and only a table whose
    structure tolerates the forced collisions builds.  In practice that
    means the symmetric tables, which the popcount ladder serves because
    its collisions are exactly the rows of equal popcount.  Measured: 0 of
    8 random five-input tables build -- about 18 seconds each to prove on
    the old product enumeration, about 60ms now that zero-unit weightings
    skip -- while parity-5 and majority-5 build in 0.14s.  The check stays
    either way: what builds is part of the contract, and the screen is
    what pins it to the symmetric tables rather than to whatever shorter
    program the enumeration occasionally finds.
    """
    if n > _LIMIT // _BAND_UNIT:
        # Each unit prices a whole residue system, so even the all-ones
        # weighting costs ``n * 256`` of span and the budget tops out at
        # eleven inputs.  A zero unit cannot rescue a table here either:
        # only symmetric tables pass the screen below, and a symmetric
        # table that ignores an input is constant -- which the cascade
        # already served.  Refusing up front skips the sum-bounded
        # enumeration below -- a million-tuple walk at thirteen inputs
        # whose every survivor the zero-unit argument rejects.
        return None
    if n > 4 and any(
        len({truth_table[r] for r in range(2**n) if bin(r).count("1") == pop}) > 1
        for pop in range(n + 1)
    ):
        return None
    # A coordinate some row flips across a class boundary -- a singleton
    # difference vector -- totals ``±units[k]`` under every mask, so a
    # weighting with a zero unit there is illegal at all masks and can be
    # skipped without testing any.  Every non-constant symmetric table has
    # all ``n`` singletons (any coordinate can carry a class-boundary bit
    # flip), and that is everything past the screen above, so past four
    # inputs the catalogue is walked without the zero-unit vectors at all.
    # Parity is the extreme case again: all 24219 weightings ordered before
    # the popcount ladder at nine inputs have a zero unit, so the ladder is
    # the first weighting *tested*.
    size = 2**n
    singles = {
        k
        for k in range(n)
        if any(
            truth_table[r] != truth_table[r | 1 << (n - 1 - k)]
            for r in range(size)
            if not r & 1 << (n - 1 - k)
        )
    }
    full_screen = len(singles) == n
    for units in _deep_weightings(n, positive=full_screen):
        if not full_screen and any(not units[k] for k in singles):
            continue
        for mask in range(2**n):
            # Legality decides the weighting; the schedule then follows.  A
            # weighting whose collisions all join rows of one class has never
            # been observed to fail here -- 63274 legal weightings inside the
            # span budget were scheduled without one refusal -- so this test
            # replaces planning as the thing being searched for, and the plan
            # below runs once rather than once per candidate.  Legal means
            # every weighted value is class-pure, read off the values
            # directly in ``T * n`` steps; the same predicate over the
            # cross-class difference vectors, whose enumeration walks
            # ``T ** 2`` row pairs, is the test suite's oracle for it.
            values = _deep_values(n, units, mask)
            classes: dict[int, str] = {}
            if any(
                classes.setdefault(value, cls) != cls
                for value, cls in zip(values, truth_table, strict=True)
            ):
                continue
            body = _deep_plan(truth_table, n, values)
            if body is None:  # pragma: no cover - legality implies a schedule
                continue
            setters = _deep_setters(units, mask)
            if setters is None:  # pragma: no cover - a planned weighting spells
                continue
            return _header(setters) + _runs(setters) + body
    return None
