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

1. **Embed** (`_phase_a`): walk to ``P_i``, emit ``{Xi}``, merge.  Each
   bit lands at a fixed mark cell; all ``2**n`` rows share one position.
2. **Separate** (`_separate`): close the segment, then split same-position
   row groups by testing mark cells until every row's position is unique.
   A test is a segment closed by ``"33"``: rows on a FALSE cell skip, rows
   on a TRUE cell re-run the segment to a fixpoint and exit offset.
3. **Verdict** (`_verdict_search`): a bounded depth-first search over
   three move kinds — a *kill* (the segment ``"1"*a + "2"`` or its
   mark-anchored variant ``"1"*a + "2" + "2"*X + "12"``, which loops the
   one row that dips into the -1..-3 ring and tests TRUE, by a proven
   periodic revisit), a *boost* (a plain test whose TRUE set excludes
   the victim, moving blockers out of the way singly or in bulk), and a
   *ring round* (descend, pop, reshuffle relative residues, depositing
   the above-position marks boosts need).  Backtracking keeps every previously
   working trajectory reachable, so the move set cannot regress a table
   that once built.
4. **Endgame** (`_endgame`): survivors need ``pos < 0`` at end of code.
   A deep descent drops everyone into the ring, where same-residue rows
   fuse; once some residue class mod 4 is free the final ``"1"*k`` parks
   every survivor on a negative ring cell and the program halts.

Every candidate move is validated on an exact tracked model of all rows
before it is emitted, and :func:`construct` replays every row of the
finished template on the real interpreter before returning it — a wrong
program is never handed out; an exhausted search raises instead.
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


def _union_tape(rows: list[_Row]) -> int:
    """Every cell any row in ``rows`` has marked."""
    u = 0
    for r in rows:
        u |= r.tape
    return u


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

    def test(self, *, kill: bool = False) -> None:
        """Close the current segment with ``"33"``.

        Rows below 0 ride the NOPs; rows on FALSE skip; rows on TRUE
        re-run the segment to a fixpoint.  With ``kill`` the TRUE rows
        must provably loop (they are marked dead); without it they must
        escape, or the emission is invalid and raises.
        """
        true_rows = [r for r in self.live() if _on_mark(r)]
        for row in true_rows:
            fate = self.fixpoint(row)
            if kill:
                if fate != "loop":
                    raise ConstructError(f"kill escaped: row {row.bits}")
                row.dead = True
            elif fate != "skip":
                raise ConstructError(f"unintended loop: row {row.bits}")
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
    b: _Builder, seg: str, *, kill: bool = False
) -> set[tuple[int, ...]] | None:
    """Try closing (pending segment + ``seg``) on a clone.

    Returns the TRUE set's row bits on success, ``None`` if any row's
    fate is invalid (an escaped kill, an unintended loop, a stdin read).
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
            if (fate != "loop") if kill else (fate != "skip"):
                return None
        return {r.bits for r in true_rows}
    except ConstructError:
        return None


def _true_set_after_walk(b: _Builder, w: int) -> set[tuple[int, ...]] | None:
    """Return the TRUE set a ``"2"*w`` candidate lands on, or ``None``.

    From a normalized state ``"2"*w`` is a pure ``pos += w`` for every
    row, so which rows end up on a marked cell is a bit test per row --
    no simulation.  This is only a *screen*: it says nothing about the
    fixpoints the closing ``"33"`` then runs, so a match still goes to
    :func:`_predict` for the real verdict.  ``None`` means the state is
    not normalized and the shortcut does not apply.
    """
    live = b.live()
    if any(r.pos < 0 for r in live):
        return None
    return {r.bits for r in live if r.tape >> (r.pos + w + _RING) & 1}


def _normalize(b: _Builder) -> None:
    """Bring every live row to ``pos >= 0``.

    ``1`` when a row sits at -3 (its wrap frees the cell the next ``2``
    would read from), ``2`` otherwise.  All four ring cells occupied is an
    absorbing dead state, so the loop raises rather than spinning.
    """
    # The decision is per character, but emitting it through ``run`` one
    # character at a time was the single hottest path in the whole build
    # (4.96M calls, 92% of the separation stage at n == 4): every call
    # rebuilt the live list, re-split the string into runs and appended a
    # chunk.  Deciding on a scratch clone and emitting the whole string
    # once is the same string, hence the same template.
    probe = b.clone()
    out: list[str] = []
    for _ in range(10000):
        live = probe.live()
        if all(r.pos >= 0 for r in live):
            if out:
                b.run("".join(out))
            return
        ch = _ONE if any(r.pos == -3 for r in live) else _ZERO
        out.append(ch)
        for row in live:
            _exec_char(row, ch)
    raise ConstructError("normalize live-locked")


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
    """Embed every input with a merge back to position 0.

    ``marks[i] = P_i + 1`` is where bit ``i``'s tape difference lands;
    the merge choreography works for every fill position ``P``.
    """
    for i, m in enumerate(marks):
        p = m - 1
        b.run("2" * p)
        b.fill(i)
        b.run("1" * (p + 1) + "212112")
        if {r.pos for r in b.live()} != {0}:  # pragma: no cover - invariant
            raise ConstructError("merge failed to re-synchronize")


def _separate(b: _Builder, table: str) -> None:
    """Split same-position groups until every position is unique.

    Rows still sharing a full state after that must all be 0-rows.
    Candidates test a cell where the group's tracked tapes differ, low
    cells first so the offsets stay bounded; a candidate is adopted
    eagerly when it reduces collision mass, and the first merely-valid
    one is kept as a fallback.  When a group offers no candidate at all,
    a bounded number of ring rounds reshuffle relative residues and the
    scan retries — the same escape the verdict search uses.
    """
    retries = 0

    def badness(bb: _Builder) -> int:
        grp: dict[int, list[_Row]] = {}
        for r in bb.live():
            grp.setdefault(r.pos, []).append(r)
        return sum(
            len(g) - 1
            for g in grp.values()
            if len(g) > 1
            and (
                len({r.tape for r in g}) > 1
                or len({_table_val(table, r.bits) for r in g}) > 1
            )
        )

    for _ in range(16 * 4**b.n):
        _normalize(b)
        grp: dict[int, list[_Row]] = {}
        for r in b.live():
            grp.setdefault(r.pos, []).append(r)
        multis = [
            (p, g)
            for p, g in grp.items()
            if len(g) > 1
            and (
                len({r.tape for r in g}) > 1
                or len({_table_val(table, r.bits) for r in g}) > 1
            )
        ]
        if not multis:
            return
        p, g = max(multis)
        cells = sorted(
            c
            for c in _cells(_union_tape(g))
            if len({r.tape >> (c + _RING) & 1 for r in g}) > 1
        )
        if not cells:
            raise ConstructError(f"group at {p} is state-identical")
        base_bad = badness(b)
        fallback: _Builder | None = None
        adopted = False
        for c in cells:
            for x in range(8):
                if c >= p + x:
                    if x:
                        continue  # pads are redundant for right walks
                    seg = "2" * (c - p)
                else:
                    seg = "2" * x + "1" * (p + x - c)
                if _predict(b, seg) is None:
                    continue
                nb = b.clone()
                nb.run(seg)
                nb.test()
                try:
                    _normalize(nb)
                except ConstructError:
                    continue
                if not _distinct_ok(nb, table):
                    continue
                if badness(nb) < base_bad:
                    b.chunks, b.seg, b.rows = nb.chunks, nb.seg, nb.rows
                    adopted = True
                    break
                if fallback is None:
                    fallback = nb
            if adopted:
                break
        if not adopted:
            if fallback is not None:
                b.chunks, b.seg, b.rows = (fallback.chunks, fallback.seg, fallback.rows)
                continue
            if retries >= 20:
                raise ConstructError(f"no split for the group at {p}")
            nb = b.clone()
            try:
                lo = min(r.pos for r in nb.live())
                nb.run("1" * (lo + 2 + (retries % 3) * 4))
                nb.run("2")
                _normalize(nb)
                _close(nb)
            except ConstructError:
                raise ConstructError(f"no split for the group at {p}") from None
            if not _distinct_ok(nb, table):
                raise ConstructError(f"no split for the group at {p}")
            retries += 1
            b.chunks, b.seg, b.rows = nb.chunks, nb.seg, nb.rows
    raise ConstructError("separation did not converge")


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
            screen = _true_set_after_walk(b, w)
            if screen is not None and screen != uppers:
                continue
            if _predict(b, "2" * w) != uppers:
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


def _victim_loops(b: _Builder, victim: tuple[int, ...], seg: str) -> bool:
    """Screen one row cheaply: the victim must test TRUE, then loop."""
    src = next(r for r in b.rows if r.bits == victim)
    row = _Row(src.bits)
    row.pos, row.tape = src.pos, src.tape
    runs = _row_runs(row, list(b.seg) + list(seg))

    def one_pass() -> None:
        for ch, w in runs:
            _exec_run(row, ch, w)

    try:
        one_pass()
        if row.pos < 0 or not row.tape >> (row.pos + _RING) & 1:
            return False
        seen = {(row.pos, row.tape)}
        for _ in range(64):
            one_pass()
            if row.pos < 0 or not row.tape >> (row.pos + _RING) & 1:
                return False
            s = (row.pos, row.tape)
            if s in seen:
                return True
            seen.add(s)
        return False
    except ConstructError:
        return False


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
    xs: list[int | None] = [None]
    xs += [c for c in _cells(v0.tape) if 0 <= c < v0.pos]
    for a in range(v0.pos + 1, max(r.pos for r in nb0.live()) + 13):
        # the victim must pop out of the ring at -1/-2, or the '2' reads
        if (a - v0.pos) % 4 not in (1, 2):
            continue
        # Every candidate for this ``a`` shares the prefix "1"*a + "2"
        # and then walks right, so the whole x-sweep rides one advancing
        # state instead of re-simulating the prefix (hundreds of
        # commands over every live row) once per x.
        try:
            head = nb0.clone()
            head_live = head.live()
            for ch, w in _runs("1" * a + "2"):
                for row in head_live:
                    _exec_run(row, ch, w)
        except ConstructError:
            continue
        # The right-walk that carries the shared state from one x to the
        # next cannot raise: every row sits at pos >= 0 after the pop
        # (a row still in the ring would have raised in the prefix, which
        # every candidate executes, so the whole ``a`` is skipped above),
        # and ``2`` from pos >= 0 only ever increments.  Only the "12"
        # tail can raise, and it runs on a throwaway clone.
        walked = 0
        for x in xs:
            seg = ("1" * a + "2") if x is None else ("1" * a + "2" + "2" * x + "12")
            if x is not None:
                for row in head_live:
                    _exec_run(row, _ZERO, x - walked)
                walked = x
            tail = head.clone()
            tail_live = tail.live()
            try:
                if x is not None:
                    for ch in "12":
                        for row in tail_live:
                            _exec_char(row, ch)
            except ConstructError:
                continue
            # 100% of the kill sweep's candidates were rejected on this
            # set alone, so it is checked before the fixpoint screens
            # that used to run first.  Rejections are unobservable, so
            # reordering them cannot change which candidate is adopted.
            if {r.bits for r in tail.live() if _on_mark(r)} != {victim}:
                continue
            if not _victim_loops(nb0, victim, seg):
                continue
            if _predict(nb0, seg, kill=True) != {victim}:
                continue
            nb = nb0.clone()
            nb.run(seg)
            nb.test(kill=True)
            try:
                _close(nb)
            except ConstructError:
                continue
            if _one_row_collided(nb, table):
                continue
            return nb
    return None


def _boost_row(
    b: _Builder, u: tuple[int, ...], above: int, table: str
) -> _Builder | None:
    """Move row ``u`` past ``above`` with tests whose TRUE set is ``{u}``."""
    nb = b.clone()
    for _ in range(64):
        row = next(r for r in nb.live() if r.bits == u)
        if row.pos > above:
            return nb
        for w in range(1, max(r.pos for r in nb.live()) + 48):
            # cheap screen: the boosted row itself must test TRUE at +w
            if not row.tape >> (row.pos + w + _RING) & 1:
                continue
            screen = _true_set_after_walk(nb, w)
            if screen is not None and screen != {u}:
                continue
            if _predict(nb, "2" * w) != {u}:
                continue
            cand = nb.clone()
            cand.run("2" * w)
            cand.test()
            try:
                _normalize(cand)
            except ConstructError:
                continue
            if not _distinct_ok(cand, table):
                continue
            nb = cand
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
    """
    nb = b.clone()
    for _ in range(64):
        v = next(r for r in nb.live() if r.bits == victim)
        if all(r.pos > v.pos for r in nb.live() if r.bits != victim):
            return nb
        moved = False
        for w in range(1, max(r.pos for r in nb.live()) + 48):
            below = [r for r in nb.live() if r.pos <= v.pos and r.bits != victim]
            # the victim must skip, and at least one blocker must jump
            if v.tape >> (v.pos + w + _RING) & 1:
                continue
            if not any(r.tape >> (r.pos + w + _RING) & 1 for r in below):
                continue
            screen = _true_set_after_walk(nb, w)
            if screen is not None and (not screen or victim in screen):
                continue
            tb = _predict(nb, "2" * w)
            if not tb or victim in tb:
                continue
            cand = nb.clone()
            cand.run("2" * w)
            cand.test()
            try:
                _normalize(cand)
            except ConstructError:
                continue
            if not _distinct_ok(cand, table) or _one_row_collided(cand, table):
                continue
            nb = cand
            moved = True
            break
        if not moved:
            return None
    return None


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

    A few cheap kill pads, then boosts of the rows blocking the lowest
    victim (a mid-pack victim rarely dies before its floor is cleared),
    then ring-round shuffles, then the deeper kill pads.  Ordering here
    is purely a cost heuristic: the search backtracks, so it changes
    which trajectory is found first, never what is reachable.
    """
    for victim in sorted(ones, key=lambda r: r.pos):
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
    for victim in sorted(ones, key=lambda r: r.pos):
        for pad in range(3, 12):
            nb = _try_kill(b, victim.bits, pad, table)
            if nb is not None:
                yield nb


def _verdict_search(b: _Builder, table: str, budget: int = 300) -> _Builder | None:
    """Bounded depth-first search until every 1-row is provably looping.

    Backtracking keeps any previously working trajectory reachable, so a
    fixed move set cannot regress a table that built; the budget bounds
    the whole search, and exhausting it raises upstream rather than
    emitting anything.
    """
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
        seen: set[tuple[object, ...]] = set()
        verdict = None
        for _ in range(500000):
            if machine.halted:
                verdict = "0"
                break
            s = machine.snapshot()
            if s in seen:
                verdict = "1"
                break
            seen.add(s)
            machine.step()
        if verdict != table[combo]:  # pragma: no cover - the gate
            raise ConstructError(f"replay disagrees at row {bits}: {verdict!r}")


#: Simulated commands a :func:`construct` call may spend before raising.
#: Counted work, not wall clock, so the same table either builds or
#: raises identically on every machine.
#:
#: The counter is charged for what is actually simulated, so sharing a
#: candidate sweep's prefix buys real search depth rather than only wall
#: time.  It is never read by a search decision -- only tested against
#: zero to abort -- so a table that built before still emits the same
#: template, and what a cheaper sweep changes is which tables get far
#: enough to finish at all.  Four-input tables build within it, sparse
#: and dense alike (measured 40-80s each); the budget is what keeps a
#: table whose search cannot converge bounded instead of endless.
_WORK_BUDGET = 2_000_000_000


def construct(truth_table: str, spacing: int = 6) -> str:
    """Build a 123 template for ``truth_table`` at any arity.

    Deterministic; every emitted template is replayed row by row on the
    real interpreter before it is returned.  Raises :class:`ValueError`
    when a search stage exhausts its move budget or the whole build
    exhausts its work budget — no unproven template is ever produced.
    """
    n = max(1, (len(truth_table) - 1).bit_length())
    _work[0] = _WORK_BUDGET
    try:
        b = _Builder(n)
        marks = [spacing * 3**i + 1 for i in range(n)]
        _phase_a(b, marks)
        _close(b)
        _separate(b, truth_table)
        _gap_fix(b, truth_table)
        _align_residues(b, truth_table)
        result = _verdict_search(b, truth_table)
        if result is None:
            raise ConstructError("verdict search exhausted its budget")
        b = result
        _endgame(b)
        template = b.template()
        _replay(template, n, truth_table)
    except _WorkExhaustedError:
        raise ValueError(
            f"123 construction failed for {truth_table!r}: the work "
            "budget ran out before the searches converged"
        ) from None
    except ConstructError as exc:
        raise ValueError(f"123 construction failed for {truth_table!r}: {exc}") from exc
    return template
