r"""Constructed 123 templates for four and more inputs."""

from __future__ import annotations

from collections.abc import Iterable
from functools import cache

__all__ = ["ConstructError", "construct"]

# : Fill characters, shared.
_ONE, _ZERO = "1", "2"

# : Bit offset of cell 0 in a.
# : -1..-3, so shifting by.
# : non-negative and lets one.
_RING = 3


def _on_mark(row: _Row) -> bool:
    r"""Report whether ``row`` is parked on one of its own marked cells."""
    return row.pos >= 0 and bool(row.tape >> (row.pos + _RING) & 1)


def _mask(cells: Iterable[int]) -> int:
    r"""Build a tape mask from cell numbers (bit ``c + _RING`` per cell)."""
    m = 0
    for c in cells:
        m |= 1 << (c + _RING)
    return m


# : One emitted token: a.
# : fill slot.
# : of thousands of commands.
# : character made.
# : build (3.5s of 7.3s).
# : nothing that hands the.
type _Token = str | tuple[str, int]


class ConstructError(Exception):
    r"""A stage of the construction found no valid move."""


class _WorkExhaustedError(Exception):
    r"""The deterministic work budget ran out mid-build."""


class _Row:
    r"""Tracked state of one instantiation while the template is built."""

    __slots__ = ("bits", "dead", "pos", "tape")

    # : ``tape`` is a bitmask, not.
    # : ``pos``.
    # : innermost loop, where an.
    # : set operation, and it.
    # : ``frozenset(tape)`` these.
    def __init__(self, bits: tuple[int, ...]) -> None:
        self.bits = bits
        self.pos = 0
        self.tape = 0
        self.dead = False


# : Remaining work budget for.
# : in simulated commands —.
# : builds or raises.
# : decremented in place from.
_work = [0]


def _exec_char(row: _Row, ch: str) -> None:
    r"""Apply one ``1``/``2`` command to a row, mirroring the interpreter."""
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
            row.pos = 0  # prints a junk byte;.
        else:
            row.pos += 1
    else:  # pragma: no cover - the builder only emits 1/2 runs
        raise AssertionError(ch)


def _exec_run(row: _Row, ch: str, w: int) -> None:
    r"""Apply ``ch`` repeated ``w`` times to one row."""
    if w and row.pos >= 0:
        if ch == _ZERO:
            _work[0] -= w
            if _work[0] < 0:
                raise _WorkExhaustedError
            row.pos += w
            return
        if row.pos - w >= -1:
            # A descent that stops at -1 or.
            # exactly "toggle the w cells.
            # the cells pos-w+1..pos are.
            # w-bit mask.
            # at -3 both matter, so that.
            _work[0] -= w
            if _work[0] < 0:
                raise _WorkExhaustedError
            row.tape ^= ((1 << w) - 1) << (row.pos - w + 1 + _RING)
            row.pos -= w
            return
    if ch == _ONE and row.pos >= 0 and w > row.pos + 1:
        # A descent that runs past -1.
        # part above it is the.
        head = row.pos + 1
        _work[0] -= head
        if _work[0] < 0:
            raise _WorkExhaustedError
        row.tape ^= ((1 << head) - 1) << _RING
        row.pos = -1
        w -= head
    if ch == _ONE and w >= 4 and row.pos < 0:
        # Inside the ring ``1`` cycles.
        # period 4, toggling each of.
        # whole number of laps.
        # lap count is even and flips.
        # ``w % 4`` steps have to be.
        # inner loop, where the.
        laps, rest = divmod(w, 4)
        _work[0] -= w - rest
        if _work[0] < 0:
            raise _WorkExhaustedError
        if laps & 1:
            row.tape ^= 0b1111  # cells -3..0, i.e.
        for _ in range(rest):
            _exec_char(row, ch)
        return
    if ch == _ZERO and w and row.pos < 0:
        # ``2`` at -1 or -2 lands on 0.
        # and -3 reads stdin, which is.
        # everything and the remaining.
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
    r"""Resolve ``toks`` for one row and coalesce it into runs."""
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
    r"""``"2211"`` -> ``["22", "11"]``, the maximal runs as substrings."""
    out: list[str] = []
    size = len(s)
    i = 0
    while i < size:
        ch = s[i]
        if ch == _ONE:
            other = _ZERO
        elif ch == _ZERO:
            other = _ONE
        else:  # pragma: no cover - 2**n groups is the exact worst case
            raise AssertionError(ch)
        j = s.find(other, i + 1)
        if j < 0:
            j = size
        out.append(s[i:j])
        i = j
    return out


class _Builder:
    r"""Emits template chunks while tracking every row's exact state."""

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
        r"""Emit straight-line commands; every live row executes them."""
        live = self.live()
        parts = _run_parts(s)
        for part in parts:
            ch, w = part[0], len(part)
            for row in live:
                _exec_run(row, ch, w)
        self.seg.extend(parts)
        self.chunks.append(s)

    def fill(self, i: int) -> None:
        r"""Emit ``{Xi}``; each row executes its own fill character."""
        for row in self.live():
            self.apply_token(row, ("X", i))
        self.seg.append(("X", i))
        self.chunks.append(f"{{X{i}}}")

    def fixpoint(self, row: _Row, extra: str = "") -> str:
        r"""Re-run the pending segment (+ ``extra``) until the row escapes."""
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
        r"""Close the current segment with ``"33"``."""
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
    r"""Bring every live row to ``pos >= 0``."""
    # Which character comes next.
    # ``1`` when some row sits at.
    # have marked.
    # positions, with no tape and.
    # string is executed (once,.
    # difference between planning.
    # every row's tape through.
    # command the separation stage.
    positions = [r.pos for r in b.live()]
    if all(p >= 0 for p in positions):
        return
    # A live-lock is a repeated.
    # the step is deterministic and.
    # negative row, so a cycling.
    # (measured worst case: nine).
    # immediately instead of.
    # this loop spent 4.96M of its.
    # *do* normalize emit only a.
    out: list[str] = []
    seen: set[tuple[int, ...]] = {tuple(positions)}
    while True:
        if any(p == -3 for p in positions):
            out.append(_ONE)
            # ``1`` steps left and wraps -4.
            positions = [0 if p == -4 else p for p in (q - 1 for q in positions)]
        else:
            out.append(_ZERO)
            # ``2`` at -3 would read stdin,.
            # cleared -3, so every row here.
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
    r"""Walk right until every live row sits on a FALSE cell, then test."""
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
    r"""Embed every input, merge back to position 0, and scrub the blob."""
    for i, m in enumerate(marks):
        p = m - 1
        b.run("2" * p)
        b.fill(i)
        b.run("1" * (p + 1) + "212112")
        b.run("2" * m + "1" * (m + 1) + "2")
        if {r.pos for r in b.live()} != {0}:  # pragma: no cover - invariant
            raise ConstructError("merge failed to re-synchronize")


def _separate(b: _Builder, marks: list[int], ws: tuple[int, ...] | None = None) -> None:
    r"""Give every row a unique position by a planned decode tree."""
    for i, mk in enumerate(marks):
        for _visit in range(2**b.n + 1):
            pending = [p for p in {r.pos for r in b.live()} if p < mk]
            if not pending:
                break
            d = mk - max(pending)
            w = max(1, d // 2) if ws is None else ws[i]
            if d < w:  # pragma: no cover - the probed arities all pass
                raise ConstructError(f"level {i}: walk {d} under escape {w}")
            # `d < w` is refused above, and.
            # overshoots the escape, so.
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
    r"""Pick arity ``n``'s mark geometry: tight when it proves out."""
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
    # No probed arity reaches this.
    # total by argument at the.
    return tuple(2 ** (n + 1) * 2**i + 1 for i in range(n)), None  # pragma: no cover


def _paint(b: _Builder, k: int) -> None:
    r"""Flip exactly cell ``pos + k`` for every live row, positions kept."""
    if k < 1:  # pragma: no cover - the verdict computes k >= 1
        raise ConstructError(f"paint offset {k} is not above the row")
    b.run("2" * k + "1" * k)
    if k > 1:
        b.run("2" * (k - 1) + "1" * (k - 1))


def _paint_all(b: _Builder, offsets: list[int]) -> None:
    r"""Emit :func:`_paint` at every offset, applying them in one step."""
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
    r"""Shield every 0-row, then loop every 1-row with one planned kill."""
    ones = [r for r in b.live() if _table_val(table, r.bits) == "1"]
    if not ones:
        return
    live = b.live()
    positions = [r.pos for r in live]
    if len(set(positions)) != len(positions) or any(p % 2 == 0 for p in positions):
        # Never observed (separation.
        # the spacing :func:`_geometry`.
        # mark base keeps the gaps.
        # keeps the.
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
    r"""Park every survivor below 0 at the end of the code, so it halts."""
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
    r"""Per ``3`` position, where a backward and a forward jump land."""
    threes = [i for i, c in enumerate(code) if c == "3"]
    back = [0] * len(code)
    fwd = [0] * len(code)
    prev = -1
    for i in threes:
        back[i] = prev + 1  # just after the previous 3, or.
        prev = i
    nxt = len(code)
    for i in reversed(threes):
        fwd[i] = nxt + 1 if nxt < len(code) else len(code)
        nxt = i
    return back, fwd


def _code_runs(code: str) -> tuple[list[int], list[str], list[int]]:
    r"""Index ``code`` into maximal ``1``/``2`` runs."""
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
    r"""Apply ``"1"*w``, per the interpreter's rule for ``1``."""
    while w > 0:
        if pos >= 0:
            head = min(w, pos + 1)
            tape ^= ((1 << head) - 1) << (pos - head + 1 + _RING)
            pos -= head
            w -= head
            # No wrap check here: ``head``.
            # walk stops at -1 at the.
            # wrap belongs to the.
            # only place the pointer steps.
            continue
        laps, rest = divmod(w, 4)
        if laps:
            if laps & 1:
                tape ^= 0b1111  # a lap flips cells -3..0 once.
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
    r"""Apply ``"2"*w``; the first step decides whether the ring is left."""
    if w <= 0:
        return pos, tape
    if pos == -3:
        raise ConstructError("replay: '2' at -3 reads stdin")
    if pos in (-1, -2):
        pos = 0
        w -= 1
    return pos + w, tape


def _replay_verdict(code: str) -> str:
    r"""Execute one instantiated program: ``"0"`` halts, ``"1"`` loops."""
    if not any(c in "123" for c in code):
        return "0"  # a command-less program halts.
    back, fwd = _jump_tables(code)
    run_at, run_ch, run_end = _code_runs(code)
    size = len(code)
    ip = pos = tape = 0
    power = lam = 1
    saved: tuple[int, int, int] | None = None
    # Events, not commands: only.
    # run of any length is one step.
    # command cap here: the answer.
    # never a fuel-limit inference.
    # tape prefix, so one of those.
    while True:
        if ip >= size:
            # End of the program: halt.
            if pos < 0:
                return "0"
            ip = 0
        elif code[ip] == "3":
            if pos < 0:
                ip += 1  # below location 0 a 3 is a NOP.
                continue
            if not tape >> (pos + _RING) & 1:
                ip = fwd[ip]  # FALSE skips forward; ip still.
                continue
            ip = back[ip]
        else:
            r = run_at[ip]
            if r < 0:  # unrecognized characters are.
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


# : Simulated commands a.
# : Counted work, not wall.
# : raises identically on every.
# :.
# : The counter is charged for.
# : read by a planning decision.
# : so charging cannot change.
# : a diverging build is cut.
# : so the budget is a.
# : at an unprobed arity, not a.
# : scales it with the row.
_WORK_BUDGET = 2_000_000_000


def construct(truth_table: str) -> str:
    r"""Build a 123 template for ``truth_table`` at any arity."""
    n = max(1, (len(truth_table) - 1).bit_length())
    # The mark geometry comes from.
    # when its per-arity reference.
    # the doubling base with.
    # arity -- otherwise.
    # caches, so it is charged once.
    # .
    # The budget still bounds a.
    # wider table is exponentially.
    # shield paints -- so the cap.
    # divergence guard, not an.
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
