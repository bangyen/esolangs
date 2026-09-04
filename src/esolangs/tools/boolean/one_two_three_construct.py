r"""Constructed 123 templates for four and more inputs.

The stored plans in :mod:`esolangs.tools.boolean.one_two_three` cover one,
two and three inputs; this module builds a template for *any* wider table,
under the same contract: each ``{Xi}`` appears once in name order, ``1``
embeds a one and ``2`` a zero (equal width), and the instantiated program
halts for a 0 entry and loops by a proven state revisit for a 1.

Why this is possible at all
---------------------------

``docs/walls.md`` recorded the wider arities as open because "the pointer
phase *is* the computed value, so a trailing inert embed shifts the very
quantity the plan decodes."  That objection binds the phase-decode shape
the searched plans use, not the language: after each embed the two fill
branches can be *re-merged* to a common pointer position, because ``2``
maps both -1 and -2 to 0 (the -2 route prints a junk byte, which is
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
   rows re-run the last segment and escape one walk higher).  Escape
   offsets are chosen so the minimum inter-group gap at worst halves
   per level, and the mark base ``2**(n+1)`` gives the first gap enough
   room to survive all ``n`` halvings — which is why this stage cannot
   fail at any arity.  Pure right-walk segments never flip a cell,
   never enter the ring, never read stdin.
3. **Verdict** (`_verdict_search`): a bounded depth-first search over
   three move kinds — a *kill* (the segment ``"1"*a + "2"`` or its
   mark-anchored variant ``"1"*a + "2" + "2"*X + "12"``, which loops the
   row that dips into the -1..-3 ring and tests TRUE, by a proven
   periodic revisit; bystander rows the descent also dips may test TRUE
   once and skip on a later pass), a *boost* (a plain test whose TRUE
   set excludes the victim, moving blockers out of the way singly or in
   bulk), and a *ring round* (descend, pop, reshuffle relative residues,
   depositing the above-position marks boosts need).  On the clean state
   separation leaves, the first candidate — kill the lowest live 1-row,
   letting the 0-rows below it dip and skip — succeeds nearly every
   time, so the search normally runs as a straight-line schedule and
   backtracking is the insurance, not the mechanism.
4. **Endgame** (`_endgame`): survivors need ``pos < 0`` at end of code.
   A deep descent drops everyone into the ring, where same-residue rows
   fuse; once some residue class mod 4 is free the final ``"1"*k`` parks
   every survivor on a negative ring cell and the program halts.

:func:`construct` runs the whole pipeline under two mark geometries in
order (uniform and residue-staggered — see its comment for the parity
law that makes some tables solvable under only one), validates every
candidate move on an exact tracked model of all rows before emitting
it, and replays every row of the finished template on the real
interpreter before returning it — a wrong program is never handed out;
an exhausted search raises instead.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from itertools import pairwise

__all__ = ["ConstructError", "construct"]

#: Fill characters, shared with the stored-plan module's contract.
_ONE, _ZERO = "1", "2"

#: Bit offset of cell 0 in a row's tape mask.  The ring occupies cells
#: -1..-3, so shifting by three keeps every reachable cell's bit index
#: non-negative and lets one ``1 << (pos + _RING)`` cover both regions.
_RING = 3


def _pos_after_ones(p: int, a: int) -> int:
    """Where ``"1"*a`` leaves a row that starts at ``p >= 0``.

    The walk falls straight to -1 in ``p + 1`` steps and then rides the
    ring's 4-cycle ``-1, -2, -3, 0``, so the landing cell is arithmetic
    rather than a simulation.  Verified against the interpreter model
    over every ``p < 60`` and ``a < 200``.
    """
    if a <= p:
        return p - a
    return (-1, -2, -3, 0)[(a - (p + 1)) % 4]


def _ones_then_pop_reads(positions: list[int], a: int) -> bool:
    """Report whether ``"1"*a + "2"`` would read stdin for a row.

    The ``2`` is fatal exactly when some row sits at -3 after the
    descent, and where the descent lands depends only on the starting
    position -- so a kill prefix can be rejected by arithmetic over the
    live positions instead of by descending every row hundreds of cells
    and catching the raise.  Most candidate prefixes die here.
    """
    return any(_pos_after_ones(p, a) == -3 for p in positions)


def _on_mark(row: _Row) -> bool:
    """Report whether ``row`` is parked on one of its own marked cells."""
    return row.pos >= 0 and bool(row.tape >> (row.pos + _RING) & 1)


def _cells(mask: int) -> list[int]:
    """Ascending cell numbers set in ``mask``."""
    return [i - _RING for i in range(mask.bit_length()) if mask >> i & 1]


def _mask(cells: Iterable[int]) -> int:
    """Build a tape mask from cell numbers -- the inverse of :func:`_cells`."""
    m = 0
    for c in cells:
        m |= 1 << (c + _RING)
    return m


#: One emitted token: a literal command, or ``("X", i)`` for a fill slot.
type _Token = str | tuple[str, int]


class ConstructError(Exception):
    """A stage of the construction found no valid move.

    Raised instead of emitting a template that was not proven correct;
    :func:`construct` turns it into :class:`ValueError` for callers.
    """


class _WorkExhaustedError(Exception):
    """The deterministic work budget ran out mid-search.

    Deliberately not a :class:`ConstructError`: candidate validators
    swallow those to try the next candidate, and a drained budget must
    abort the whole build instead of being retried away.
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

    Straight runs are nearly everything the searches simulate, and each
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
    batched path in :func:`_exec_run`.
    """
    out: list[tuple[str, int]] = []
    for tok in toks:
        ch = (_ONE if row.bits[tok[1]] else _ZERO) if isinstance(tok, tuple) else tok
        if out and out[-1][0] == ch:
            out[-1] = (ch, out[-1][1] + 1)
        else:
            out.append((ch, 1))
    return out


def _runs(s: str) -> list[tuple[str, int]]:
    """``"2211"`` -> ``[("2", 2), ("1", 2)]``."""
    out: list[tuple[str, int]] = []
    for ch in s:
        if out and out[-1][0] == ch:
            out[-1] = (ch, out[-1][1] + 1)
        else:
            out.append((ch, 1))
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
            _exec_char(row, tok)

    def run(self, s: str) -> None:
        """Emit straight-line commands; every live row executes them."""
        live = self.live()
        for ch, w in _runs(s):
            for row in live:
                _exec_run(row, ch, w)
        self.seg.extend(s)
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
        runs = _row_runs(row, list(self.seg) + list(extra))
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

    def test(self, *, kill: tuple[int, ...] | None = None) -> None:
        """Close the current segment with ``"33"``.

        Rows below 0 ride the NOPs; rows on FALSE skip; rows on TRUE
        re-run the segment to a fixpoint.  With ``kill`` the named row
        must provably loop (it is marked dead) — every other TRUE row
        must still escape, which permits a kill whose descent dips
        bystander rows: they test TRUE once, re-run, and skip on a later
        pass.  Without ``kill`` every TRUE row must escape, or the
        emission is invalid and raises.
        """
        true_rows = [r for r in self.live() if _on_mark(r)]
        for row in true_rows:
            fate = self.fixpoint(row)
            if row.bits == kill:
                if fate != "loop":
                    raise ConstructError(f"kill escaped: row {row.bits}")
                row.dead = True
            elif fate != "skip":
                raise ConstructError(f"unintended loop: row {row.bits}")
        if kill is not None and not any(r.dead and r.bits == kill for r in self.rows):
            raise ConstructError(f"kill missed: row {kill} never tested TRUE")
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


def _predict(
    b: _Builder, seg: str, *, kill: tuple[int, ...] | None = None
) -> set[tuple[int, ...]] | None:
    """Try closing (pending segment + ``seg``) on a clone.

    Returns the TRUE set's row bits on success, ``None`` if any row's
    fate is invalid (an escaped kill, an unintended loop, a stdin read).
    With ``kill`` the named row must loop; every other TRUE row must
    still skip, possibly after re-runs.
    """
    nb = b.clone()
    try:
        live = nb.live()
        for ch, w in _runs(seg):
            for row in live:
                _exec_run(row, ch, w)
        true_rows = [r for r in nb.live() if _on_mark(r)]
        for row in true_rows:
            fate = nb.fixpoint(row, seg)
            if (fate != "loop") if row.bits == kill else (fate != "skip"):
                return None
        return {r.bits for r in true_rows}
    except ConstructError:
        return None


def _true_set_after_walk(b: _Builder, w: int) -> set[tuple[int, ...]] | None:
    """Give the exact TRUE set of closing the pure walk ``"2"*w`` as a test.

    From a normalized state with no pending segment, ``"2"*w + "33"``
    cannot loop (positions strictly increase, so no state revisits) and
    cannot read (``2`` at ``pos >= 0`` never touches the ring), so the
    whole candidate is decidable without simulation: a row is TRUE iff
    its first landing is marked, and its escape chain -- one more walk
    per marked landing -- must fit the fixpoint's 64-re-run cap.
    ``None`` means the shortcut does not apply (a row below zero or a
    pending segment) or the candidate is invalid (a chain past the
    cap); anything else is the verdict :func:`_predict` would return,
    at a few integer ops per row instead of a charged all-rows clone --
    which was 88% of the whole build's work at five inputs.
    """
    live = b.live()
    if b.seg or any(r.pos < 0 for r in live):
        return None
    out = set()
    for r in live:
        p = r.pos + w
        if r.tape >> (p + _RING) & 1:
            out.add(r.bits)
            hops = 0
            while r.tape >> (p + _RING) & 1:
                p += w
                hops += 1
                if hops > 64:
                    return None
    return out


def _normalize(b: _Builder) -> None:
    """Bring every live row to ``pos >= 0``.

    ``1`` when a row sits at -3 (its wrap frees the cell the next ``2``
    would read from), ``2`` otherwise.  All four ring cells occupied is an
    absorbing dead state, so the loop raises rather than spinning.
    """
    # Which character comes next depends only on where the rows *are* --
    # ``1`` when some row sits at -3, ``2`` otherwise -- and never on
    # what they have marked.  So the whole string is planned on a plain
    # list of positions, with no tape and no builder clone, and only the
    # finished string is executed (once, through the batched ``run``).
    # This is the difference between planning and simulating: the probe
    # used to run every row's tape through ``_exec_char`` per character,
    # which was 92% of every command the separation stage simulated.
    positions = [r.pos for r in b.live()]
    if all(p >= 0 for p in positions):
        return
    # A live-lock is a repeated position vector, and it is reached almost
    # at once: the step is deterministic and only the four ring cells can
    # hold a negative row, so a cycling state repeats within a handful of
    # steps (measured worst case: nine).  Detecting the repeat ends those
    # calls immediately instead of spinning to a 10000-iteration cap --
    # which is where this loop spent 4.96M of its 4.96M iterations, since
    # the calls that *do* normalize emit only a few characters each.
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


def _distinct_ok(b: _Builder, table: str) -> bool:
    """No two rows with different verdicts may share an exact state."""
    seen: dict[tuple[int, int], tuple[int, ...]] = {}
    for r in b.live():
        key = (r.pos, r.tape)
        if key in seen and seen[key] != r.bits:
            if _table_val(table, seen[key]) == "0" == _table_val(table, r.bits):
                continue
            return False
        seen[key] = r.bits
    return True


def _one_row_collided(b: _Builder, table: str) -> bool:
    """Report whether a live 1-row shares a position with any live row.

    That state is a trap: kills discriminate by position first, so the
    1-rows must stay position-unique.
    """
    grp: dict[int, list[_Row]] = {}
    for r in b.live():
        grp.setdefault(r.pos, []).append(r)
    return any(
        len(g) > 1 and any(_table_val(table, r.bits) == "1" for r in g)
        for g in grp.values()
    )


def _phase_a(b: _Builder, marks: list[int]) -> None:
    """Embed every input, merge back to position 0, and scrub the blob.

    ``marks[i] = P_i + 1`` is where bit ``i``'s tape difference lands;
    the merge choreography works for every fill position ``P``.

    The fill+merge flips the whole interval ``[0, P+1]`` for a 0 row and
    ``[0, P]`` for a 1 row — hundreds of contiguous junk marks per embed,
    which used to push every later closing walk (and so every position)
    far above the cells that still distinguish the rows.  Since all rows
    are position-synchronized after the merge, one more walk-descend-pop
    over ``[0, P+1]`` re-flips the junk identically for every row and
    cancels it, leaving exactly one mark at ``P+1`` per *set* bit:
    after phase A row ``r``'s tape is ``{marks[i] : r.bits[i] == 1}``.
    """
    for i, m in enumerate(marks):
        p = m - 1
        b.run("2" * p)
        b.fill(i)
        b.run("1" * (p + 1) + "212112")
        b.run("2" * m + "1" * (m + 1) + "2")
        if {r.pos for r in b.live()} != {0}:  # pragma: no cover - invariant
            raise ConstructError("merge failed to re-synchronize")


def _separate(b: _Builder, marks: list[int]) -> None:
    """Give every row a unique position by a planned decode tree.

    Phase A leaves all rows at position 0 with tape ``{marks[i] : bit_i}``
    (see :func:`_phase_a`), so separation is a schedule, not a search:
    level ``i`` walks each same-position group — highest first — exactly
    onto mark cell ``marks[i]``, where the ``33`` splits it by bit ``i``
    (set-bit rows re-run the last segment and escape one walk higher).

    Each visit is a shift ``"2"*s + "33"`` followed by a test
    ``"2"*w + "33"``: the escape re-runs only the *last* segment, so the
    escape offset ``w`` is decoupled from the walk-to-the-mark distance
    ``d = s + w``.  With ``w = d // 2`` the escaped rows land strictly
    inside the gap above their group, which

    * never merges two separated groups (each escape stays inside its
      own inter-group window, and the windows are disjoint), and
    * at worst halves the minimum inter-group gap per level, so a base
      mark spacing of ``2**(n+1)`` (see :func:`construct`) guarantees
      every gap is still ``>= 2`` after all ``n`` levels — which is what
      makes this total at every arity.

    Pure right-walk segments never flip a cell, never enter the ring and
    never read stdin, and positions after level ``i`` stay below
    ``2 * marks[i] < marks[i+1]``, so no landing ever chains onto a
    later level's mark.  Every fate is still validated by ``test()``.
    """
    for i, mk in enumerate(marks):
        for _visit in range(2**b.n + 1):
            pending = [p for p in {r.pos for r in b.live()} if p < mk]
            if not pending:
                break
            d = mk - max(pending)
            w = max(1, d // 2)
            if d > w:
                b.run("2" * (d - w))
                b.test()
            b.run("2" * w)
            b.test()
        else:  # pragma: no cover - 2**n groups is the exact worst case
            raise ConstructError(f"level {i} did not converge")
    poss = [r.pos for r in b.live()]
    if len(set(poss)) != len(poss):  # pragma: no cover - invariant
        raise ConstructError("separation left shared positions")


def _gap_fix(b: _Builder, table: str, gap_min: int = 12) -> None:
    """Boost the rows above any too-narrow gap so kills have headroom.

    Best-effort: a gap the boost search cannot widen is left for the
    verdict search's own moves to handle.
    """
    for _ in range(8 * len(b.live()) + 8):
        order = sorted(b.live(), key=lambda r: r.pos)
        boundary = next(
            (lo.pos for lo, hi in pairwise(order) if 0 < hi.pos - lo.pos < gap_min),
            None,
        )
        if boundary is None:
            return
        uppers = {r.bits for r in b.live() if r.pos > boundary}
        for w in range(1, max(r.pos for r in b.live()) + 64):
            if _true_set_after_walk(b, w) != uppers:
                continue
            nb = b.clone()
            nb.run("2" * w)
            nb.test()
            try:
                _normalize(nb)
            except ConstructError:
                continue
            if not _distinct_ok(nb, table):
                continue
            b.chunks, b.seg, b.rows = nb.chunks, nb.seg, nb.rows
            break
        else:
            return


def _after_ones_pop(p: int, tape: int, a: int) -> tuple[int, int] | None:
    """(pos, tape) after ``"1"*a + "2"`` from ``p >= 0``, ``None`` on a read.

    The same closed forms :func:`_exec_run` batches with, but with no
    row, no clone and no work charge: a shallow descent is one XOR and a
    deep one is the ``[0, p]`` flip, a lap parity, and up to three ring
    steps.  This is what lets the kill sweep consider every ``a`` for
    free and pay simulation costs only for candidates that survive the
    screens.  Verified against ``_exec_run`` on 200000 random
    ``(p, tape, a)`` triples with zero mismatches, raises included.
    """
    if a <= p:
        tape ^= ((1 << a) - 1) << (p - a + 1 + _RING)
        return p - a + 1, tape
    tape ^= ((1 << (p + 1)) - 1) << _RING  # the straight part: cells 0..p
    laps, rem = divmod(a - p - 1, 4)
    if laps & 1:
        tape ^= 0b1111  # one lap flips cells -3..0 once each
    for i in range(rem):  # the first `rem` of the cycle -1, -2, -3, 0
        tape ^= 1 << ((-1 - i if i < 3 else 0) + _RING)
    land = (-1, -2, -3, 0)[rem]
    if land == -3:
        return None  # the "2" would read stdin
    return (1 if land == 0 else 0), tape


def _kill_fate(p: int, tape: int, a: int, x: int | None) -> str:
    """Decide a lone row's fate under ``"1"*a + "2"`` (+ ``"2"*x + "12"``).

    The kill segment is four straight runs, so a whole fixpoint is
    iterable arithmetically: each pass is one :func:`_after_ones_pop`,
    a walk, and one flip -- O(1) per pass, no clone, no work charge.
    ``"skip"`` means the row escapes (immediately or after re-runs),
    ``"loop"`` a proven state revisit, ``"invalid"`` a stdin read or no
    verdict within the pass cap -- verified against a per-row simulated
    fixpoint on 50000 random ``(p, tape, a, x)`` cases with zero
    mismatches.  Exact only for a row with no pending segment, which is
    how kills are tried; _predict remains the adopting gate either way.
    """
    seen = set()
    for _ in range(65):
        res = _after_ones_pop(p, tape, a)
        if res is None:
            return "invalid"
        p, tape = res
        if x is not None:
            p += x
            tape ^= 1 << (p + _RING)
        if not tape >> (p + _RING) & 1:
            return "skip"
        s = (p, tape)
        if s in seen:
            return "loop"
        seen.add(s)
    return "invalid"


def _try_kill(
    b: _Builder, victim: tuple[int, ...], pad: int, table: str
) -> _Builder | None:
    """Search a kill of ``victim``: pad, descend ``a``, pop, test.

    ``"1"*a + "2"`` tests cell 0 after the ring pop; the mark-anchored
    variant appends ``"2"*X + "12"`` so the tested cell is any low TRUE
    cell ``X`` of the victim — the descent flips X on the way down and
    the trailing ``1`` restores it, making the victim's re-run periodic.
    """
    nb0 = b.clone()
    try:
        if pad:
            nb0.run("2" * pad)
            _close(nb0)
    except ConstructError:
        return None
    v0 = next(r for r in nb0.live() if r.bits == victim)
    if v0.pos < 0:
        return None
    # On a freshly separated state the victim's marks below its position
    # are its set bits -- a handful.  After a few kills the descents have
    # marked hundreds of cells, and sweeping every one of them against
    # every ``a`` was the dominant wall cost of a stalled node, so the
    # anchored variant considers a bounded, spread sample instead.
    below = [c for c in _cells(v0.tape) if 0 <= c < v0.pos]
    if len(below) > 48:
        below = below[:24] + below[24 :: max(1, (len(below) - 24) // 24)]
    xs: list[int | None] = [None, *below]
    prefix_positions = [r.pos for r in nb0.live()]
    state_of = {r.bits: (r.pos, r.tape) for r in nb0.live()}
    for a in range(v0.pos + 1, max(r.pos for r in nb0.live()) + 13):
        # the victim must pop out of the ring at -1/-2, or the '2' reads
        if (a - v0.pos) % 4 not in (1, 2):
            continue
        # Every candidate for this ``a`` shares the prefix "1"*a + "2"
        # and then walks right, so the whole x-sweep rides one advancing
        # state instead of re-simulating the prefix (hundreds of
        # commands over every live row) once per x.
        #
        # A prefix whose pop would read stdin kills the whole ``a``, and
        # that is decidable from the live positions alone -- which is
        # most of them, and used to be paid for with a full descent per
        # row before the raise surfaced.
        if _ones_then_pop_reads(prefix_positions, a):
            continue
        dipped = {r.bits for r in nb0.live() if r.pos < a}
        # The whole prefix is arithmetic (see _after_ones_pop), so every
        # candidate ``a`` costs a few int ops per row instead of a full
        # descent through _exec_run -- which, charged at ``a`` commands
        # per row per candidate, used to burn the entire work budget on
        # sweeps at five inputs before a single kill was adopted.
        head_rows: list[_PlanRow] = []
        for r in nb0.live():
            res = _after_ones_pop(r.pos, r.tape, a)
            if res is None:  # pragma: no cover - screened above
                head_rows = []
                break
            head_rows.append((r.bits, res[0], res[1]))
        if not head_rows:
            continue  # pragma: no cover - screened above
        v_land = next(p for bits, p, _ in head_rows if bits == victim)
        for x in xs:
            seg = ("1" * a + "2") if x is None else ("1" * a + "2" + "2" * x + "12")
            # The victim's re-run can only revisit a state if each pass
            # returns it to the cell it tests: the second descent starts
            # at that cell, so it must pop at -1/-2 (anchored variant)
            # or land back where the first pop left it (plain variant).
            # A candidate with the wrong residue *drifts* instead, and
            # its fixpoint burns the full 64 passes before failing --
            # which is where the whole work budget went at five inputs.
            if x is None:
                land2 = _pos_after_ones(v_land, a)
                nxt = 0 if land2 in (-1, -2) else 1 if land2 == 0 else None
                if nxt != v_land:
                    continue
            elif _pos_after_ones(x, a) not in (-1, -2):
                continue
            # The walk and the closing "12" are arithmetic too: the
            # ``1`` toggles cell ``p`` and steps to ``p - 1``, the ``2``
            # steps back (or out of the ring to 0).  From ``pos >= 0``
            # it can never read stdin, so there is no failure to catch.
            true_set = set()
            if x is None:
                for bits, p, tape in head_rows:
                    if tape >> (p + _RING) & 1:
                        true_set.add(bits)
            else:
                for bits, p, tape in head_rows:
                    q = p + x - 1
                    tape ^= 1 << (p + x + _RING)
                    q = 0 if q in (-1, -2) else q + 1
                    if tape >> (q + _RING) & 1:
                        true_set.add(bits)
            # Nearly all of the kill sweep's candidates are rejected on
            # this set alone, so it is checked before the fixpoint
            # screens.  The victim must test TRUE; a bystander the
            # descent *dipped* below zero may also test TRUE -- it skips
            # on a later pass, and _predict validates exactly that fate
            # -- but a TRUE row the descent left standing drifts left on
            # every re-run instead of settling, so those candidates are
            # rejected before any fixpoint is paid for.
            if victim not in true_set:
                continue
            if any(bits not in dipped for bits in true_set - {victim}):
                continue
            # Per-row fate screens before the all-rows validation: at
            # five inputs eighteen thousand candidates per kill reached
            # _predict with a bystander whose fate then failed, and each
            # paid every live row's simulation -- then per-row *charged*
            # simulation still drained the budget at 15k commands per
            # fate, so the fates are arithmetic now (_kill_fate).
            if any(
                _kill_fate(*state_of[bits], a, x) != "skip"
                for bits in true_set - {victim}
            ):
                continue
            if _kill_fate(*state_of[victim], a, x) != "loop":
                continue
            if _predict(nb0, seg, kill=victim) is None:
                continue
            nb = nb0.clone()
            nb.run(seg)
            nb.test(kill=victim)
            try:
                _close(nb)
            except ConstructError:
                continue
            # Rows the kill leaves at a shared position are fine as long
            # as no two of them share the *exact* state with different
            # verdicts: later kills discriminate by tape as well as by
            # position, and every adopted move keeps proving itself.
            if not _distinct_ok(nb, table):
                continue
            return nb
    return None


#: A planning row: ``(bits, pos, tape)``.  Pure right-walk tests never
#: change a tape, so a whole chain of them can be planned on these
#: triples and materialized through the real builder once, on success.
type _PlanRow = tuple[tuple[int, ...], int, int]


def _walk_plan(
    state: list[_PlanRow], w: int
) -> tuple[list[_PlanRow], set[tuple[int, ...]]] | None:
    """Exact post-state and TRUE set of the test ``"2"*w + "33"``.

    A TRUE row escapes one more walk per marked landing; a chain past
    the fixpoint's 64-re-run cap invalidates the candidate (``None``),
    exactly as the simulated close would have raised.
    """
    out: list[_PlanRow] = []
    true_set: set[tuple[int, ...]] = set()
    for bits, p, tape in state:
        q = p + w
        if tape >> (q + _RING) & 1:
            true_set.add(bits)
            hops = 0
            while tape >> (q + _RING) & 1:
                q += w
                hops += 1
                if hops > 64:
                    return None
        out.append((bits, q, tape))
    return out, true_set


def _plan_ok(state: list[_PlanRow], table: str, *, ones_unique: bool) -> bool:
    """Run the planned analogues of ``_distinct_ok`` and ``_one_row_collided``."""
    seen: dict[tuple[int, int], tuple[int, ...]] = {}
    for bits, p, tape in state:
        key = (p, tape)
        if (
            key in seen
            and seen[key] != bits
            and not (_table_val(table, seen[key]) == "0" == _table_val(table, bits))
        ):
            return False
        seen[key] = bits
    if ones_unique:
        grp: dict[int, list[tuple[int, ...]]] = {}
        for bits, p, _ in state:
            grp.setdefault(p, []).append(bits)
        if any(
            len(g) > 1 and any(_table_val(table, bb) == "1" for bb in g)
            for g in grp.values()
        ):
            return False
    return True


def _materialize_walks(b: _Builder, ws: list[int]) -> _Builder | None:
    """Emit a planned chain of walk-tests on a clone, model-validated."""
    nb = b.clone()
    try:
        for w in ws:
            nb.run("2" * w)
            nb.test()
    except ConstructError:  # pragma: no cover - the plan is exact
        return None
    return nb


def _boost_row(
    b: _Builder, u: tuple[int, ...], above: int, table: str
) -> _Builder | None:
    """Move row ``u`` past ``above`` with tests whose TRUE set is ``{u}``.

    Planned on triples and materialized once, like :func:`_group_boost`.
    """
    state = [(r.bits, r.pos, r.tape) for r in b.live()]
    ws: list[int] = []
    for _ in range(64):
        u_pos, u_tape = next((p, t) for bits, p, t in state if bits == u)
        if u_pos > above:
            return _materialize_walks(b, ws)
        top = max(p for _, p, _ in state)
        for w in range(1, top + 48):
            # cheap screen: the boosted row itself must test TRUE at +w
            if not u_tape >> (u_pos + w + _RING) & 1:
                continue
            res = _walk_plan(state, w)
            if res is None or res[1] != {u}:
                continue
            if not _plan_ok(res[0], table, ones_unique=False):
                continue
            state = res[0]
            ws.append(w)
            break
        else:
            return None
    return None


def _group_boost(b: _Builder, victim: tuple[int, ...], table: str) -> _Builder | None:
    """Lift the victim's blockers in bulk until it is the minimum.

    A boost's TRUE set need not be a single row: any test whose TRUE set
    excludes the victim moves floor out from under it wholesale, which
    turns a mid-pack victim into the bottom row in a handful of moves
    instead of one campaign per blocker.

    The chain is planned on ``(bits, pos, tape)`` triples -- pure walks
    never change a tape, so each candidate is a few bit tests -- and
    materialized through the real builder only once, on success.  The
    incremental version simulated every adopted inner step on a clone,
    which at five inputs charged ~30M commands per *rejected* call and
    was, after everything else got cheap, 88% of the whole build.
    """
    state = [(r.bits, r.pos, r.tape) for r in b.live()]
    ws: list[int] = []
    for _ in range(64):
        v_pos, v_tape = next((p, t) for bits, p, t in state if bits == victim)
        if all(p > v_pos for bits, p, _ in state if bits != victim):
            break
        top = max(p for _, p, _ in state)
        for w in range(1, top + 48):
            # the victim must skip, and at least one blocker must jump
            if v_tape >> (v_pos + w + _RING) & 1:
                continue
            if not any(
                t >> (p + w + _RING) & 1
                for bits, p, t in state
                if p <= v_pos and bits != victim
            ):
                continue
            res = _walk_plan(state, w)
            if res is None:
                continue
            plan, tb = res
            # Screened above: a row joins the TRUE set exactly when its
            # first landing is marked (verified against _walk_plan on
            # 300000 random cases), so the screen that requires the
            # victim to skip already keeps it out of `tb`, and the one
            # that requires a blocker to jump already makes `tb`
            # non-empty.  Kept as the plan's own statement of what it
            # needs rather than as a live exit.
            if not tb or victim in tb:  # pragma: no cover - screened above
                continue
            if not _plan_ok(plan, table, ones_unique=True):
                continue
            state = plan
            ws.append(w)
            break
        else:
            return None
    else:
        return None
    return _materialize_walks(b, ws)


def _ring_round(b: _Builder, table: str, x: int, depth: int) -> _Builder | None:
    """Pad, descend past the bottom row, pop.

    Reshuffles relative residues mod 4 — the one thing plain walks
    cannot change.
    """
    nb = b.clone()
    try:
        if x:
            nb.run("2" * x)
        lo = min(r.pos for r in nb.live())
        nb.run("1" * (lo + 2 + depth))
        nb.run("2")
        _normalize(nb)
        _close(nb)
    except ConstructError:
        return None
    if _one_row_collided(nb, table) or not _distinct_ok(nb, table):
        return None
    return nb


def _align_residues(b: _Builder, table: str) -> None:
    """Best-effort: leave at most three residue classes mod 4 occupied.

    A deep descend-and-pop is only valid when the dipped rows leave one
    ring cell free for the pop's ``2``; bottom ring rounds give the
    lowest entity +1 mod 4 per round, which usually frees a class in a
    few tries.  Failure is acceptable — the verdict search still has its
    shallow moves.
    """
    for _ in range(16):
        if len({r.pos % 4 for r in b.live()}) < 4:
            return
        nb = b.clone()
        try:
            lo = min(r.pos for r in nb.live())
            nb.run("1" * (lo + 2))
            nb.run("2")
            _normalize(nb)
            _close(nb)
        except ConstructError:
            return
        if _one_row_collided(nb, table) or not _distinct_ok(nb, table):
            return
        b.chunks, b.seg, b.rows = nb.chunks, nb.seg, nb.rows


def _moves(b: _Builder, table: str, ones: list[_Row]) -> Iterator[_Builder]:
    """Yield successor states, best first.

    A few cheap kill pads for the lowest victims, then boosts of the
    rows blocking the lowest victim (a mid-pack victim rarely dies
    before its floor is cleared), then ring-round shuffles, then the
    kill pads for every victim.  Ordering here is purely a cost
    heuristic: the search backtracks, so it changes which trajectory is
    found first, never what is reachable.  The first family stops at
    the three lowest victims because the schedule is bottom-up anyway:
    when the bottom rows are dirty enough to poison every dipped-kill
    fate, sweeping all fifteen victims' doomed kills before the first
    boost was minutes of wall time per node.
    """
    order = sorted(ones, key=lambda r: r.pos)
    for victim in order[:3]:
        for pad in range(3):
            nb = _try_kill(b, victim.bits, pad, table)
            if nb is not None:
                yield nb
    victim = min(ones, key=lambda r: r.pos)
    nb = _group_boost(b, victim.bits, table)
    if nb is not None:
        yield nb
    blockers = sorted(
        (r for r in b.live() if r.bits != victim.bits and r.pos <= victim.pos + 24),
        key=lambda r: r.pos,
    )
    for u in blockers:
        top = max(r.pos for r in b.live())
        nb = _boost_row(b, u.bits, top + 8, table)
        if nb is not None:
            yield nb
    # ring rounds before the deep kill pads: a row that has only ever
    # walked right has no TRUE cell above its position, so on a fresh
    # state no boost can fire until a descend-and-pop deposits one.  The
    # depths are taken from the blockers' own positions — a bottom-only
    # dip leaves every mid-pack blocker dirtless and unboostable — and
    # dipped 0-rows may collide freely, since only the victim's position
    # must stay unique.
    lo = min(r.pos for r in b.live())
    depths = sorted({0, 4} | {r.pos - lo for r in blockers})
    for depth in depths:
        for x in range(4):
            nb = _ring_round(b, table, x, depth)
            if nb is not None:
                yield nb
    for victim in order:
        for pad in range(12):
            if victim in order[:3] and pad < 3:
                continue  # the first family already tried these
            nb = _try_kill(b, victim.bits, pad, table)
            if nb is not None:
                yield nb


def _verdict_search(b: _Builder, table: str, budget: int = 0) -> _Builder | None:
    """Bounded depth-first search until every 1-row is provably looping.

    Backtracking keeps any previously working trajectory reachable, so a
    fixed move set cannot regress a table that built; the budget bounds
    the whole search, and exhausting it raises upstream rather than
    emitting anything.  The default budget scales with the number of
    rows: a table can need one kill per 1-row, and each may take a few
    preparatory moves, so a flat cap would starve wide arities.
    """
    if not budget:
        budget = 300 + 60 * len(b.live())
    seen: set[tuple[tuple[int, tuple[int, ...], int], ...]] = set()
    spent = [0]

    def sig(bb: _Builder) -> tuple[tuple[int, tuple[int, ...], int], ...]:
        # ``r.bits`` is unique per row, so the tape never decides the
        # sort order -- this is the same signature the set-tape build
        # produced, with the mask standing in for the frozenset.
        return tuple(sorted((r.pos, r.bits, r.tape) for r in bb.live()))

    def dfs(bb: _Builder) -> _Builder | None:
        ones = [r for r in bb.live() if _table_val(table, r.bits) == "1"]
        if not ones:
            return bb
        if spent[0] >= budget:
            return None
        s = sig(bb)
        if s in seen:
            return None
        seen.add(s)
        spent[0] += 1
        for nb in _moves(bb, table, ones):
            res = dfs(nb)
            if res is not None:
                return res
            if spent[0] >= budget:
                return None
        return None

    return dfs(b.clone())


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


def _replay(template: str, n: int, table: str) -> None:
    """Run every instantiation on the real interpreter.

    Raises on any wrong verdict: the builder's model is exact, but
    nothing ships on the model's word alone.
    """
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.one_two_three import _Machine

    for combo in range(2**n):
        bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
        program = template
        for i, bit in enumerate(bits):
            program = program.replace(f"{{X{i}}}", _ONE if bit else _ZERO)
        machine = _Machine(program, ScriptedIO(""))
        verdict = None
        # Brent's cycle detection, with the cheap fields compared first:
        # a snapshot()-per-step set works at four inputs, but a wider
        # template is hundreds of thousands of commands and its tape
        # holds thousands of set cells, so hashing a sorted tuple of
        # them every step made the closing gate cost more than the whole
        # build.  Here a step costs an (ip, pos) compare, the tape is
        # only compared on those rare matches, and states are saved just
        # at power-of-two step counts.  The cap scales with the template
        # (a flat 500000 ran out mid-execution at six inputs and called
        # a halting row None); it only guards against a build bug making
        # a row diverge without ever revisiting a state.
        power = lam = 1
        saved: tuple[int, int, frozenset[int], int] | None = None
        for _ in range(64 * len(program) + 500000):
            if machine.halted:
                verdict = "0"
                break
            ip, pos, cells, _done = machine.state
            if (
                saved is not None
                and lam
                and saved[:2] == (ip, pos)
                and saved[2] == frozenset(cells)
                and saved[3] == machine.io.position()
            ):
                verdict = "1"
                break
            if power == lam:
                saved = (ip, pos, frozenset(cells), machine.io.position())
                power *= 2
                lam = 0
            lam += 1
            machine.step()
        if verdict != table[combo]:  # pragma: no cover - the gate
            raise ConstructError(f"replay disagrees at row {bits}: {verdict!r}")


#: Simulated commands a :func:`construct` call may spend before raising.
#: Counted work, not wall clock, so the same table either builds or
#: raises identically on every machine.
#:
#: The counter is charged for what is actually simulated -- candidate
#: screens that run on arithmetic (the kill sweep's prefix, fates, and
#: tails) charge nothing, so the budget buys adopted moves and their
#: validation rather than rejected candidates.  It is never read by a
#: search decision -- only tested against zero to abort -- so a table
#: that built before still emits the same template, and what a cheaper
#: sweep changes is which tables get far enough to finish at all.  The
#: budget is what keeps a table whose search cannot converge bounded
#: instead of endless; :func:`construct` scales it with the row count
#: so it stays a divergence guard rather than an arity ceiling.
_WORK_BUDGET = 2_000_000_000


def construct(truth_table: str, *, verify: bool = True) -> str:
    """Build a 123 template for ``truth_table`` at any arity.

    Deterministic; every emitted template is replayed row by row on the
    real interpreter before it is returned.  Raises :class:`ValueError`
    when a search stage exhausts its move budget or the whole build
    exhausts its work budget — no unproven template is ever produced.

    ``verify=False`` skips that closing replay, which is 40-65% of a
    four-input build (the program is long, and running it sixteen times
    is most of the work).  It exists for callers that replay the result
    themselves anyway — the wider tests here do, and paying for both is
    the same execution twice.  The default stays ``True``: this is the
    only execution gate the constructed route has, since the exhaustive
    sweeps in the suite cover ``n <= 3``, which the stored plans serve
    without ever calling this.  A caller that skips it and does not
    check the template itself is shipping an unproven program.
    """
    n = max(1, (len(truth_table) - 1).bit_length())
    failure: str | None = None
    # Two mark geometries, tried in order.  The base must be at least
    # 2**(n+1): separation halves its minimum inter-group gap once per
    # level, and every gap has to survive all n levels at >= 2 (see
    # _separate); the tripling keeps each level's escapes below the
    # next level's mark.  The two layouts differ in the marks' residues
    # mod 4: an anchored kill needs its test cell to satisfy a residue
    # constraint the dipped bystanders pin, so under either single
    # layout some victim/bystander parity patterns starve the kill
    # sweep -- measured both ways: the uniform +1 exhausts on a table
    # the staggered +1/+3 solves in seconds, and vice versa.  Trying
    # both is deterministic and strictly stronger than either.
    for stagger in (0, 1):
        # The budget still bounds a diverging search, but everything
        # about a wider table is exponentially bigger -- rows, template
        # length, kill sweeps -- so the cap scales with the row count
        # (per attempt) to stay a divergence guard, not an arity
        # ceiling.  Deterministic either way.
        _work[0] = _WORK_BUDGET * max(1, 2 ** (n - 4))
        try:
            b = _Builder(n)
            marks = [2 ** (n + 1) * 3**i + 1 + 2 * (i & 1) * stagger for i in range(n)]
            _phase_a(b, marks)
            _close(b)
            _separate(b, marks)
            _gap_fix(b, truth_table)
            _align_residues(b, truth_table)
            result = _verdict_search(b, truth_table)
            if result is None:
                raise ConstructError("verdict search exhausted its budget")
            b = result
            _endgame(b)
            template = b.template()
            if verify:
                _replay(template, n, truth_table)
            return template
        except _WorkExhaustedError:
            failure = "the work budget ran out before the searches converged"
        except ConstructError as exc:
            failure = str(exc)
    raise ValueError(f"123 construction failed for {truth_table!r}: {failure}")
