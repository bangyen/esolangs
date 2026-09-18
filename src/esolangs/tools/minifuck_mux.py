"""The Minifuck mux: the preloaded-strip lookup, linear in the table.

Each input is weighted as it lands so every row selects its own control
cell; the strip is preloaded with the table and one left run reads it.
The sculpted route this module used to hold (separate, then fix rows one by
one) and its staged predecessor were deleted: nothing shipped reached them.
"""

from functools import cache

from esolangs.tools.minifuck_pool import (
    _BASE,
    _POOL_CODES,
    _POOL_MASK,
    _POOL_WIDTH,
    _PROBE_WALK_OUT,
    _READS,
)
from esolangs.tools.minifuck_sim import (
    _MINIFUCK_INPUT,
    _Joint,
    _runs,
    _Sim,
    _walk_to,
)

# Weighting is closed form: ``setter(i); weight(2**(n-1-i)); pad`` per input,
# so the pointer lands at ``c0 - sum(2**(n-1-i) * x_i)``, injective.  Two
# measured conditions: the bit must be fresh (one ``[x`` between setter and
# gadget folds it into the prefix-XOR and every weight collapses to 1), and
# gadgets must not overlap (weight ``k`` writes at most ``k - 3`` cells
# left).  Replaced four searches: 15.0s at n=4, failing at n=5 after 191s;
# this is 0.004s at 5.  448 of 448 rows correct at n=5,6,7.

# Pool codes were designed against ``_walk_to``'s uniform wake, marks to
# ~cell 14; eight writable cells between guard and embed are what the
# construction needs, and sealing them turned n=4 from 15s into a failure.
_MUX_BASE = _BASE + 16
_MUX_GUARD = _MUX_BASE - 8

# No upper bound: every ``None`` site closes uniformly in ``n`` (the
# generator tests, "Is ``_mux`` total?").  Two is the floor because
# ``_solve`` routes constants and projections to :func:`_degenerate` first.
_MUX_MIN_ARITY = 2


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


def _mux(truth_table: str, n: int) -> str | None:
    """Build the table with the linear preloaded-strip rule."""
    if n < _MUX_MIN_ARITY:
        return None
    return _mux_lookup(truth_table, n)
