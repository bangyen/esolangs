r"""Constructed 123 templates for four and more inputs.

Same contract as :mod:`esolangs.tools.one_two_three`: each run once in
name order, ``1`` a one and ``2`` a zero, halt for a 0 entry and a proven
loop for a 1.

At four inputs and up :func:`_construct_linear` emits by rule, one
segment per input: **the fill is the splitter**.  A one flips the cell
under it and steps left, a zero steps right, so the branches part by two
and the ``33`` sees the flip; the set-bit branch then replays twice,
because a replay is the first pass translated by its own displacement and
:func:`_segment` picks which cells it marks so that the third landing
cell, not the second, comes up clear.  Replays cost displacement and no
source, so the same split needs half the walk.  Nothing is pre-painted,
and the marks each pass leaves are read by the verdict, not cleared.

Below four inputs :func:`construct` runs the older modelled pipeline --
:func:`_phase_a` embeds each bit as a mark and re-merges the branches,
:func:`_separate` walks a decode tree onto the geometry
:func:`_geometry` picks, :func:`_verdict` shields each 0-row and fires
one kill, :func:`_endgame` parks the survivors below zero.  Every stage
there is validated on an exact model while emitting, and raises rather
than ship an unproven template.

Neither route replays what it emitted; the suite runs emitted programs on
the real interpreter, exhaustively at ``n <= 3``.  :func:`_replay_verdict`
is a separate 123 interpreter for those tests, checked against the real
one on random programs.
"""

from __future__ import annotations

from functools import cache

from esolangs.tools.helpers import TEMPLATE_CHAR

__all__ = ["ConstructError", "construct"]

#: Fill characters, shared with the stored-plan module's contract.
#: The fills: one character each, so instantiations are equal length.  The
#: template spells each input as a run of :data:`TEMPLATE_CHAR` this wide.
_ONE, _ZERO = "1", "2"
_INPUT = TEMPLATE_CHAR * len(_ZERO)

#: Bit offset of cell 0 in a row's tape mask.  The ring occupies cells
#: -1..-3, so shifting by three keeps every reachable cell's bit index
#: non-negative and lets one ``1 << (pos + _RING)`` cover both regions.
_RING = 3


def _on_mark(row: _Row) -> bool:
    """Report whether ``row`` is parked on one of its own marked cells."""
    return row.pos >= 0 and bool(row.tape >> (row.pos + _RING) & 1)


#: One emitted token: a maximal ``1``/``2`` *run*, or ``("X", i)`` for a
#: fill slot.  A run rather than a character because a segment is hundreds
#: of thousands of commands long and only a few dozen runs: storing it per
#: character made :func:`_row_runs` re-coalesce 21.3M tokens per ten-input
#: build (3.5s of 7.3s).  A one-character string is still a valid run, so
#: nothing that hands the builder a token list has to change.
type _Token = str | tuple[str, int]


class ConstructError(Exception):
    """A stage of the construction found no valid move.

    :func:`construct` turns it into :class:`ValueError`.
    """


class _WorkExhaustedError(Exception):
    """The deterministic work budget ran out mid-build.

    Not a :class:`ConstructError`: a drained budget aborts the whole build.
    """


class _Row:
    """Tracked state of one instantiation while the template is built."""

    __slots__ = ("bits", "dead", "pos", "tape")

    #: ``tape`` is a bitmask, not a set: bit ``pos + _RING`` is cell
    #: ``pos``.  The builder toggles and tests one cell at a time in the
    #: innermost loop, where an int shift is several times cheaper than a
    #: set operation, and it doubles as its own hashable snapshot -- the
    #: ``frozenset(tape)`` these state keys used to build was pure cost.
    def __init__(self, bits: tuple[int, ...]) -> None:
        self.bits = bits
        self.pos = 0
        self.tape = 0
        self.dead = False


#: Remaining work budget for the current :func:`construct` call, counted
#: in simulated commands — machine-independent, so the same table either
#: builds or raises identically everywhere.  A list so the counter can be
#: decremented in place from :func:`_exec_char`.
_work = [0]


def _exec_char(row: _Row, ch: str) -> None:
    """Apply one ``1``/``2`` command to a row, mirroring the interpreter.

    ``2`` at -3 would read stdin, so it raises.
    """
    _work[0] -= 1
    if _work[0] < 0:
        raise _WorkExhaustedError
    if ch == "1":
        row.tape ^= 1 << (row.pos + _RING)
        row.pos -= 1
        if row.pos == -4:
            row.pos = 0
    elif ch == "2":
        if row.pos == -3:
            raise ConstructError(f"row {row.bits}: '2' at -3 reads stdin")
        if row.pos == -2:
            row.pos = 0  # prints a junk byte; snapshot-invisible
        else:
            row.pos += 1
    else:  # pragma: no cover - the builder only emits 1/2 runs
        raise AssertionError(ch)


def _exec_run(row: _Row, ch: str, w: int) -> None:
    """Apply ``ch`` repeated ``w`` times to one row.

    Each straight run collapses to O(1): ``2`` from ``pos >= 0`` is
    ``pos += w``; ``1`` from ``pos >= 0`` toggles the cells stepped off (one
    XOR), and a deeper descent laps the period-4 ring by parity; ``2``
    inside the ring is decided by its first step.  The work counter is
    decremented by the full ``w`` on every path.
    """
    if w and row.pos >= 0:
        if ch == _ZERO:
            _work[0] -= w
            if _work[0] < 0:
                raise _WorkExhaustedError
            row.pos += w
            return
        if row.pos - w >= -1:
            # A descent that stops at -1 or above never wraps, so it is
            # exactly "toggle the w cells it steps off, then move down":
            # the cells pos-w+1..pos are contiguous, hence one XOR with a
            # w-bit mask.  Below -1 the ring's -4 -> 0 wrap and the read
            # at -3 both matter, so that case stays per-character.
            _work[0] -= w
            if _work[0] < 0:
                raise _WorkExhaustedError
            row.tape ^= ((1 << w) - 1) << (row.pos - w + 1 + _RING)
            row.pos -= w
            return
    if ch == _ONE and row.pos >= 0 and w > row.pos + 1:
        # A descent that runs past -1 splits at the ring boundary: the
        # part above it is the contiguous-XOR case, and the rest laps.
        head = row.pos + 1
        _work[0] -= head
        if _work[0] < 0:
            raise _WorkExhaustedError
        row.tape ^= ((1 << head) - 1) << _RING
        row.pos = -1
        w -= head
    if ch == _ONE and w >= 4 and row.pos < 0:
        # Inside the ring ``1`` cycles 0 -> -1 -> -2 -> -3 -> 0 with
        # period 4, toggling each of those four cells once per lap.  A
        # whole number of laps therefore cancels on every cell when the
        # lap count is even and flips all four when it is odd, so only
        # ``w % 4`` steps have to be walked.  This is the kill segment's
        # inner loop, where the descents run hundreds of cells deep.
        laps, rest = divmod(w, 4)
        _work[0] -= w - rest
        if _work[0] < 0:
            raise _WorkExhaustedError
        if laps & 1:
            row.tape ^= 0b1111  # cells -3..0, i.e. bits 0..3
        for _ in range(rest):
            _exec_char(row, ch)
        return
    if ch == _ZERO and w and row.pos < 0:
        # ``2`` at -1 or -2 lands on 0 (the -2 route prints a junk byte),
        # and -3 reads stdin, which is fatal -- so the first step decides
        # everything and the remaining w-1 are a plain right-walk.
        _exec_char(row, ch)
        w -= 1
        if w:
            _work[0] -= w
            if _work[0] < 0:
                raise _WorkExhaustedError
            row.pos += w
        return
    for _ in range(w):
        _exec_char(row, ch)


def _row_runs(row: _Row, toks: list[_Token]) -> list[tuple[str, int]]:
    """Resolve ``toks`` for one row and coalesce it into runs.

    A segment a fixpoint re-runs up to 64 times is resolved once.
    """
    out: list[tuple[str, int]] = []
    for tok in toks:
        if isinstance(tok, tuple):
            ch, w = (_ONE if row.bits[tok[1]] else _ZERO), 1
        else:
            ch, w = tok[0], len(tok)
        if out and out[-1][0] == ch:
            out[-1] = (ch, out[-1][1] + w)
        else:
            out.append((ch, w))
    return out


def _run_parts(s: str) -> list[str]:
    """``"2211"`` -> ``["22", "11"]``, the maximal runs as substrings.

    :meth:`str.find` per run: splitting the ten-input build's 15.9M commands
    per character cost 1.8s of 7.3s.
    """
    out: list[str] = []
    size = len(s)
    i = 0
    while i < size:
        ch = s[i]
        if ch == _ONE:
            other = _ZERO
        elif ch == _ZERO:
            other = _ONE
        else:  # pragma: no cover - the builder only emits 1/2 runs
            raise AssertionError(ch)
        j = s.find(other, i + 1)
        if j < 0:
            j = size
        out.append(s[i:j])
        i = j
    return out


class _Builder:
    """Emits template chunks while tracking every row's exact state.

    ``seg`` holds the tokens since the last ``"33"``, which a TRUE row re-runs.
    """

    __slots__ = ("chunks", "n", "rows", "seg")

    def __init__(self, n: int) -> None:
        self.n = n
        self.chunks: list[str] = []
        self.seg: list[_Token] = []
        self.rows = [
            _Row(tuple((r >> (n - 1 - i)) & 1 for i in range(n))) for r in range(2**n)
        ]

    def live(self) -> list[_Row]:
        return [r for r in self.rows if not r.dead]

    def apply_token(self, row: _Row, tok: _Token) -> None:
        if isinstance(tok, tuple):
            _exec_char(row, _ONE if row.bits[tok[1]] else _ZERO)
        else:
            _exec_run(row, tok[0], len(tok))

    def run(self, s: str) -> None:
        """Emit straight-line commands; every live row executes them."""
        live = self.live()
        parts = _run_parts(s)
        for part in parts:
            ch, w = part[0], len(part)
            for row in live:
                _exec_run(row, ch, w)
        self.seg.extend(parts)
        self.chunks.append(s)

    def fill(self, i: int) -> None:
        """Emit input ``i``'s run; each row executes its own fill character."""
        for row in self.live():
            self.apply_token(row, ("X", i))
        self.seg.append(("X", i))
        self.chunks.append(_INPUT)

    def fixpoint(self, row: _Row, extra: str = "") -> str:
        """Re-run the pending segment (+ ``extra``) until the row escapes.

        ``"skip"`` on a FALSE cell or below 0, ``"loop"`` on a proven revisit.
        """
        tail: list[_Token] = list(_run_parts(extra))
        runs = _row_runs(row, list(self.seg) + tail)
        seen = {(row.pos, row.tape)}
        for _ in range(64):
            for ch, w in runs:
                _exec_run(row, ch, w)
            if row.pos < 0 or not row.tape >> (row.pos + _RING) & 1:
                return "skip"
            s = (row.pos, row.tape)
            if s in seen:
                return "loop"
            seen.add(s)
        raise ConstructError(f"fixpoint cap: row {row.bits}")

    def test(self, *, kills: frozenset[tuple[int, ...]] | None = None) -> None:
        """Close the current segment with ``"33"``.

        With ``kills`` every named row must provably loop and every other TRUE
        row escape; without, every TRUE row must escape, or this raises.
        """
        kills = kills or frozenset()
        true_rows = [r for r in self.live() if _on_mark(r)]
        for row in true_rows:
            fate = self.fixpoint(row)
            if row.bits in kills:
                if fate != "loop":
                    raise ConstructError(f"kill escaped: row {row.bits}")
                row.dead = True
            elif fate != "skip":
                raise ConstructError(f"unintended loop: row {row.bits}")
        dead = {r.bits for r in self.rows if r.dead}
        missed = [k for k in kills if k not in dead]
        if missed:
            raise ConstructError(f"kill missed: row {missed[0]} never tested TRUE")
        self.seg = []
        self.chunks.append("33")

    def template(self) -> str:
        return "".join(self.chunks)

    def clone(self) -> _Builder:
        nb = _Builder.__new__(_Builder)
        nb.n = self.n
        nb.chunks = list(self.chunks)
        nb.seg = list(self.seg)
        nb.rows = []
        for r in self.rows:
            nr = _Row(r.bits)
            nr.pos, nr.tape, nr.dead = r.pos, r.tape, r.dead
            nb.rows.append(nr)
        return nb


def _table_val(table: str, bits: tuple[int, ...]) -> str:
    return table[int("".join(map(str, bits)), 2)]


def _normalize(b: _Builder) -> None:
    """Bring every live row to ``pos >= 0``.

    ``1`` at -3, ``2`` otherwise; all four ring cells occupied raises.
    """
    # Which character comes next depends only on where the rows *are* --
    # ``1`` when some row sits at -3, ``2`` otherwise -- never on what they
    # have marked.  So the whole string is planned on a plain list of
    # positions, with no tape and no builder clone, and only the finished
    # string is executed (once, through the batched ``run``).  This is the
    # difference between planning and simulating: the probe used to run
    # every row's tape through ``_exec_char`` per character, 92% of every
    # command the separation stage simulated.
    positions = [r.pos for r in b.live()]
    if all(p >= 0 for p in positions):
        return
    # A live-lock is a repeated position vector, reached almost at once:
    # the step is deterministic and only the four ring cells can hold a
    # negative row, so a cycling state repeats within a handful of steps
    # (measured worst case: nine).  Detecting the repeat ends those calls
    # immediately instead of spinning to a 10000-iteration cap -- where
    # this loop spent 4.96M of its 4.96M iterations, since the calls that
    # *do* normalize emit only a few characters each.
    out: list[str] = []
    seen: set[tuple[int, ...]] = {tuple(positions)}
    while True:
        if any(p == -3 for p in positions):
            out.append(_ONE)
            # ``1`` steps left and wraps -4 -> 0; no cell read can fail.
            positions = [0 if p == -4 else p for p in (q - 1 for q in positions)]
        else:
            out.append(_ZERO)
            # ``2`` at -3 would read stdin, but the branch above already
            # cleared -3, so every row here either sits at -1/-2 (landing
            # on 0) or walks right.
            positions = [0 if p in (-1, -2) else p + 1 for p in positions]
        if all(p >= 0 for p in positions):
            b.run("".join(out))
            return
        key = tuple(positions)
        if key in seen:
            raise ConstructError("normalize live-locked")
        seen.add(key)


def _close(b: _Builder) -> None:
    """Walk right until every live row sits on a FALSE cell, then test."""
    _normalize(b)
    probe = b.clone()
    for w in range(100001):
        if all(r.pos >= 0 and not r.tape >> (r.pos + _RING) & 1 for r in probe.live()):
            if w:
                b.run("2" * w)
            b.test()
            return
        for row in probe.live():
            _exec_char(row, "2")
    raise ConstructError("no clean closing cell")


def _phase_a(b: _Builder, marks: list[int]) -> None:
    """Embed every input, merge back to position 0, and scrub the blob.

    ``marks[i] = P_i + 1``.  The fill+merge flips ``[0, P+1]`` (0 row) or
    ``[0, P]`` (1 row); one more synchronized walk-descend-pop re-flips the
    junk identically, leaving one mark at ``P+1`` per set bit.
    """
    for i, m in enumerate(marks):
        p = m - 1
        b.run("2" * p)
        b.fill(i)
        b.run("1" * (p + 1) + "212112")
        b.run("2" * m + "1" * (m + 1) + "2")
        if {r.pos for r in b.live()} != {0}:  # pragma: no cover - invariant
            raise ConstructError("merge failed to re-synchronize")


def _separate(b: _Builder, marks: list[int], ws: tuple[int, ...] | None = None) -> None:
    """Give every row a unique position by a planned decode tree.

    Level ``i`` walks each same-position group, highest first, onto
    ``marks[i]``, where ``33`` splits it by bit ``i``.  Each visit is a shift
    ``"2"*s + "33"`` then a test ``"2"*w + "33"``, so the escape offset ``w``
    is decoupled from the distance.  Doubling base (``ws is None``):
    ``w = d // 2`` halves the minimum gap per level, so spacing ``2**(n+1)``
    keeps every gap ``>= 2`` after ``n`` levels at any arity.  Tight
    geometry: fixed even ``ws[i]``, the budget ``sum ws == 2**(n + 1) - 2``
    under the spacing, positions closing to ``base + 2*r``; admitted by the
    reference run, not this argument.
    """
    for i, mk in enumerate(marks):
        for _visit in range(2**b.n + 1):
            pending = [p for p in {r.pos for r in b.live()} if p < mk]
            if not pending:
                break
            d = mk - max(pending)
            w = max(1, d // 2) if ws is None else ws[i]
            if d < w:  # pragma: no cover - the probed arities all pass
                raise ConstructError(f"level {i}: walk {d} under escape {w}")
            # `d < w` is refused above, and the planned walk always
            # overshoots the escape, so this always runs.
            if d > w:  # pragma: no branch
                b.run("2" * (d - w))
                b.test()
            b.run("2" * w)
            b.test()
        else:  # pragma: no cover - 2**n groups is the exact worst case
            raise ConstructError(f"level {i} did not converge")
    poss = [r.pos for r in b.live()]
    if len(set(poss)) != len(poss):  # pragma: no cover - invariant
        raise ConstructError("separation left shared positions")


@cache
def _geometry(n: int) -> tuple[tuple[int, ...], tuple[int, ...] | None]:
    """Pick arity ``n``'s mark geometry: tight when it proves out.

    Tight: marks ``(i + 1) * 2**(n + 1) + 1`` with escapes ``2**(n - i)``,
    linear where the base doubles -- 2.2x smaller at four inputs, 64x at
    nine (48.2M vs 752K chars).  The spacing is ``2**(n + 1)`` because
    ``2**n`` *is* the level-0 escape (an escapee cascaded onto mark 1); the
    escapes are a binary encoding with budget ``2**(n + 1) - 2``, and the
    least even spacing above it keeps every position odd.  Measured floor is
    ``2**(n + 1) - 4`` (<=0.2%); ``- 6`` refuses at every ``n >= 3``.  One
    reference run per arity (~1ms at seven inputs, cached) decides it: each
    row at a distinct odd position with nothing marked above, else the
    doubling base.  Passes at every probed arity (one through ten).
    """
    marks = tuple((i + 1) * 2 ** (n + 1) + 1 for i in range(n))
    ws = tuple(2 ** (n - i) for i in range(n))
    _work[0] = _WORK_BUDGET * max(1, 2 ** (n - 4))
    try:
        b = _Builder(n)
        _phase_a(b, list(marks))
        _close(b)
        _separate(b, list(marks), ws)
        rows = b.live()
        poss = [r.pos for r in rows]
        ok = (
            len(set(poss)) == len(poss)
            and all(p % 2 for p in poss)
            and not any(_on_mark(r) for r in rows)
            and all(r.tape >> (r.pos + 1 + _RING) == 0 for r in rows)
        )
    except (ConstructError, _WorkExhaustedError):  # pragma: no cover
        ok = False
    if ok:
        return marks, ws
    # No probed arity reaches this fallback; it is what keeps construct
    # total by argument at the arities nobody has probed.
    return tuple(2 ** (n + 1) * 2**i + 1 for i in range(n)), None  # pragma: no cover


def _paint(b: _Builder, k: int) -> None:
    """Flip exactly cell ``pos + k`` for every live row, positions kept.

    ``"2"*k + "1"*k`` and the ``k - 1`` block XOR to one mark; the walk
    never descends past its start.
    """
    if k < 1:  # pragma: no cover - the verdict computes k >= 1
        raise ConstructError(f"paint offset {k} is not above the row")
    b.run("2" * k + "1" * k)
    if k > 1:
        b.run("2" * (k - 1) + "1" * (k - 1))


def _paint_all(b: _Builder, offsets: list[int]) -> None:
    """Paint every offset in one outward-and-back sweep.

    Walk to the highest target, descend; an unselected cell gets a ``21``
    excursion so it flips twice.  At most four commands per cell, one XOR
    per tracked row.  Offsets must be distinct (a clash is a broken precondition).
    """
    if any(k < 1 for k in offsets):  # pragma: no cover - the verdict computes k >= 1
        raise ConstructError("a paint offset is not above the row")
    if len(set(offsets)) != len(offsets):  # pragma: no cover - positions are odd
        raise ConstructError("two shields aim at one offset")
    live = b.live()
    if any(r.pos < 0 for r in live):  # pragma: no cover - separation leaves pos >= 1
        raise ConstructError("a shield would walk out of the ring")
    targets = set(offsets)
    top = max(offsets)
    parts = [_ZERO * top]
    for k in range(top, 0, -1):
        parts.append(_ONE)
        if k not in targets:
            parts.append(_ZERO + _ONE)
    _work[0] -= sum(map(len, parts)) * len(live)
    if _work[0] < 0:
        raise _WorkExhaustedError
    delta = 0
    for k in offsets:
        delta |= 1 << k
    for row in live:
        row.tape ^= delta << (row.pos + _RING)
    source = "".join(parts)
    # ``parts`` includes mixed ``"21"`` excursions, while ``seg`` stores
    # maximal homogeneous runs.  Most callers close on a false cell and
    # never replay the sweep; conditional painting does, so preserving a
    # mixed part as one token would replay it as two ``2`` commands.
    b.seg.extend(_run_parts(source))
    b.chunks.append(source)


def _verdict(b: _Builder, table: str) -> None:
    """Shield every 0-row, then loop every 1-row with one planned kill.

    With rows at distinct odd ``P(r)`` and nothing marked above, the kill
    ``"1"*a + "2" + "2"*(a-1) + "12"`` (``a`` odd) is a closed form: a row at
    ``p >= a`` walks back to ``p`` and tests its own unmarked cell (FALSE);
    a row at ``p < a`` dips into the ring (odd ``a`` and ``p`` land at -1 or
    -2, never the read at -3), pops, and tests ``a-1`` or ``a`` in its virgin
    zone, just marked by the trailing ``1`` -- TRUE, and the second or
    fourth pass is an exact revisit.  A pre-existing mark there is cleared
    instead, the row tests FALSE and skips: the shield, plantable per row
    because positions are odd and distinct.  :func:`_paint_all` plants one
    per live 0-row, the paints are closed, and one kill sits two above the
    highest 1-row.  Every fate is still validated by ``test(kills=...)``.
    """
    ones = [r for r in b.live() if _table_val(table, r.bits) == "1"]
    if not ones:
        return
    live = b.live()
    positions = [r.pos for r in live]
    if len(set(positions)) != len(positions) or any(p % 2 == 0 for p in positions):
        # Never observed (separation puts row r at ``base + 2*r`` under
        # the spacing :func:`_geometry` picks, checked to n = 10, and the
        # mark base keeps the gaps even); raising
        # keeps the no-unproven-template contract if a wider arity
        # ever breaks the parity.
        raise ConstructError("verdict precondition: positions not distinct odd")
    a = max(r.pos for r in ones) + 2
    offsets: list[int] = []
    for r in sorted(live, key=lambda row: row.pos):
        if r.pos >= a or _table_val(table, r.bits) == "1":
            continue
        tested = a if (a - r.pos) % 4 == 0 else a - 1
        offsets.append(tested - r.pos)
    if offsets:
        _paint_all(b, offsets)
        b.test()
    b.run("1" * a + "2" + "2" * (a - 1) + "12")
    b.test(kills=frozenset(r.bits for r in ones))


def _endgame(b: _Builder) -> None:
    """Park every survivor below 0 at the end of the code, so it halts.

    A deep descent fuses rows of equal residue mod 4 in the ring; a round
    frees a class (every other row lands at -2 or higher, so no read).
    """
    live = b.live()
    if not live:
        return
    for _ in range(64 * 2**b.n + 64):
        _normalize(b)
        poss = sorted({r.pos for r in live})
        if len(poss) == 1:
            break
        if len({p % 4 for p in poss}) == 4:
            b.run("1" * (poss[0] + 2))
            b.run("2")
            continue
        b.run("1" * (max(poss) + 1))
    else:
        raise ConstructError("endgame did not converge")
    p = min(r.pos for r in live)
    b.run("1" * (p + 1))
    if any(r.pos >= 0 for r in live):  # pragma: no cover - invariant
        raise ConstructError("a survivor would restart instead of halting")


def _paint_source(offsets: list[int]) -> str:
    """Spell :func:`_paint_all` without constructing per-row tape states."""
    targets = set(offsets)
    top = max(offsets)
    return _ZERO * top + "".join(
        _ONE if k in targets else _ONE + _ZERO + _ONE for k in range(top, 0, -1)
    )


def _position_after_ones(pos: int, count: int) -> int:
    """Return a pointer position after ``count`` ``1`` commands."""
    if count <= pos + 1:
        return pos - count
    return (-1, -2, -3, 0)[(count - pos - 1) % 4]


def _linear_endgame(positions: set[int]) -> str:
    """Park the given nonnegative positions below zero in O(max(position)) source."""
    out = []
    while len(positions) > 1:
        while any(pos < 0 for pos in positions):
            if -3 in positions:
                out.append(_ONE)
                positions = {0 if pos == -3 else pos - 1 for pos in positions}
            else:
                out.append(_ZERO)
                positions = {0 if pos in (-1, -2) else pos + 1 for pos in positions}
        if len({pos % 4 for pos in positions}) == 4:
            count = min(positions) + 2
            out.append(_ONE * count)
            positions = {_position_after_ones(pos, count) for pos in positions}
            out.append(_ZERO)
            positions = {0 if pos in (-1, -2) else pos + 1 for pos in positions}
        else:
            count = max(positions) + 1
            out.append(_ONE * count)
            positions = {_position_after_ones(pos, count) for pos in positions}
    pos = next(iter(positions))
    out.append(_ONE * (pos + 1))
    return "".join(out)


def _walk(i: int) -> int:
    """Level ``i``'s stride ``d``: a zero advances ``d + 2``, a one ``3*d``.

    The least admissible stride, not a tuned constant.  A set-bit row runs
    the segment three times (see :func:`_segment`), so it splits by
    ``3*d - (d + 2) = 2*d - 2``, and the split has to beat the spread
    ``2*(2**i - 1)`` already accumulated or two rows collide -- so
    ``2*d - 2 = 2*2**i``, which is this.
    """
    return (1 << i) + 1


def _segment(i: int) -> str:
    """Level ``i``'s splitter: one fill, three passes for a set bit.

    ``"2"*d`` puts the fill on cell ``d``, ``"2"*(2*d+1)`` carries the walk
    out to ``3*d``, and the descent comes back to ``d`` marking every cell
    it leaves except ``2*d`` and ``3*d-1`` (``"121"`` toggles a cell twice
    and still steps down, so skipping costs two characters).  A pass is the
    one before it translated by ``d``, so the pass-``j`` landing cell
    ``j*d`` is marked exactly when an odd number of ``{d, 2*d, 3*d}`` are
    toggled: ``d`` and ``3*d`` are, ``2*d`` is not, so passes 1 and 2 land
    marked and pass 3 lands clear.  ``3*d-1`` is skipped so the next
    level's fill cell, ``2*d - 1`` above this one's landing, is clear.
    """
    d = _walk(i)
    descent = _ONE + "121" + _ONE * (d - 2) + "121" + _ONE * (d - 1)
    return _ZERO * d + _INPUT + _ZERO * (2 * d + 1) + descent + "33"


def _leftover(n: int, bit: int, off: int) -> bool:
    """Whether cell ``off`` above a row's landing cell ends the walk marked.

    Closed form, not a simulation: only the last level's marks survive above
    its own landing cell.  With ``M`` the descent's marks -- ``[d+1, 3*d]``
    less ``2*d`` and ``3*d-1`` -- the toggles left above are ``M - d`` for a
    clear bit and, three passes in, ``(M - d)`` xor ``(M - 2*d)`` for a set
    one.
    """
    d = _walk(n - 1)
    if off == 2 * d:
        return True
    if bit:
        return d - 1 <= off <= 2 * d - 2
    return 1 <= off <= d - 1 or d + 1 <= off <= 2 * d - 2


def _construct_linear(truth_table: str, n: int) -> str:
    """Build the fill-as-splitter 123 construction in O(T) time and source.

    Level ``i`` is one :func:`_segment` with stride ``d = _walk(i)``.  The
    fill itself is the split: a one flips the cell under it and steps left,
    a zero steps right, so the two branches part and the ``33`` sees the
    flip.  A set-bit row lands on that fresh mark and replays *twice* before
    its landing cell comes up clear, so it advances ``3*d`` against a clear
    bit's ``d + 2``.  Nothing is pre-painted: the split is ``2*d - 2``, so
    ``d = 2**i + 1`` doubles the spread and row ``r`` ends at
    ``sum(d_i + 2) + 2*bit_reverse(r)`` -- distinct, even-strided positions.

    Three passes cost no source, only displacement, which is why the stride
    is half what one replay needs: the zero branch's advance -- and with it
    the kill and the endgame, both priced off the topmost row -- falls from
    ``4*T`` to ``3*T``.  :func:`_leftover` gives what each pass leaves above
    a row's landing cell; the verdict reads that rather than clearing it, so
    a shield is planted only where the tape disagrees with the table.
    """
    out: list[str] = [_segment(i) for i in range(n)]

    reversed_rows = [0]
    for _ in range(n):
        reversed_rows = [2 * row for row in reversed_rows] + [
            2 * row + 1 for row in reversed_rows
        ]
    start = sum(_walk(i) + 2 for i in range(n))
    positions = [start + 2 * row for row in reversed_rows]
    ones = [positions[row] for row, bit in enumerate(truth_table) if bit == "1"]
    if ones:
        boundary = max(ones) + 2
        shields = []
        for row, pos in enumerate(positions):
            if pos >= boundary:
                continue
            tested = boundary if (boundary - pos) % 4 == 0 else boundary - 1
            # Below the kill a 0-row's tested cell must end marked and a
            # 1-row's clear, so paint only where the leftovers disagree.
            if _leftover(n, row & 1, tested - pos) != (truth_table[row] == "0"):
                shields.append(tested - pos)
        if shields:
            out.extend((_paint_source(shields), "33"))
        out.extend(
            (
                _ONE * boundary,
                _ZERO,
                _ZERO * (boundary - 1),
                _ONE + _ZERO,
                "33",
            )
        )
        live = {
            (boundary if (boundary - pos) % 4 == 0 else boundary - 1)
            if pos < boundary
            else pos
            for row, pos in enumerate(positions)
            if truth_table[row] == "0"
        }
    else:
        live = set(positions)
    if live:
        out.append(_linear_endgame(live))
    return "".join(out)


#: Simulated commands a :func:`construct` call may spend before raising.
#: Counted work, not wall clock, so the same table either builds or
#: raises identically on every machine.
#:
#: The counter is charged for what is actually simulated.  It is never
#: read by a planning decision -- only tested against zero to abort --
#: so charging cannot change which template a table emits, only whether
#: a diverging build is cut off.  The pipeline is planned end to end,
#: so the budget is a divergence guard for a stage invariant breaking
#: at an unprobed arity, not a search allowance; :func:`construct`
#: scales it with the row count so it never becomes an arity ceiling.
_WORK_BUDGET = 2_000_000_000


def construct(truth_table: str) -> str:
    """Build a 123 template for ``truth_table`` at any arity.

    Deterministic; every stage asserts its invariants.  Raises
    :class:`ValueError` on a violated invariant or exhausted budget.  No
    closing replay here (81% of a four-input call, 95% at six): the suite
    sweeps every table at ``n <= 3`` and replays wider ones row by row on the
    real interpreter.
    """
    n = max(1, (len(truth_table) - 1).bit_length())
    if n >= 4:
        return _construct_linear(truth_table, n)
    # The mark geometry comes from _geometry: the tight linear layout
    # when its per-arity reference run proves out (every probed arity),
    # the doubling base with halving escapes -- proven total at every
    # arity -- otherwise.  The reference run manages its own budget and
    # caches, so it is charged once per arity, not per table.
    #
    # The budget still bounds a diverging build, but everything about a
    # wider table is exponentially bigger -- rows, template length,
    # shield paints -- so the cap scales with the row count to stay a
    # divergence guard, not an arity ceiling.
    marks_t, ws = _geometry(n)
    marks = list(marks_t)
    _work[0] = _WORK_BUDGET * max(1, 2 ** (n - 4))
    try:
        b = _Builder(n)
        _phase_a(b, marks)
        _close(b)
        _separate(b, marks, ws)
        _verdict(b, truth_table)
        _endgame(b)
        template = b.template()
    except _WorkExhaustedError:
        raise ValueError(
            f"123 construction failed for {truth_table!r}: "
            "the work budget ran out before the build converged"
        ) from None
    except ConstructError as exc:
        raise ValueError(f"123 construction failed for {truth_table!r}: {exc}") from exc
    return template
