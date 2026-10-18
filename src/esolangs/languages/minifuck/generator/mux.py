"""The Minifuck mux: the preloaded-strip lookup, linear in the table.

Each input is weighted as it lands so every row selects its own control
cell; the strip is preloaded with the table and one left run reads it.
"""

from functools import cache
from itertools import pairwise

from esolangs.languages.minifuck.generator.pool import (
    _BASE,
    _POOL,
    _POOL_MASK,
    _POOL_WIDTH,
    _PROBE_WALK_OUT,
    _READS,
)
from esolangs.languages.minifuck.generator.sim import (
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
# ~cell 14.  The pool is cells 0..7; the guard is the first cell past it and
# gadgets write only to its right.  The cells right of it must stay writable
# (sealing eight of them turned n=4 from 15s into a failure).  The guard was
# cell 24; at 8, no length grows and 175,828 of 177,728 sampled outputs
# shrink (n=2..11, up to 231 characters), and the n=3 and n=4 starts drop too.
_MUX_GUARD = _POOL_WIDTH

# Where the control field starts.  Its place changes no length, but moving it
# with the guard grew wrapped n=3 and n=4 outputs by a character.
_MUX_FIELD = _BASE + 12

# Constants and unary projections use the standing column instead.
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
    (``k - 3`` from the setter), so with ``start = 2**(n-1) + _MUX_GUARD - 1``
    the leftmost write is ``_MUX_GUARD + 1`` at every arity.  Derived, not
    tuned: lower is shorter, one lower writes on the guard.  Two inputs
    would start inside the field, so they start where the embed clears it.
    """
    return max((1 << (n - 1)) + _MUX_GUARD - 1, _MUX_FIELD + 3 - 3 * (1 << n))


#: Where the pool code parks the pointer.  The tail's ``[x`` walk complements
#: the prefix-XOR of cells above it, so cells ``0..4`` must already read the
#: pool and the window above must be ``1, 0, 0`` (every walked cell then
#: reads 0 and the window parity, 1, carries into the accumulator).  Landings
#: 2..4 construct; 5 and 6 cannot, cell 7 only ever gets a carry.
_SCULPT_LANDED = 4


def _sculpt_pool_code(landed: int = _SCULPT_LANDED) -> str:
    """Return the code taking the canonical pool state to its frame at ``landed``.

    Start ``(0, 1, 1, 1, 1, 1, 1, 1)``, pointer 0.  A ``[`` complements the
    cell it crosses and advances; crossing a one clears it, flips the cell
    above and owes a skip.  The pointer moves right only by crossing, so each
    of cells 1..6 is crossed once (when it must flip) or twice (``[<`` back
    over it then ``[`` again, when it must not).  A carry's skip eats the next
    ``<``: ``[<`` after a clearing cross, ``[<<`` when stepping back.  Cell 7
    is never crossed (a clear there would carry into the accumulator); it is
    only checked, and the pointer then walks back to ``landed``.  Replaced a
    found string; 16 characters either way.
    """
    target = [*_POOL[: landed + 1], 1, *([0] * (_POOL_WIDTH - landed - 2))]
    cells = [0] + [1] * (_POOL_WIDTH - 1)
    parts: list[str] = []
    for j in range(1, _POOL_WIDTH - 1):
        crossings = 1 if cells[j] != target[j] else 2
        for k in range(crossings):
            cleared = cells[j]
            cells[j] ^= 1
            cells[j + 1] ^= cleared
            # The skip owed by a clear eats one ``<``; stepping back needs one more.
            parts.append("[" + "<" * (cleared + (k + 1 < crossings)))
    if cells != target:  # pragma: no cover - holds for landed 2..4
        raise AssertionError("the pool cannot be sculpted to that frame")
    return "".join(parts) + "<" * (_POOL_WIDTH - 2 - landed)


_SCULPT_POOL_CODE = _sculpt_pool_code()


#: The relay leaves the pointer at 6 for a one, 7 for a zero, over pool
#: ``00110000`` and a set cell 8, so a bare ``.`` prints ``'1'`` or ``'0'``.
_PRINT = "."


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
    j.emit(_PRINT)


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


def _mux_init_bits(bits: str, *, paired: bool = False) -> str:
    """Write ``bits`` on fresh cells in one left-to-right pass.

    Each tile leaves the next cell preset to one; callers append a zero guard.
    ``paired`` adds comments only to leading fresh-one writes.
    """
    parts: list[str] = []
    zero_seen = False
    for bit in bits:
        if not zero_seen:
            if bit == "1":
                parts.append("[x" if paired else "[")
            else:
                parts.append("[<[x")
                zero_seen = True
        elif bit == "0":
            parts.append("[x")
        else:
            parts.append("[x<[")
    return "".join(parts)


#: An ignored input's run that equals one pad step ``[x`` under either fill,
#: from any state whose two cells right of the pointer are zero.  Checked on
#: all 1024 windows of cells p-5..p+4: equal on exactly the 256 with p+1 and
#: p+2 zero.
_GAP_BLOCK = "[[<[" + _MINIFUCK_INPUT + "<[x<[[x<"


def _mux_pads(weights: tuple[int, ...], gaps: tuple[int, ...]) -> tuple[list[int], int]:
    """Return the pad after each setter and the total gap extension.

    A pad spans the next gadget's reach (``a + b - 1`` for consecutive
    weights ``a, b``); a gap extends its pad when the ignored input's
    block needs fresh cells beyond that reach.
    """
    pads = [
        max(a + b - 1, a + (gaps[i] if gaps else 0))
        for i, (a, b) in enumerate(pairwise(weights))
    ]
    extra = sum(
        pad - (a + b - 1)
        for pad, a, b in zip(pads, weights[:-1], weights[1:], strict=True)
    )
    return pads, extra


def _mux_controls(truth_table: str, n: int, extra: int) -> tuple[list[int], int]:
    """Return the control bits and their sentinel (the controls' parity).

    With zero controls the printed row is ``popcount(r)`` plus the
    separator phase, so each control is the table bit XOR that baseline;
    a control flips every row but its own and the sentinel flips all.
    """
    total = len(truth_table)
    # Cross the setter before the first gap so its right-hand cells are fresh.
    # Each extra step flips one separator bit and moves the final pointer once.
    phase = (n ^ _mux_start(n) ^ extra ^ 1) & 1
    baseline = [((row.bit_count() ^ phase) & 1) for row in range(total)]
    controls = [
        int(bit) ^ base for bit, base in zip(truth_table, baseline, strict=True)
    ]
    return controls, sum(controls) & 1


def _mux_field(
    controls: list[int], sentinel: int, total: int, n: int, *, paired: bool
) -> tuple[list[str], int, int]:
    """Lay the control field; return (parts, strip start, field's top cell)."""
    field_lo = _MUX_FIELD
    field = "".join(map(str, reversed(controls))) + str(sentinel)
    # Fresh cells flip to one and never skip, so their walks need no ``x``;
    # one preserving step crosses the preset one the field ends before.
    field_end = field_lo + len(field) + 1
    start = _mux_start(n) + 4 * total
    walk = "[x" if paired else "["
    parts = [walk * (field_lo - 1), _mux_init_bits(field + "0", paired=paired)]
    parts.extend((_MUX_PRESERVE_RIGHT, walk * (start - 1 - field_end)))
    return parts, start, field_lo + total - 1


def _mux_setters(
    weights: tuple[int, ...], pads: list[int], gaps: tuple[int, ...]
) -> list[str]:
    """Emit each input's setter and weight gadget, pads and gaps between."""
    parts: list[str] = []
    for i, weight in enumerate(weights):
        parts.append(_MINIFUCK_INPUT)
        parts.append(_mux_weight(weight))
        if i + 1 < len(weights):
            # The next gadget reaches ``next_weight - 2`` left of its setter;
            # ordinary pads sum to 3T/2-n-2; gap extensions add at most O(n).
            gap = gaps[i] if gaps else 0
            parts.append("[x" * (pads[i] - gap) + _GAP_BLOCK * gap)
    return parts


def _mux_relay(start: int, extra: int, total: int, field_high: int) -> list[str]:
    """Walk from the last setter to the pool frame and print the chosen bit."""
    pmax = start + 3 * total // 2 - 3 + extra
    parts = ["<" * (pmax - field_high + 1), "[x", "<" * (field_high + 1)]
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
            _PRINT,
        )
    )
    return parts


def _mux_lookup(
    truth_table: str, n: int, *, paired: bool = False, gaps: tuple[int, ...] = ()
) -> str:
    """Return the linear preloaded-strip mux.

    The controls are written on fresh tape, and one left run maps row
    ``r`` to control ``r``.  With zero controls the printed row is
    ``popcount(r)`` plus the separator phase; a control flips every row but
    its own and the sentinel flips all, so the selected output is the bit.
    ``paired`` absorbs skips on fresh padding, allowing two-character breaks.
    ``gaps[i]`` ignored inputs (see :data:`_GAP_BLOCK`) sit after setter ``i``.
    """
    weights = _mux_weights(n)
    pads, extra = _mux_pads(weights, gaps)
    controls, sentinel = _mux_controls(truth_table, n, extra)
    parts, start, field_high = _mux_field(
        controls, sentinel, len(truth_table), n, paired=paired
    )
    parts.extend(_mux_setters(weights, pads, gaps))
    parts.extend(_mux_relay(start, extra, len(truth_table), field_high))
    return "".join(parts)


def _mux(truth_table: str, n: int) -> str:
    """Build the table with the linear preloaded-strip rule."""
    if n < _MUX_MIN_ARITY:
        raise ValueError("mux requires at least two inputs")
    return _mux_lookup(truth_table, n)
