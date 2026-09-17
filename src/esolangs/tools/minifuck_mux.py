"""The Minifuck sculpted route: separate the rows, then fix them one by one.

The route that closes the four-input residue.  Weighting each input as it
lands puts every row at its own pointer position in closed form, and rounds of
``'<' * K + '[x' * K`` then fix the printed column from the highest row down.
"""

from functools import cache
from itertools import pairwise

from esolangs.tools.minifuck_pool import (
    _BASE,
    _POOL_CODES,
    _POOL_MASK,
    _POOL_WIDTH,
    _PROBE_WALK_OUT,
    _READS,
    _complement,
    _pool_slice,
    _try_print,
)
from esolangs.tools.minifuck_sim import (
    _MINIFUCK_INPUT,
    _clamp,
    _Joint,
    _runs,
    _Sim,
    _walk_to,
)

# ---------------------------------------------------------------------------
# The sculpted route: separate every row into its own pointer position, then
# fix the printed column one row at a time, highest position down.  Closes
# the four-input residue with every input embedded exactly once.
#
# **Separation** is closed form: ``setter(i); weight(2**(n-1-i)); pad`` per
# input.  :func:`_mux_weight` makes a bit worth ``k``: ``k`` restoring reads
# ``[x<[<`` with a one-cell rewind between compound to ``-k * bit`` (linear
# for k 1..8), so the pointer lands at ``c0 - sum(2**(n-1-i) * x_i)``,
# injective.  Two measured conditions: the bit must be fresh (one ``[x``
# between setter and gadget folds it into the prefix-XOR and every weight
# collapses to 1 -- the "wall" an earlier attempt hit; rightward pad 0..10
# preserves it), and gadgets must not overlap (weight ``k`` writes at most
# ``k - 3`` cells left; :func:`_mux_pad` clears that plus the deepest
# rewind's room; the ``2**(n-2) - 1`` threshold is sharp, misses below it
# are rows clamping at the floor).  Replaced four searches (pointer-census
# BFS, greedy aimed reads, beam, two-machine BFS): 2.8s at n=3, 15.0s at
# n=4, failing at n=5 after 191s.  This is 0.0007s at 4, 0.004s at 5.
#
# **Sculpting** fixes target cell ``C`` below every row.  One round
# ``'<' * K + '[x' * K``, ``K = b - C + 1``: the row at ``b`` rewinds to
# ``C - 1`` and flips ``C`` unconditionally; rows above ``b`` never write
# below their own rewind, so their read value is untouched; rows below
# pick up cascade debris (scrambled).  Fixing the highest disagreeing row
# strictly lowers the frontier: at most ``2**n`` rounds.  The pool code is
# a constant (:data:`_SCULPT_POOL_CODE`); the allowance and fall-through
# stay because the cap is what makes "a stall returns None" true.  The
# trailing ``x`` is the ``_FLIP`` lesson: a cascading last ``[`` sets skip.
#
# **Measured.**  All 3652 n=4 tables the deleted staged families missed build and
# print 16/16 rows, closing the arity at 64594 of 64594.  ~220ms per build
# for 43% shorter programs: the first ``(C, orientation, read)`` that prints
# (7ms) is a poor choice since a round costs ``3 * K + 1`` -- sampled n=4
# first-ascending 1046 chars, first-descending 700, min over all 594; XOR5
# 2511 -> 1174.  Two probe savings verified byte-identical.
#
# **No arity gate.**  All six refusal sites close uniformly in ``n`` (the
# generator tests, "Is ``_mux`` total?"), replacing the arity tuple with
# :data:`_MUX_MIN_ARITY`.  200 of 200 fully-essential n=5 tables print
# 32/32 at ~0.14s; two n=6 tables that used to raise emit 4040 and 3993
# chars in 41.6s and 53.8s; 448 of 448 rows correct at n=5,6,7.
# Last route in :func:`_solve`; a pool code
# refusing every ``(C, orientation, read)`` raises rather than sweeping.

# Pool codes were designed against ``_walk_to``'s uniform wake, marks to
# ~cell 14: scribbling there strands every probe (0 usable vs 14).  Eight
# writable cells between guard and embed are what let the searches finish;
# sealing them turned the n=4 separation from 15s into a failure.
_MUX_BASE = _BASE + 16
_MUX_GUARD = _MUX_BASE - 8

# No upper bound: the old ``(2, 3, 4, 5)`` tuple was a configuration gate,
# and the generator tests ("Is ``_mux`` total?") close all six ``None``
# sites with no residual ``n`` (affine injective separation via the 24-cell
# saturation margin and non-overlapping halving weights; rewind guard is an
# identity; round cap is window geometry; the pool probe reads only cells
# the initial walk freezes).  Two is the floor because ``_solve`` routes
# constants and projections to :func:`_degenerate` first.
_MUX_MIN_ARITY = 2

# One separation per arity, forked out.  A dict: the value is a mutable ``_Joint``.
_MUX_SEPARATED: dict[int, _Joint] = {}


def _mux_reference(n: int) -> _Joint:
    """Return a joint walked to the embed's start with nothing embedded yet.

    The tape :func:`_mux_separate` must leave untouched left of :data:`_MUX_GUARD`.
    """
    j = _Joint(n)
    _walk_to(j, _mux_start(n) - 1)
    return j


def _mux_intact(before: _Joint, after: _Joint) -> bool:
    """Whether every cell left of the guard survived, on every row."""
    return all(
        m.cells(_MUX_GUARD) == m0.cells(_MUX_GUARD)
        for m, m0 in zip(after.ms, before.ms, strict=True)
    )


def _mux_weight(k: int) -> str:
    """Return the gadget displacing a **fresh** setter bit by exactly ``-k``.

    ``k`` restoring reads ``[x<[<`` with one-cell rewinds compound to ``-k``
    times the bit (linear for k 1..8).  *Fresh*: one ``[x`` between the
    setter and this folds the bit into the prefix-XOR and every weight reads
    1.  Writes at most ``max(0, k - 3)`` cells left of the setter.
    """
    return ("[x<[<" + "<") * (k - 1) + "[x<[<" if k > 0 else ""


def _mux_weights(n: int) -> tuple[int, ...]:
    """Return the per-input weights: ``2**(n-1-i)``, so the sum is the row."""
    return tuple(2 ** (n - 1 - i) for i in range(n))


def _mux_pad(n: int) -> int:
    """Return the slack each gadget gets beyond the previous one's weight.

    Clears the ``k - 3`` reach and keeps the deepest rewind above cell 0;
    ``2**(n-2) - 1`` is sharp (n=4: pad 3 separates all 16; n=5: pad 7 closes
    it; below, rows clamp at the floor).  A shift, since mypy widens ``2 **``.
    """
    return max((1 << (n - 2)) - 1, 1)


def _mux_start(n: int) -> int:
    """Return where to lay the embed so no gadget writes left of the guard.

    The first gadget is the heaviest and reaches ``k - 2`` left of the bit
    (``k - 3`` from the setter); with ``start = _MUX_BASE + 2**(n-1) - offset``
    the ``2**(n-1)`` cancels and the leftmost write is
    ``_MUX_BASE - offset + 2`` at every arity, so
    ``offset = _MUX_BASE - _MUX_GUARD + 1`` (9) clears the guard by one.
    Derived, not tuned: every offset builds and larger is shorter (n=5 mean
    1443 -> 1383 for offsets 3..13), but one more lands on :data:`_MUX_GUARD`
    and :func:`_mux_intact` fails.  Applies only from five inputs.
    """
    return _MUX_BASE + max(0, (1 << (n - 1)) - (_MUX_BASE - _MUX_GUARD + 1))


def _mux_separate(n: int) -> _Joint | None:
    """Emit an embed leaving all ``2**n`` rows at distinct pointers.

    Setter, :func:`_mux_weight` on the fresh bit, then a pad, so the pointer
    ends at ``c0 - sum(2**(n-1-i) * x_i)``: affine with binary weights,
    hence injective.  Table-independent, cached per arity.  No right-pad:
    ``min(q) = start + (n-1) * (pad + 1) - 1`` clears the span by 30, 28, 28,
    39, 71, 151 cells at n=2..7 and grows.
    """
    if n in _MUX_SEPARATED:
        return _MUX_SEPARATED[n].fork()
    weights = _mux_weights(n)
    pad = _mux_pad(n)
    j = _Joint(n)
    _walk_to(j, _mux_start(n) - 1)
    for i, k in enumerate(weights):
        j.emit_setter(i)
        j.emit_weight(_mux_weight(k), k)
        if i + 1 < n:
            j.emit("[x" * (k + pad))
    # Checked before caching: a lost row would otherwise surface as an
    # unfixable table.  Neither fires at any arity (argued uniformly in the
    # generator tests); they guard against a future weighting.
    if any(m.dead for m in j.ms) or len(set(j.ptrs())) != 2**n:
        return None  # pragma: no cover - the construction separates by design
    if not _mux_intact(_mux_reference(n), j):
        return None  # pragma: no cover - the construction separates by design
    _MUX_SEPARATED[n] = j.fork()
    return j


#: The sculpting probe's pool code, a constant of the construction.  The
#: probe state is canonical: :func:`_mux_probe` emits ``x`` then clamps and
#: ``<`` never writes, so every probe has all pointers at 0, no skip, pool
#: region ``(0, 1, 1, 1, 1, 1, 1, 1)`` -- 2 distinct states in all (the two
#: ``cell7`` values) over 50688 probes at n=3, 200 tables at 4, 12 at 5.  No
#: pool code touches past cell 6 from there, and a round's rewind guard
#: ``rewind > min(ptrs) - _POOL_WIDTH`` keeps it out of the region.  So the
#: fifth code answers ``cell7 == 0`` everywhere and none answers 1.  Worth
#: ~0.3s on a warm n=5 build (3.1 -> 2.8s); the column derivation in
#: :func:`_mux_probe` is a different question.  :func:`_find_pool` answers
#: the unclamped derivation path via :data:`_POOL_CODE_OF` likewise.
_SCULPT_POOL_CODE = _POOL_CODES[4]


def _sculpt_pool_code(cell7: int) -> str | None:
    """Return the code a sculpting probe reaches, by :data:`_SCULPT_POOL_CODE`.

    ``test_sculpt_pool_code_matches_scan`` replays the replaced scan.
    """
    return _SCULPT_POOL_CODE if cell7 == 0 else None


def _canonical_endgame(j: _Joint, acc: int, *, direct: bool) -> None:
    """Print ``acc`` from the canonical pool state by the named orientation."""
    if acc < _POOL_WIDTH:
        raise ValueError("accumulator must sit past the pool")
    if any(
        m.dead or m.skip or m.ptr != 0 or (m.tape & _POOL_MASK) != _POOL_MASK ^ 1
        for m in j.ms
    ):
        raise AssertionError("the construction did not reach its canonical pool state")
    j.emit(_SCULPT_POOL_CODE)
    _walk_to(j, acc - 1)
    j.emit(_READS[1] if direct else _READS[0])
    j.emit("<" * (acc - (_POOL_WIDTH - 1)))
    for cell in range(_POOL_WIDTH):
        if len(set(j.col(cell))) != 1:
            raise AssertionError(f"pool cell {cell} is input-dependent")
    j.emit("[x.")


@cache
def _probe_frame(code: str, byte: int) -> tuple[int, int] | None:
    """Return ``(landed, parity)`` for ``code`` run from a converged row.

    Run twice with different junk above the pool region; None when they
    disagree or the region is written, a skip pending, the row dead or the
    pointer past the region.
    """
    frames = []
    for high in (0, (1 << 64) - 1):
        sim = _Sim(_POOL_WIDTH + _PROBE_WALK_OUT + 4)
        sim.tape = byte | (high << _POOL_WIDTH)
        sim.apply(_runs(code))
        if sim.dead or sim.skip or sim.ptr >= _POOL_WIDTH:
            return None
        if sim.tape >> _POOL_WIDTH != high:
            return None
        frames.append((sim.ptr, sim.tape & _POOL_MASK))
    if frames[0] != frames[1]:  # pragma: no cover - no code both reads and frames
        # Catches a code that *reads* above the region (the write is the
        # guard above).  The ``<[.x`` alphabet through length 8 produced a
        # writer (``.[[...[<``) and no reader; residual, not reachable.
        return None
    landed, low = frames[0]
    return landed, (low >> (landed + 1)).bit_count() & 1


def _sculpt_columns(j: _Joint, acc: int) -> tuple[int, ...] | None:
    """Return the probe column by the parity law, or None to fall back.

    After the pool code the cell at ``acc`` is the prefix-XOR carry, so a
    row's answer is the frame's parity XOR the parity of its cells
    ``8..acc``; valid while every row is alive and shares the window byte.
    """
    if acc <= _POOL_WIDTH:
        return None
    ms = j.ms
    byte = ms[0].tape & _POOL_MASK
    frame = _probe_frame(_SCULPT_POOL_CODE, byte)
    if frame is None:
        return None
    parity = frame[1]
    mask = ((1 << (acc + 1)) - 1) ^ _POOL_MASK
    column = []
    for m in ms:
        if m.dead or (m.tape & _POOL_MASK) != byte:
            return None
        column.append(parity ^ ((m.tape & mask).bit_count() & 1))
    return tuple(column)


def _mux_probe_sim(
    j: _Joint, acc: int, cell7: int
) -> tuple[tuple[int, ...], str] | None:
    """Run the probe by simulation: fork, absorb, clamp, set the pool, walk.

    The specification the parity law is held to, and the fallback.
    """
    probe = j.fork()
    probe.emit("x")  # absorb a pending skip so the clamp below is exact
    _clamp(probe)
    code = _sculpt_pool_code(cell7)
    if code is None:
        return None
    probe.emit(code)
    try:
        _walk_to(probe, acc - 1)
    except ValueError:  # pragma: no cover - not observed; as _printed_column
        # As in ``_printed_column``: ``_find_pool`` ignores ``walk_out``.
        # Not observed over 38144 sculpting rounds at n=2,3.
        return None
    return tuple(probe.col(probe.ms[0].ptr + 1)), code


def _mux_probe(
    j: _Joint, acc: int, cell7: int, hint: str | None = None
) -> tuple[tuple[int, ...], str] | None:
    """Return the column printed at ``acc`` and the pool code that got it.

    The code is :data:`_SCULPT_POOL_CODE` (the probe state is canonical);
    ``hint`` is accepted and ignored.  The column is :func:`_sculpt_columns`'s
    parity law, with :func:`_mux_probe_sim` as fallback; the scout compares
    the two live once per build.
    """
    del hint
    code = _sculpt_pool_code(cell7)
    if code is None:
        return None
    column = _sculpt_columns(j, acc)
    if column is None:
        return _mux_probe_sim(j, acc, cell7)
    return column, code


def _mux_sculpt(
    base: _Joint,
    truth_table: str,
    n: int,
    acc: int,
    cell7: int,
    *,
    direct: bool,
    hint: str | None = None,
) -> str | None:
    """Sculpt the printed column at one ``(C, orientation, read)``.

    Take the highest disagreeing row, flip its cell ``C`` with one round,
    repeat.  The cap is the frontier bound plus slack; a stall returns None.
    The joint is handed to :func:`_try_print`.
    """
    want = tuple(int(c) for c in truth_table)
    j = base.fork()
    for _ in range(2**n + 4):
        found = _mux_probe(j, acc, cell7, hint)
        if found is None:
            return None
        column, hint = found
        got = column if direct else _complement(column)
        disagree = [p for p, g, w in zip(j.ptrs(), got, want, strict=True) if g != w]
        if not disagree:
            break
        frontier = max(disagree)
        rewind = frontier - acc + 1
        if rewind > min(j.ptrs()) - _POOL_WIDTH:
            # The closest guard: 38144 rewinds at n=2,3 with margin 0..24,
            # so ``_mux_separate``'s padding is exactly enough at its tightest.
            return None  # pragma: no cover - not observed; margin reaches 0
        # Three runs, not one string: same template, but the two long runs
        # then go through ``_Sim.run_left``/``run_walk`` instead of per-char.
        j.emit("<" * rewind)
        j.emit("[x" * rewind)
        j.emit("x")
    else:
        # ``2**n + 4`` rounds, each fixing the frontier row; exceeding it
        # means a round undid a fix.  Not observed at n=2,3; this else is
        # the "stall returns None" contract.
        return None  # pragma: no cover - a round never undoes an earlier fix
    j.emit("x")
    _clamp(j)
    hit = _try_print(j, truth_table, acc)
    return None if hit is None else hit.template()


def _pascal_parity_row(n: int) -> int:
    """Return row ``n`` of Pascal's triangle modulo two as a bitvector.

    Lucas: the set positions are the submasks of ``n``, one shift per set bit.
    """
    row = 1
    bit = 1
    while bit <= n:
        if n & bit:
            row ^= row << bit
        bit <<= 1
    return row


def _mux_round_plan(
    tapes: list[int],
    ptrs: list[int],
    parities: list[int],
    want: list[int],
    acc: int,
    *,
    flip: int,
    guard: int,
    round_limit: int | None,
) -> tuple[list[int], int] | None:
    """Return the sculpt's rewinds and their cost by the Pascal inverse.

    A round fired at row ``h`` replaces a suffix by one plus its prefix XOR;
    its inverse is first difference, and in the product entry ``(i, q)`` is
    ``binomial(c[q], i-q) mod 2``, the bit test ``(i-q) & ~c[q] == 0``.  So
    the parity after every prior round is read directly, no replay.
    ``round_limit`` reproduces the scout's strict prune.
    """
    inverse_rows: list[int] = []
    selected_through: list[int] = []
    selected = 0
    bias = 0
    parity_functional = 0
    rewinds: list[int] = []
    cost = 0
    for i, (tape, base_parity, target) in enumerate(
        zip(tapes, parities, want, strict=True)
    ):
        inverse = 1 << i
        for q, count in enumerate(selected_through):
            distance = i - q
            if distance & ~count == 0:
                inverse ^= inverse_rows[q]
        inverse_rows.append(inverse)
        parity_functional ^= inverse

        local = (tape >> (acc - i)) & ((1 << (i + 1)) - 1)
        outside = base_parity ^ (local.bit_count() & 1)
        got = flip ^ outside ^ (((local ^ bias) & parity_functional).bit_count() & 1)
        if got != target:
            rewind = ptrs[i] - acc + 1
            round_cost = 3 * rewind + 1
            if rewind > guard or (
                round_limit is not None and cost + round_cost > round_limit
            ):
                return None
            rewinds.append(rewind)
            cost += round_cost
            bias ^= _pascal_parity_row(selected) << i
            selected += 1
        selected_through.append(selected)
    return rewinds, cost


def _mux_scout(
    base: _Joint,
    truth_table: str,
    n: int,
    accs: range,
    rewinds_out: dict[tuple[int, bool], list[int]] | None = None,
) -> tuple[tuple[int, bool, int] | None, bool]:
    """Price every ``(accumulator, orientation)`` sculpt without emitting.

    ``(winner, trusted)``: the shortest build in sweep order, or None;
    ``trusted`` False means the base defeats the summary.  The sculpt loop is
    solved by its Pascal inverse (:func:`_mux_round_plan`); the endgame's
    lengths are frame constants.  Guard and refusal sites are reproduced one
    for one; a combination is abandoned only when its running length
    strictly exceeds the best completed.  The first column is computed both
    ways and a disagreement distrusts the scout.  ``rewinds_out`` collects
    each combination's rewinds for :func:`_mux_plan_tail`.
    """
    del n  # the Pascal inverse has no arity-specific step
    ms = base.ms
    if any(m.dead or m.skip for m in ms):
        return None, False
    byte = ms[0].tape & _POOL_MASK
    if any((m.tape & _POOL_MASK) != byte for m in ms):
        return None, False
    frame = _probe_frame(_SCULPT_POOL_CODE, byte)
    if frame is None:
        return None, False
    c_probe = frame[1]
    codes = tuple(_POOL_CODES)
    slice0 = _pool_slice(codes, 0, skip=False)
    # Per orientation: ``_find_pool``'s code, its landing, and the walk-out
    # parity; None when no code answers (= ``_derive_column`` None).
    endgames: dict[int, tuple[int, int, int] | None] = {}
    for cell7 in (0, 1):
        chosen = slice0.get((byte, cell7))
        if chosen is None:
            endgames[cell7] = None
            continue
        end_frame = _probe_frame(codes[chosen[0]], byte)
        if end_frame is None or end_frame[0] != chosen[1]:
            return None, False
        endgames[cell7] = (len(codes[chosen[0]]), chosen[1], end_frame[1])

    want = tuple(int(ch) for ch in truth_table)
    ptrs = base.ptrs()
    rows = len(ptrs)
    highest, lowest = max(ptrs), min(ptrs)
    order = sorted(range(rows), key=lambda r: ptrs[r], reverse=True)
    ptrs_s = [ptrs[r] for r in order]
    want_s = [want[r] for r in order]
    if any(a - b != 1 for a, b in pairwise(ptrs_s)):
        return None, False
    tapes_s = [ms[r].tape for r in order]
    base_len = len(base.template())
    guard = lowest - _POOL_WIDTH
    checked = False
    best: int | None = None
    lengths: dict[tuple[int, bool], int] = {}
    # Largest accumulator first: rounds cost ``3 * K + 1``, ``K = frontier
    # - acc + 1``, so cheap builds price first and the strict-abort prunes
    # the rest.  The order prices; it never picks.
    parities: list[int] | None = None
    for acc in reversed(accs):
        # Row parity over cells ``8..acc``; stepping ``acc`` down flips it
        # by the dropped cell.
        if parities is None:
            pmask = (1 << (acc - _POOL_WIDTH + 1)) - 1
            parities = [((t >> _POOL_WIDTH) & pmask).bit_count() & 1 for t in tapes_s]
        else:
            parities = [
                par ^ ((t >> (acc + 1)) & 1)
                for par, t in zip(parities, tapes_s, strict=True)
            ]
        for direct in (True, False):
            g = 0 if direct else 1
            # ``_try_print``'s trial order: a read matches when its polarity
            # cancels the probe/endgame parity offset.
            matched = None
            for read, cell7 in (
                (_READS[0], 0),
                (_READS[0], 1),
                (_READS[1], 0),
                (_READS[1], 1),
            ):
                end = endgames[cell7]
                if end is None:
                    continue
                offset = g ^ c_probe ^ end[2]
                if offset == (0 if read == _READS[1] else 1):
                    matched = (read, end)
                    break
            if matched is None:
                # No read prints this orientation; ``_try_print`` would refuse.
                continue
            read, (code_len, landed, _) = matched
            # Fixed cost outside the rounds: ``x``, clamp, pool code, walk
            # out, read, rewind, ``[x.``.
            total = (
                base_len
                + 1
                + (highest + 1)
                + code_len
                + 2 * (acc - 1 - landed)
                + len(read)
                + (acc - _POOL_WIDTH + 1)
                + 3
            )
            flip = c_probe ^ g
            if not checked:
                simmed = _mux_probe_sim(base, acc, 0)
                fast = _sculpt_columns(base, acc)
                if simmed is None or fast is None or fast != simmed[0]:
                    return None, False
                checked = True
            planned = _mux_round_plan(
                tapes_s,
                ptrs_s,
                parities,
                want_s,
                acc,
                flip=flip,
                guard=guard,
                round_limit=None if best is None else best - total,
            )
            if planned is not None:
                pending, round_cost = planned
                total += round_cost
                lengths[(acc, direct)] = total
                if rewinds_out is not None:
                    rewinds_out[(acc, direct)] = pending
                if best is None or total < best:
                    best = total
    if best is None:
        return None, True
    for acc in accs:
        for direct in (True, False):
            if lengths.get((acc, direct)) == best:
                return (acc, direct, best), True
    raise AssertionError("the scout lost its own winner")  # pragma: no cover


def _mux_plan_tail(base: _Joint, acc: int, rewinds: list[int]) -> tuple[str, str]:
    """Spell the fixed sculpt from its derived rewinds.

    Every part is a frame constant.  Returns ``(rounds, suffix)``;
    :func:`_mux` replays it over every row before shipping.
    """
    byte = base.ms[0].tape & _POOL_MASK
    if byte != _POOL_MASK ^ 1:  # pragma: no cover - separation fixes the byte
        raise AssertionError("the separation changed the canonical pool byte")
    frame = _probe_frame(_SCULPT_POOL_CODE, byte)
    if frame is None:  # pragma: no cover - the fixed code has a frame
        raise AssertionError("the fixed pool code has no frame")
    landed, parity = frame
    if parity != 1:  # pragma: no cover - the direct rule depends on this offset
        raise AssertionError("the fixed pool code changed its parity")
    highest = max(base.ptrs())
    rounds: list[str] = []
    for rewind in rewinds:
        rounds.append("<" * rewind)
        rounds.append("[x" * rewind)
        rounds.append("x")
    suffix = "".join(
        (
            "x",
            "<" * (highest + 1),
            _SCULPT_POOL_CODE,
            "[x" * (acc - 1 - landed),
            _READS[1],
            "<" * (acc - (_POOL_WIDTH - 1)),
            "[x.",
        )
    )
    return "".join(rounds), suffix


def _mux_replays(
    base: _Joint, rewinds: list[int], suffix: str, truth_table: str
) -> bool:
    """Whether the spelled build really prints the table, row by row.

    The module-wide acceptance: rounds through :meth:`_Sim.run_rewinds`,
    the endgame through the parsed runs.
    """
    probe = base.fork()
    for m in probe.ms:
        m.run_rewinds(rewinds)
    probe.emit(suffix)
    return probe.printed() == list(truth_table)


_MUX_PRESERVE_RIGHT = "[x<" * 3 + "[x"


def _mux_init_bits(bits: str) -> str:
    """Write ``bits`` on fresh cells in one left-to-right pass.

    Each tile leaves the next cell preset to one; callers append a zero guard.
    """
    parts: list[str] = []
    zero_seen = False
    for bit in bits:
        if not zero_seen:
            if bit == "1":
                parts.append("[")
            else:
                parts.append("[<[x")
                zero_seen = True
        elif bit == "0":
            parts.append("[x")
        else:
            parts.append("[x<[")
    return "".join(parts)


def _mux_lookup(truth_table: str, n: int) -> str:
    """Return the linear preloaded-strip mux.

    ``[x<[x<[x<[x`` advances one cell and restores a cell; repeating it
    crosses the preloaded controls unchanged, and one left run maps row
    ``r`` to control ``r``.  With zero controls the printed row is
    ``popcount(r)`` plus the separator phase; a control flips every row but
    its own and the sentinel flips all, so the selected output is the bit.
    """
    total = len(truth_table)
    phase = (n ^ (_mux_start(n) - _MUX_BASE) ^ 1) & 1
    baseline = [((row.bit_count() ^ phase) & 1) for row in range(total)]
    controls = [
        int(bit) ^ base for bit, base in zip(truth_table, baseline, strict=True)
    ]
    sentinel = sum(controls) & 1

    field_lo = _MUX_GUARD + 4
    field = "".join(map(str, reversed(controls))) + str(sentinel)
    parts = ["[x" * (field_lo - 1), _mux_init_bits(field + "0")]
    parts.append("<" * (field_lo + len(field) + 3))

    field_end = field_lo + len(field) + 1
    parts.append(_MUX_PRESERVE_RIGHT * field_end)
    start = _mux_start(n) + 4 * total
    parts.append("[x" * (start - 1 - field_end))

    weights = _mux_weights(n)
    for i, weight in enumerate(weights):
        parts.append(_MINIFUCK_INPUT)
        parts.append(_mux_weight(weight))
        if i + 1 < n:
            # The next gadget reaches ``next_weight - 2`` left of its setter;
            # this pad puts it on fresh tape.  Pads sum to T/2-1, not T/4 each.
            parts.append("[x" * (weight + weights[i + 1] - 1))

    pmax = start + 3 * total // 2 - 3
    field_high = field_lo + total - 1
    parts.extend(("<" * (pmax - field_high + 1), "[x"))
    parts.append("<" * (field_high + 1))

    byte = _POOL_MASK ^ 1
    frame = _probe_frame(_SCULPT_POOL_CODE, byte)
    if frame is None:  # pragma: no cover - fixed arity-free pool frame
        raise AssertionError("the fixed pool code has no frame")
    landed, parity = frame
    if parity != 1:  # pragma: no cover - lookup polarity uses this frame
        raise AssertionError("the fixed pool code changed its parity")
    acc = pmax + 8
    parts.extend(
        (
            _SCULPT_POOL_CODE,
            "[x" * (acc - 1 - landed),
            _READS[1],
            "<" * (acc - (_POOL_WIDTH - 1)),
            "[x.",
        )
    )
    return "".join(parts)


def _mux_sweep(base: _Joint, truth_table: str, n: int, accs: range) -> str | None:
    """Sculpt every combination for real and keep the shortest build.

    The specification :func:`_mux_scout` is held to; the seed probe settles
    the orientations (``cell7 == 1`` answers to no code).
    """
    best: str | None = None
    for acc in accs:
        for cell7 in (0, 1):
            seed = _mux_probe(base, acc, cell7)
            if seed is None:
                continue
            for direct in (True, False):
                built = _mux_sculpt(
                    base, truth_table, n, acc, cell7, direct=direct, hint=seed[1]
                )
                if built is not None and (best is None or len(built) < len(best)):
                    best = built
    return best


def _mux(truth_table: str, n: int) -> str | None:
    """Build the table with the linear preloaded-strip rule."""
    if n < _MUX_MIN_ARITY:
        return None
    return _mux_lookup(truth_table, n)
