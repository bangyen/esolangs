r"""Constructed 123 templates for four and more inputs.

The small-arity route in :mod:`esolangs.tools.boolean.one_two_three`
covers one, two and three inputs from a cheaper bare-fill seed; this
module builds a template for *any* wider table, under the same contract:
each ``{Xi}`` appears once in name order, ``1`` embeds a one and ``2`` a
zero (equal width), and the instantiated program halts for a 0 entry and
loops by a proven state revisit for a 1.

Why this is possible at all
---------------------------

``docs/walls.md`` recorded the wider arities as open because "the pointer
phase *is* the computed value, so a trailing inert embed shifts the very
quantity the plan decodes."  That objection binds the phase-decode shape
the searched plans use, not the language: after each embed the two fill
branches can be *re-merged* to a common pointer position, since ``2`` maps
both -1 and -2 to 0 (the -2 route prints a junk byte, which is
snapshot-invisible — ``ScriptedIO.position()`` counts reads, not writes).
The common string ``"1"*(P+1) + "212112"`` merges the branches of a fill
executed at position ``P`` back to position 0 for every ``P``, leaving the
bit as a tape difference at the fixed cells ``{P, P+1}``.  With every row
position-synchronized after every embed, the embeds stop computing anything
and become pure storage — and the rest is decode.

The pipeline
------------

1. **Embed** (`_phase_a`): walk to ``P_i``, emit ``{Xi}``, merge, and
   *scrub* — the merge's blanket flip of ``[0, P_i + 1]`` is re-flipped
   by one more synchronized walk-descend-pop, so phase A ends with all
   ``2**n`` rows at position 0 and the tape carrying exactly one mark at
   ``marks[i]`` per set bit, nothing else.
2. **Separate** (`_separate`): a *planned* decode tree, not a search.
   Level ``i`` walks each same-position group exactly onto mark cell
   ``marks[i]``; the closing ``"33"`` splits it by bit ``i`` (set-bit
   rows re-run the last segment and escape one walk higher).  The mark
   geometry comes from :func:`_geometry`: a tight linear layout with
   fixed even escapes where a per-arity reference run proves it out
   (every probed arity, and 2-3x smaller templates), else the doubling
   base whose halving escapes provably survive all ``n`` levels at any
   arity — the fallback that keeps this stage total by argument.  Pure
   right-walk segments never flip a cell, never enter the ring, never
   read stdin.
3. **Verdict** (`_verdict`): a *planned* shield-and-sweep, not a
   search.  Separation leaves every row at a distinct odd position with
   nothing marked above its own cell, and on that state the kill
   ``"1"*a + "2" + "2"*(a-1) + "12"`` (``a`` odd) is a closed form:
   rows at or above ``a`` walk back to exactly where they started and
   test their own unmarked cell, while every row below ``a`` dips
   through the ring and tests a cell in its virgin zone that the
   segment itself just marked — TRUE, and a proven periodic revisit.
   The one escape is a pre-existing mark on the tested cell, which the
   segment then *clears* — so each 0-row below the kill is shielded
   beforehand by one paint, a pair of walk-descend blocks whose flips
   cancel everywhere except the 0-row's tested cell (:func:`_paint_all`
   emits the whole campaign and applies it in one XOR per row).  One
   kill two above the highest 1-row then loops every 1-row at once.
4. **Endgame** (`_endgame`): survivors need ``pos < 0`` at end of code.
   A deep descent drops everyone into the ring, where same-residue rows
   fuse; once some residue class mod 4 is free the final ``"1"*k`` parks
   every survivor on a negative ring cell and the program halts.

:func:`construct` runs the whole pipeline and validates every stage on an
exact tracked model of all rows while emitting; a violated stage invariant
raises rather than handing back a template the rule does not license.

It does not replay the finished template, and there is no flag to make it:
a check that costs 81-95% of a call does not belong on the caller, and a
switch nothing turns on is worse than no switch.  The execution gate lives
in the suite, which runs emitted programs on the real shipped interpreter
— exhaustively at ``n <= 3``, row by row above it, and over all 65536
four-input tables in ``scripts/check_123_four_input.py``.

:func:`_replay_verdict` remains for those tests.  It is a 123 interpreter
written here against the language's rules — *not*
``esolangs.interpreters.tape_based.one_two_three``, which nothing in this
module imports — and the suite checks it against that real interpreter on
random programs, a stronger test than running it on the well-behaved
shapes this builder emits.
"""

from __future__ import annotations

from collections.abc import Iterable
from functools import cache

__all__ = ["ConstructError", "construct"]

#: Fill characters, shared with the stored-plan module's contract.
_ONE, _ZERO = "1", "2"

#: Bit offset of cell 0 in a row's tape mask.  The ring occupies cells
#: -1..-3, so shifting by three keeps every reachable cell's bit index
#: non-negative and lets one ``1 << (pos + _RING)`` cover both regions.
_RING = 3


def _on_mark(row: _Row) -> bool:
    """Report whether ``row`` is parked on one of its own marked cells."""
    return row.pos >= 0 and bool(row.tape >> (row.pos + _RING) & 1)


def _mask(cells: Iterable[int]) -> int:
    """Build a tape mask from cell numbers (bit ``c + _RING`` per cell)."""
    m = 0
    for c in cells:
        m |= 1 << (c + _RING)
    return m


#: One emitted token: a maximal ``1``/``2`` *run*, or ``("X", i)`` for a
#: fill slot.  A run rather than a character because a segment is hundreds
#: of thousands of commands long and only a few dozen runs: storing it per
#: character made :func:`_row_runs` re-coalesce 21.3M tokens per ten-input
#: build (3.5s of 7.3s).  A one-character string is still a valid run, so
#: nothing that hands the builder a token list has to change.
type _Token = str | tuple[str, int]


class ConstructError(Exception):
    """A stage of the construction found no valid move.

    Raised instead of emitting a template that was not proven correct;
    :func:`construct` turns it into :class:`ValueError` for callers.
    """


class _WorkExhaustedError(Exception):
    """The deterministic work budget ran out mid-build.

    Deliberately not a :class:`ConstructError`: stage validators catch
    those where a refusal has a defined meaning, and a drained budget
    must abort the whole build instead of being caught on the way.
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

    ``2`` at -3 would read stdin — fatal under the harness's empty script —
    so it raises here, which rejects whatever candidate move reached it.
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

    Straight runs are nearly everything the build simulates, and each
    case below collapses one into O(1) work instead of ``w`` trips
    through :func:`_exec_char`:

    * ``2`` from ``pos >= 0`` never touches the tape and cannot reach
      the ring, so it is ``pos += w``.
    * ``1`` from ``pos >= 0`` toggles exactly the contiguous cells it
      steps off, so a descent stopping at -1 or above is one XOR.
    * a deeper descent splits at the ring boundary and then *laps*: the
      ring cycle ``0 -> -1 -> -2 -> -3`` has period 4 and touches each
      of its four cells once per lap, so whole laps reduce to a parity.
    * ``2`` from inside the ring is decided by its first step (-1 and
      -2 land on 0; -3 reads stdin and raises), after which the rest is
      a plain right-walk.

    Only a short remainder is ever walked per character.  The work
    counter is decremented by the full ``w`` on every path, since the
    budget counts *simulated commands* and must not depend on which
    path ran them -- a batched path that counted less would silently
    change which borderline tables build.
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

    A fill's character is fixed once the row is known, so a segment that
    a fixpoint re-runs up to 64 times can be resolved and coalesced
    *once* -- which also lets the long right-walks inside it take the
    batched path in :func:`_exec_run`.  The tokens are already runs, so
    the loop is over a few dozen of them, not over every command.
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

    Found with :meth:`str.find` -- one C-level scan per *run* -- rather
    than a Python loop per character: the ten-input build emits 15.9M
    commands in about 2000 runs, and splitting them per character cost
    1.8s of a 7.3s build.
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

    ``seg`` holds the tokens since the last ``"33"`` — the segment a
    TRUE row re-runs — so tests can replay it faithfully, fills included.
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
        """Emit ``{Xi}``; each row executes its own fill character."""
        for row in self.live():
            self.apply_token(row, ("X", i))
        self.seg.append(("X", i))
        self.chunks.append(f"{{X{i}}}")

    def fixpoint(self, row: _Row, extra: str = "") -> str:
        """Re-run the pending segment (+ ``extra``) until the row escapes.

        Returns ``"skip"`` when the row lands on a FALSE cell or below 0,
        and ``"loop"`` on a proven state revisit.  A 3 whose test stays
        TRUE re-runs its whole segment, so this is the machine's actual
        behaviour, not an approximation.
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

        Rows below 0 ride the NOPs; rows on FALSE skip; rows on TRUE
        re-run the segment to a fixpoint.  With ``kills`` every named
        row must provably loop (it is marked dead) — every other TRUE
        row must still escape.  Without ``kills`` every TRUE row must
        escape, or the emission is invalid and raises.
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

    ``1`` when a row sits at -3 (its wrap frees the cell the next ``2``
    would read from), ``2`` otherwise.  All four ring cells occupied is an
    absorbing dead state, so the loop raises rather than spinning.
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
    """Walk right until every live row sits on a FALSE cell, then test.

    Closes the pending segment harmlessly: nobody is TRUE, everybody
    skips, and the next segment starts clean.
    """
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

    ``marks[i] = P_i + 1`` is where bit ``i``'s tape difference lands;
    the merge choreography works for every fill position ``P``.

    The fill+merge flips the whole interval ``[0, P+1]`` for a 0 row and
    ``[0, P]`` for a 1 row — hundreds of contiguous junk marks per embed,
    which used to push every later closing walk (and so every position) far
    above the cells that still distinguish the rows.  Since all rows are
    position-synchronized after the merge, one more walk-descend-pop over
    ``[0, P+1]`` re-flips the junk identically for every row and cancels it,
    leaving exactly one mark at ``P+1`` per *set* bit: after phase A row
    ``r``'s tape is ``{marks[i] : r.bits[i] == 1}``.
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

    Phase A leaves all rows at position 0 with tape ``{marks[i] : bit_i}``
    (see :func:`_phase_a`), so separation is a schedule, not a search:
    level ``i`` walks each same-position group — highest first — exactly
    onto mark cell ``marks[i]``, where the ``33`` splits it by bit ``i``
    (set-bit rows re-run the last segment and escape one walk higher).

    Each visit is a shift ``"2"*s + "33"`` followed by a test
    ``"2"*w + "33"``: the escape re-runs only the *last* segment, so the
    escape offset ``w`` is decoupled from the walk-to-the-mark distance
    ``d = s + w``.  Two escape policies serve the two geometries
    :func:`_geometry` chooses between:

    * ``ws is None`` — the doubling base's ``w = d // 2``: the escaped
      rows land strictly inside the gap above their group, which never
      merges two separated groups and at worst halves the minimum
      inter-group gap per level, so a base mark spacing of ``2**(n+1)``
      guarantees every gap is still ``>= 2`` after all ``n`` levels —
      what makes that geometry total at *every* arity.  Positions after
      level ``i`` stay below ``2 * marks[i] < marks[i+1]``, so no
      landing ever chains onto a later level's mark.
    * fixed ``ws[i]`` — the tight linear geometry's even offsets: an
      escape moves ``ws[i]`` per re-run, and the equal mark spacing
      means it *can* land on the next level's mark and cascade onward.
      Nothing here argues that converges at an arbitrary arity; the
      per-arity reference run in :func:`_geometry` is what admits it,
      and a walk shorter than the escape rejects the geometry outright.

    Pure right-walk segments never flip a cell, never enter the ring and
    never read stdin.  Every fate is still validated by ``test()``.
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

    The tight layout — marks ``(i + 1) * 2**n + 1`` with fixed even
    escape offsets ``2**(n - i)`` — spaces the marks linearly where the
    proven base doubles them, which measured 2.1x smaller templates at
    four inputs and 2.8x at five.  Whether it *works* at an arity is
    decidable cheaply, because separation never consults the table: one
    reference run per arity fixes where every row lands, and if it
    leaves each row at a distinct odd position, parked off its own
    marks, with nothing marked above its own cell, then the planned
    verdict's closed forms hold for every table at this arity.  Any
    failure — a raise anywhere, or a violated invariant — falls back to
    the doubling base with the halving escapes, whose totality is
    proven outright, so :func:`construct` stays total by argument
    either way.  The reference run costs about a millisecond even at
    seven inputs, and the result is cached per process.

    The tight geometry passes at every probed arity (one through
    seven); the fallback is totality insurance for the arities nobody
    has probed, not a path any known arity takes.
    """
    marks = tuple((i + 1) * 2**n + 1 for i in range(n))
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

    Two nested blocks cancel: ``"2"*k + "1"*k`` walks up ``k`` and descends
    back, flipping the stripe ``[pos+1, pos+k]``, and the ``k - 1`` block
    re-flips ``[pos+1, pos+k-1]`` — the XOR leaves one mark at ``pos + k``
    and every position where it started.  The walk never descends past its
    own start, so no row can enter the ring or read, whatever the tape
    holds.
    """
    if k < 1:  # pragma: no cover - the verdict computes k >= 1
        raise ConstructError(f"paint offset {k} is not above the row")
    b.run("2" * k + "1" * k)
    if k > 1:
        b.run("2" * (k - 1) + "1" * (k - 1))


def _paint_all(b: _Builder, offsets: list[int]) -> None:
    """Emit :func:`_paint` at every offset, applying them in one step.

    A paint restores every position and its descent's XOR does not read
    the tape, so a whole shield campaign is a single shift-and-XOR per
    row -- ``tape ^= delta << pos`` with bit ``k`` of ``delta`` set per
    offset -- instead of four simulated runs per paint per row.  At ten
    inputs that is 2.1M row steps of a 3.2M-step build, and the emitted
    text is the concatenation the separate paints would have produced,
    character for character.

    Distinct offsets are what make the fused XOR equal the sequence:
    two shields on one offset would cancel instead of stacking.  The
    verdict's collision-freedom argument already gives that, so a clash
    is a broken precondition rather than a case to handle.
    """
    if any(k < 1 for k in offsets):  # pragma: no cover - the verdict computes k >= 1
        raise ConstructError("a paint offset is not above the row")
    if len(set(offsets)) != len(offsets):  # pragma: no cover - positions are odd
        raise ConstructError("two shields aim at one offset")
    live = b.live()
    if any(r.pos < 0 for r in live):  # pragma: no cover - separation leaves pos >= 1
        raise ConstructError("a shield would walk out of the ring")
    parts: list[str] = []
    for k in offsets:
        parts.append(_ZERO * k)
        parts.append(_ONE * k)
        if k > 1:
            parts.append(_ZERO * (k - 1))
            parts.append(_ONE * (k - 1))
    _work[0] -= sum(map(len, parts)) * len(live)
    if _work[0] < 0:
        raise _WorkExhaustedError
    delta = 0
    for k in offsets:
        delta |= 1 << k
    for row in live:
        row.tape ^= delta << (row.pos + _RING)
    b.seg.extend(parts)
    b.chunks.append("".join(parts))


def _verdict(b: _Builder, table: str) -> None:
    """Shield every 0-row, then loop every 1-row with one planned kill.

    Separation leaves row ``r`` at a distinct odd position ``P(r)`` with
    tape exactly its set-bit marks, all at or below ``P(0)`` — nothing
    above any row's own cell is marked (its *virgin zone*).  On that
    state the kill ``"1"*a + "2" + "2"*(a-1) + "12"`` with ``a`` odd is
    a closed form, not a candidate:

    * A row at ``p >= a`` descends to ``p - a``, pops, and walks back
      to exactly ``p``, testing its own (unmarked) cell — FALSE, so the
      rows above the kill are untouched, positions included.
    * A row at ``p < a`` dips into the ring — ``a`` and ``p`` both odd
      means the descent lands at -1 or -2, never the fatal read at -3 —
      pops to 0 or 1, and tests cell ``a-1`` or ``a``.  Both cells are
      in its virgin zone, and the segment's trailing ``1`` has just
      marked the tested cell, so it tests TRUE; each re-run flips the
      cells below the tested one and restores the tested one, so the
      second or fourth pass is an exact state revisit — a proven loop.
    * The one escape is a pre-existing mark on the tested cell: the
      trailing ``1`` then *clears* it, the row tests FALSE, and it
      skips out unharmed.  That is the shield, and it is plantable per
      row because positions are distinct: a paint at offset ``k``
      marks ``pos + k`` for every row, and with all positions
      odd, distinct, and below the two tested cells, a shield aimed at
      one 0-row's tested cell can never land on another row's (the
      collision cases all force two rows one cell apart — impossible
      when every position is odd).

    So the whole verdict is: :func:`_paint_all` plants one shield per
    live 0-row below the kill (in ascending position order, the order
    the offsets are collected in), close the paints (every row still
    sits on its own unmarked cell,
    so the test is vacuously FALSE), and emit one kill with ``a`` two above
    the highest 1-row.  Every fate is still validated on the exact model by
    ``test(kills=...)``, and the closing replay re-runs every row on the
    interpreter's own rules — the preconditions above make the construction
    *total*, they are not what proves any single emission.
    """
    ones = [r for r in b.live() if _table_val(table, r.bits) == "1"]
    if not ones:
        return
    live = b.live()
    positions = [r.pos for r in live]
    if len(set(positions)) != len(positions) or any(p % 2 == 0 for p in positions):
        # Never observed (positions are distinct and odd for n <= 7,
        # and the mark base keeps the separation gaps even); raising
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

    A deep descent drops everyone into the ring, where rows of equal
    residue mod 4 land on the same cell and fuse; when all four classes
    are occupied a ring round first gives the lowest entity +1 mod 4
    (every other row lands at -2 or higher, so its ``2`` cannot read).
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


def _jump_tables(code: str) -> tuple[list[int], list[int]]:
    """Per ``3`` position, where a backward and a forward jump land.

    The interpreter rescans for the partner ``3`` on every jump, which on a
    template whose segments are hundreds of commands long is a linear scan
    per executed jump.  The landing sites depend only on the code, so they
    are computed once for the whole replay.
    """
    threes = [i for i, c in enumerate(code) if c == "3"]
    back = [0] * len(code)
    fwd = [0] * len(code)
    prev = -1
    for i in threes:
        back[i] = prev + 1  # just after the previous 3, or the start
        prev = i
    nxt = len(code)
    for i in reversed(threes):
        fwd[i] = nxt + 1 if nxt < len(code) else len(code)
        nxt = i
    return back, fwd


def _code_runs(code: str) -> tuple[list[int], list[str], list[int]]:
    """Index ``code`` into maximal ``1``/``2`` runs.

    Returns ``(run_id_at, char_of_run, end_of_run)``, so the executor can
    take the whole rest of a run in one step from any cursor inside it.
    """
    run_at = [-1] * len(code)
    chars: list[str] = []
    ends: list[int] = []
    i = 0
    while i < len(code):
        c = code[i]
        if c not in "12":
            i += 1
            continue
        j = i
        while j < len(code) and code[j] == c:
            j += 1
        for k in range(i, j):
            run_at[k] = len(chars)
        chars.append(c)
        ends.append(j)
        i = j
    return run_at, chars, ends


def _replay_ones(pos: int, tape: int, w: int) -> tuple[int, int]:
    """Apply ``"1"*w``, per the interpreter's rule for ``1``.

    Derived from the language, not from the builder's model: ``1`` flips
    the current cell and steps left, wrapping -4 back to 0.  Above the
    ring a walk flips exactly the contiguous cells it steps off, which is
    one XOR; inside it the pointer cycles ``0, -1, -2, -3`` with period
    4, touching each of the four cells once per lap, so whole laps are a
    parity and only ``w % 4`` steps remain.
    """
    while w > 0:
        if pos >= 0:
            head = min(w, pos + 1)
            tape ^= ((1 << head) - 1) << (pos - head + 1 + _RING)
            pos -= head
            w -= head
            # No wrap check here: ``head`` is capped at ``pos + 1``, so this
            # walk stops at -1 at the lowest and cannot reach -4.  The cell-0
            # wrap belongs to the inside-the-ring loop below, which is the
            # only place the pointer steps one at a time.
            continue
        laps, rest = divmod(w, 4)
        if laps:
            if laps & 1:
                tape ^= 0b1111  # a lap flips cells -3..0 once each
            w = rest
            continue
        for _ in range(w):
            tape ^= 1 << (pos + _RING)
            pos -= 1
            if pos == -4:
                pos = 0
        w = 0
    return pos, tape


def _replay_twos(pos: int, tape: int, w: int) -> tuple[int, int]:
    """Apply ``"2"*w``; the first step decides whether the ring is left.

    ``2`` at -3 reads stdin, which the harness cannot serve, so it raises
    exactly where the real interpreter would raise :class:`EOFError`.
    At -1 or -2 it lands on 0 (the -2 route prints a junk byte, which no
    snapshot can observe), and from ``pos >= 0`` it is a plain walk.
    """
    if w <= 0:
        return pos, tape
    if pos == -3:
        raise ConstructError("replay: '2' at -3 reads stdin")
    if pos in (-1, -2):
        pos = 0
        w -= 1
    return pos + w, tape


def _replay_verdict(code: str) -> str:
    """Execute one instantiated program: ``"0"`` halts, ``"1"`` loops.

    This is the closing execution gate, so it is written against the
    interpreter's own rules rather than against anything the builder
    believes -- a shared closed form would let one bug pass both.  What
    it does share is the *shape* of the cost: a template is a few
    hundred maximal ``1``/``2`` runs, each hundreds of commands long, and
    each run's effect on ``(pos, tape)`` is closed-form.  Stepping them
    one command at a time cost 95s per five-input table and hours at six,
    which made the gate, not the construction, the arity wall.

    Cycle detection stays exact under that batching.  ``ip`` strictly
    increases within a run and across a forward jump, so an infinite run
    must pass a *backward* jump or the end-of-code loopback infinitely
    often.  Sampling ``(ip, pos, tape)`` at only those two events
    therefore witnesses every loop a per-command detector witnesses, and
    Brent's method finds the revisit without storing a state per step.
    The input cursor is not part of the key: a program that reads has
    already raised above.
    """
    if not any(c in "123" for c in code):
        return "0"  # a command-less program halts with no output
    back, fwd = _jump_tables(code)
    run_at, run_ch, run_end = _code_runs(code)
    size = len(code)
    ip = pos = tape = 0
    power = lam = 1
    saved: tuple[int, int, int] | None = None
    # Events, not commands: only jumps and loopbacks are counted, and a
    # run of any length is one step.  There is deliberately no event or
    # command cap here: the answer is a real halt or an exact state revisit,
    # never a fuel-limit inference.  Constructed programs only touch a finite
    # tape prefix, so one of those two outcomes must eventually occur.
    while True:
        if ip >= size:
            # End of the program: halt below location 0, else loop.
            if pos < 0:
                return "0"
            ip = 0
        elif code[ip] == "3":
            if pos < 0:
                ip += 1  # below location 0 a 3 is a NOP
                continue
            if not tape >> (pos + _RING) & 1:
                ip = fwd[ip]  # FALSE skips forward; ip still increases
                continue
            ip = back[ip]
        else:
            r = run_at[ip]
            if r < 0:  # unrecognized characters are NOPs
                ip += 1
                continue
            fn = _replay_ones if run_ch[r] == _ONE else _replay_twos
            pos, tape = fn(pos, tape, run_end[r] - ip)
            ip = run_end[r]
            continue
        state = (ip, pos, tape)
        if saved == state:
            return "1"
        if power == lam:
            saved, power, lam = state, power * 2, 0
        lam += 1


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

    Deterministic; the construction is a stated rule, and every stage
    asserts its own invariants as it runs.  Raises :class:`ValueError`
    when a stage invariant is violated or the build exhausts its work
    budget.

    Nothing is replayed here.  A closing replay of all ``2**n`` rows is a
    *check*, not part of the construction -- it re-derives nothing the
    build needs, and its cost grows with the row count (81% of a
    four-input call, 90% at five, 95% at six), so it belongs in the
    suite rather than on every caller.

    The execution gate is stronger there than it ever was here:
    ``test_all_small_tables`` sweeps *every* table at ``n <= 3``, the
    wider tests replay their templates row by row, and
    ``scripts/check_123_four_input.py`` carries the exhaustive
    four-input sweep -- all through the real shipped interpreter
    (``interpreters.tape_based.one_two_three``) rather than the
    in-module :func:`_replay_verdict`, which the suite checks separately
    against that interpreter on random programs.
    """
    n = max(1, (len(truth_table) - 1).bit_length())
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
