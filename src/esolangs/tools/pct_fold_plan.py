"""Plan a %^2^-1 relocation fold: the moves, not the characters.

The fold's search half.  A state is the rows' accumulator positions, a move
merges or wipes some of them, and a plan is the sequence that lands every row
on its answer.  :mod:`esolangs.tools.pct_fold` is what emits one.
"""

from bisect import bisect_left, bisect_right, insort
from collections.abc import Callable, Iterable, Iterator
from itertools import chain, pairwise

from esolangs.tools.pct_codes import (
    _LIMIT,
)

_FOLD_STEP = 4

#: The ladder spacing tried when :data:`_FOLD_STEP` finds no plan.
#:
#: **What bounded the fold was the ladder's footprint, not the search.**  The
#: rows start at ``-step * r``, so the ladder spans ``step * (2**n - 1)``, and
#: the emitter has to lay it inside ``[-_LIMIT, 0]`` from a zero accumulator.
#: At the wide spacing that is 4092 against 3003 at ten inputs -- over the
#: workspace, so no such table could ever be emitted, however long the
#: planner searched.  (Before :func:`_fold_at` gated on the right bound, that
#: is exactly what happened: the descent wandered a relative-geometry space
#: the emitter would refuse, dead-ending 354 moves in with 420 of 514 points
#: unmerged.)  Halving the spacing halves the footprint to 2046, which fits,
#: and ten inputs then build and print every row on the interpreter.
#:
#: Two was the floor while a setter subtracted its weight itself: ``s``
#: subtracts 2 and ``i`` subtracts 3, so :func:`_sub_code` spells every
#: amount except 1.  Laid by the one pair under a ``psp``, a run leaves
#: exactly ``-bit`` behind, so the all-row fold now goes on to a step of 1
#: after this one -- ``2**n - 1 <= 3003``, eleven inputs -- and the packed
#: ladder below is left to the staged route's prefix, whose setters still
#: subtract their weights.
#:
#: It is a *fallback* rather than the default because every shipped program
#: is built on the wider ladder: at four inputs and below the narrow ladder
#: plans the same tables but emits different characters, so trying it only
#: on a miss keeps every template that builds today byte-identical and
#: confines the change to the arities that refused.
_FOLD_NARROW_STEP = 2

#: The packed ladder: ``(2, 3, 4, 8, 16, ..., 2**(n-2) * 2)``.
#:
#: **A uniform ladder wastes half the workspace.**  The fold needs the rows
#: to sit at ``2**n`` *distinct* positions -- two rows sharing a value are
#: merged by the first cut reaching them and can never be separated again --
#: but a uniform ladder buys that distinctness by spending ``step * (2**n -
#: 1)``, which is far more than distinctness costs.  What it actually costs
#: is a set of weights whose ``2**n`` subset sums are distinct, and the
#: cheapest such set spans about ``2**n`` rather than ``2 * 2**n``.
#:
#: The floor is easy to state.  The sums are ``2**n`` distinct non-negative
#: integers, so the largest is at least ``2**n - 1``; the minimum weight is 2
#: (``2a + 3b`` cannot spell 1), so no subset sums to 1, and by symmetry none
#: sums to ``S - 1``.  Two values inside ``[0, S]`` are therefore unattainable
#: and ``S >= 2**n + 1``.  The set above **meets that floor exactly**: 2 and 3
#: cover the small residues that a pure doubling ladder cannot reach without
#: a weight of 1, and the powers above them behave like a binary code, so all
#: ``2**n`` sums are distinct with a total of exactly ``2**n + 1``.
#:
#: That is what lifted the arity while every setter subtracted its own
#: weight: the narrow uniform ladder spends 4094 at eleven inputs against
#: the 3003 the workspace allows, this one **2049**.  The all-row fold now
#: lays its rows by one pair under a ``psp`` and reaches eleven on the unit
#: step (2047); this shape serves the staged route's eleven-input prefix,
#: whose setters still subtract.  Twelve needs 4097, which does not fit, so
#: this shape ends there -- and no ladder of any shape reaches thirteen,
#: since ``2**13 + 1`` exceeds even the two-sided ``6007`` positions a
#: ``p``-negated ladder could address.
#:
#: **Row order stops matching position order here**, which is the one thing
#: the rest of the fold had assumed.  On a uniform ladder row ``r`` sits at
#: ``-step * r``, so consecutive rows are adjacent points and a table's runs
#: are contiguous; with these weights row 1 (weight 1024) sits *below* row 8
#: (weight 16).  :func:`_fold_at` therefore groups runs over rows sorted by
#: position rather than over ``range(2**n)``.  Everything downstream -- the
#: plan search, the moves, the emitter -- already worked in positions and
#: needed no change.
#: The value is the ladder's irregular *head*, the two weights that are not
#: powers; :func:`_fold_subset_weights` appends the doubling tail to it.
#: They are what meets the floor -- a pure doubling ladder from 2 spans
#: ``2 * (2**n - 1)``, and it is 2 and 3 together that cover the small sums a
#: weight of 1 would otherwise be needed for.
_FOLD_SUBSET_LADDER = (2, 3)

#: ``(top, span, cls, rows)``: highest row value relative to the state's
#: top, extent below it (0 once wiped), class, rows.
_FoldPoint = tuple[int, int, str, frozenset[int]]
_FoldState = tuple[_FoldPoint, ...]

#: ``(kind, k, c, victims)``: ``"m"`` doubles, ``"d"``/``"u"`` wipe the
#: bottom/top ``k`` groups with relocation ``c``.
_FoldOp = tuple[str, int, int, frozenset[int]]

#: Largest bridge state :func:`_fold_to_cofactors` searches.  Measured: the
#: 33628 building tables at n <= 4 never exceed 8 points, adversaries at
#: n = 8, 10, 12 top out at 4, and a 512-point state once burned 192s.
_COFACTOR_BRIDGE_POINTS = 8

#: A point in the emitter's mirror: a raw row or a merged set of rows.
_FoldKey = int | frozenset[int]


def _fold_norm(items: list[_FoldPoint]) -> _FoldState:
    """Sort by top descending and rebase so the highest top is 0."""
    ordered = sorted(items, key=lambda t: (-t[0], t[1]))
    top = ordered[0][0]
    return tuple((p - top, s, c, i) for p, s, c, i in ordered)


def _fold_merge(items: list[_FoldPoint]) -> _FoldState | None:
    """Coalesce equal positions, or ``None`` on a cross-class collision.

    Legal only within a class and between wiped points.
    """
    by_pos: dict[int, list[tuple[int, str, frozenset[int]]]] = {}
    for p, s, c, i in items:
        by_pos.setdefault(p, []).append((s, c, i))
    out: list[_FoldPoint] = []
    for p, grp in by_pos.items():
        if len(grp) == 1:
            s, c, i = grp[0]
            out.append((p, s, c, i))
        else:
            if len({c for _, c, _ in grp}) != 1:
                return None
            if any(s != 0 for s, _, _ in grp):
                return None
            out.append((p, 0, grp[0][1], frozenset(x for _, _, i in grp for x in i)))
    return _fold_norm(out)


def _fold_moves(
    state: _FoldState, kcap: int | None = None
) -> Iterator[tuple[str, int, int, frozenset[int], _FoldState]]:
    """Yield every candidate move from ``state``.

    A wipe relocates its victims by ``3004 + slack``, so a dive of the bottom
    ``k`` maps each survivor to ``q_i - c`` for ``c`` in ``[3004, 3003 + q_1]``
    (the gap to the nearest survivor's bottom); rises mirror.  Doubling is
    what lets a gap outgrow 3004, without which a landing can never split two
    survivors (an exhaustive wipe-only search confirms four-alternation
    tables are out of reach).
    """
    m = len(state)
    kmax = m if (kcap is None or m <= 8) else min(m, kcap)
    top_all = max(p for p, _, _, _ in state)
    bot_all = min(p - s for p, s, _, _ in state)
    spread = top_all - bot_all
    # State must fit in [-3003, 3003] after doubling; odd 3003 has no
    # integer placement, hence -2.
    if 0 < spread * 2 <= 2 * _LIMIT - 2:
        yield (
            "m",
            0,
            0,
            frozenset(),
            _fold_norm([(p * 2, s * 2, c, i) for p, s, c, i in state]),
        )
    if len({c for _, _, c, _ in state}) == 1 and any(s or p for p, s, _, _ in state):
        allids = frozenset(x for _, _, _, i in state for x in i)
        yield ("d", m, _LIMIT + 1, allids, ((0, 0, state[0][2], allids),))
    asc = sorted(state, key=lambda t: t[0])
    for k in range(1, min(m, kmax + 1) if m > 8 else m):
        vic = asc[:k]
        if len({c for _, _, c, _ in vic}) != 1:
            continue
        vcls = vic[0][2]
        vt = vic[-1][0]
        surv = asc[k:]
        q1 = min(p - s for p, s, _, _ in surv) - vt
        if q1 < 1:
            continue
        cmin, cmax = _LIMIT + 1, _LIMIT + q1
        cands = {cmin, cmax}
        qtops = [(p - vt, s, c) for p, s, c, _ in surv]
        for qt, qspan, qcls in qtops:
            if qspan == 0 and qcls == vcls and cmin <= qt <= cmax:
                cands.add(qt)
            for adj in (qt - 4, qt - 2, qt + 2, qt + 4):
                if cmin <= adj <= cmax:
                    cands.add(adj)
        for (qa, _, _), (qb, _, _) in pairwise(qtops):
            mid = (qa + qb) // 2
            if cmin <= mid <= cmax:
                cands.add(mid)
        for amount in cands:
            items = [(p - vt - amount, s, cc, ii) for p, s, cc, ii in surv]
            items.append((0, 0, vcls, frozenset(x for _, _, _, i in vic for x in i)))
            hi = max(p for p, _, _, _ in items)
            lo = min(p - s for p, s, _, _ in items)
            if hi - lo > 2 * _LIMIT:
                continue
            merged = _fold_merge(items)
            if merged is not None:
                yield (
                    "d",
                    k,
                    amount,
                    frozenset(x for _, _, _, i in vic for x in i),
                    merged,
                )
    desc = sorted(state, key=lambda t: -t[0])
    for k in range(1, min(m, kmax + 1) if m > 8 else m):
        vic = desc[:k]
        if len({c for _, _, c, _ in vic}) != 1:
            continue
        vcls = vic[0][2]
        vb = min(p - s for p, s, _, _ in vic)
        surv = desc[k:]
        q1 = vb - max(p for p, _, _, _ in surv)
        if q1 < 1:
            continue
        cmin, cmax = _LIMIT + 1, _LIMIT + q1
        cands = {cmin, cmax}
        qtops = [(vb - p, s, c) for p, s, c, _ in surv]
        for qt, qspan, qcls in qtops:
            if qspan == 0 and qcls == vcls and cmin <= qt <= cmax:
                cands.add(qt)
            for adj in (qt - 4, qt - 2, qt + 2, qt + 4):
                if cmin <= adj <= cmax:
                    cands.add(adj)
        for (qa, _, _), (qb, _, _) in pairwise(qtops):
            mid = (qa + qb) // 2
            if cmin <= mid <= cmax:
                cands.add(mid)
        for amount in cands:
            items = [(amount - (vb - p), s, cc, ii) for p, s, cc, ii in surv]
            items.append((0, 0, vcls, frozenset(x for _, _, _, i in vic for x in i)))
            hi = max(p for p, _, _, _ in items)
            lo = min(p - s for p, s, _, _ in items)
            if hi - lo > 2 * _LIMIT:
                continue
            merged = _fold_merge(items)
            # The span check is the merge's precondition; passing it merges.
            if merged is not None:  # pragma: no branch
                yield (
                    "u",
                    k,
                    amount,
                    frozenset(x for _, _, _, i in vic for x in i),
                    merged,
                )


def _fold_done(state: _FoldState) -> bool:
    """Two wiped points at most: one value per class, nothing unmerged."""
    return len(state) <= 2 and all(t[1] == 0 for t in state)


def _cofactor_done(state: _FoldState) -> bool:
    """Whether one wiped point remains for every live suffix cofactor."""
    return all(span == 0 for _, span, _, _ in state) and len(
        {cls for _, _, cls, _ in state}
    ) == len(state)


class _FoldLedger:
    """The plan state kept sorted, so a step costs its victims, not the state.

    Rebuilding the tuple state per step made the dense build quadratic
    (x4.2 per input, 1360 steps over 530 points at ten inputs).  Points live
    in absolute position as a sorted list of tops with dicts keyed by top; a
    wipe removes ``k`` victims from one end and inserts one landing, and only
    the doubling touches every point.  Row ids are chunks flattened only
    when a point becomes a victim.  ``to_state``/``from_state`` bridge to the
    tuple form the tests use.
    """

    __slots__ = (
        "bots",
        "bounds",
        "by_cls",
        "cls",
        "count",
        "ids",
        "nspan",
        "span",
        "tops",
    )

    def __init__(self) -> None:
        self.tops: list[int] = []
        self.bots: list[int] = []
        self.span: dict[int, int] = {}
        self.cls: dict[int, str] = {}
        self.ids: dict[int, list[frozenset[int]]] = {}
        #: Class -> sorted tops of its wiped (span 0) points: case 2's target.
        self.by_cls: dict[str, list[int]] = {}
        self.count: dict[str, int] = {}
        self.nspan = 0
        #: Adjacent pairs in top order whose classes differ: the run count
        #: less one, kept incrementally so the threshold test is O(1).
        self.bounds = 0

    @classmethod
    def from_state(cls, state: "Iterable[_FoldPoint]") -> "_FoldLedger":
        self = cls()
        for top, span, c, ids in state:
            self._insert(top, span, c, [ids])
        return self

    def to_state(self) -> _FoldState:
        """Return the tuple form: top descending, rebased so the highest is 0."""
        base = self.tops[-1]
        return tuple(
            (t - base, self.span[t], self.cls[t], frozenset().union(*self.ids[t]))
            for t in reversed(self.tops)
        )

    @property
    def size(self) -> int:
        return len(self.tops)

    def _insert(self, top: int, span: int, c: str, ids: list[frozenset[int]]) -> None:
        # Tops are distinct: a landing on a survivor merges.
        if top in self.span:
            raise AssertionError(top)
        at = bisect_left(self.tops, top)
        below = self.tops[at - 1] if at else None
        above = self.tops[at] if at < len(self.tops) else None
        if below is not None and above is not None:
            self.bounds -= self.cls[below] != self.cls[above]
        if below is not None:
            self.bounds += self.cls[below] != c
        if above is not None:
            self.bounds += self.cls[above] != c
        self.tops.insert(at, top)
        insort(self.bots, top - span)
        self.span[top] = span
        self.cls[top] = c
        self.ids[top] = ids
        self.count[c] = self.count.get(c, 0) + 1
        if span:
            self.nspan += 1
        else:
            insort(self.by_cls.setdefault(c, []), top)

    def _remove(self, top: int) -> None:
        span = self.span.pop(top)
        c = self.cls.pop(top)
        del self.ids[top]
        at = bisect_left(self.tops, top)
        below = self.tops[at - 1] if at else None
        above = self.tops[at + 1] if at + 1 < len(self.tops) else None
        if below is not None:
            self.bounds -= self.cls[below] != c
        if above is not None:
            self.bounds -= self.cls[above] != c
        if below is not None and above is not None:
            self.bounds += self.cls[below] != self.cls[above]
        del self.tops[at]
        del self.bots[bisect_left(self.bots, top - span)]
        if self.count[c] == 1:
            del self.count[c]
        else:
            self.count[c] -= 1
        if span:
            self.nspan -= 1
        else:
            lst = self.by_cls[c]
            del lst[bisect_left(lst, top)]

    def is_done(self) -> bool:
        """Two wiped points at most: one value per class, nothing unmerged."""
        return len(self.tops) <= 2 and self.nspan == 0

    def is_threshold(self) -> bool:
        """At most two runs of wiped points: one class wholly below the other.

        What the emitter's endgame prints from; extents must be gone since two
        spanned runs can interleave.
        """
        return self.nspan == 0 and self.bounds <= 1

    def is_cofactor_done(self) -> bool:
        """One wiped point per live class."""
        return self.nspan == 0 and len(self.count) == len(self.tops)

    def spread(self) -> int:
        return self.tops[-1] - self.bots[0]

    def can_double(self) -> bool:
        # As in ``_fold_double``: fit in [-3003, 3003], odd -> -2.
        return 0 < self.spread() * 2 <= 2 * _LIMIT - 2

    def _victims(self, kind: str, k: int) -> list[int]:
        return self.tops[:k] if kind == "d" else self.tops[-k:]

    def wipe_frame(self, kind: str, k: int) -> tuple[int, int, int] | None:
        """Return ``(q1, ref, survivors' lowest bottom)`` or ``None``.

        ``ref`` is the victims' reference edge and ``q1`` the gap to the nearest
        survivor's *bottom*; one whose extent reaches past the victims leaves no window.
        """
        m = len(self.tops)
        if k >= m or k < 1:
            return None
        vic = self._victims(kind, k)
        vcls = self.cls[vic[0]]
        if any(self.cls[t] != vcls for t in vic):
            return None
        # Survivors' lowest bottom, O(k): stop at the first value no victim owns.
        skip: dict[int, int] = {}
        for t in vic:
            b = t - self.span[t]
            skip[b] = skip.get(b, 0) + 1
        i = 0
        while skip.get(self.bots[i], 0):
            skip[self.bots[i]] -= 1
            i += 1
        minbot = self.bots[i]
        if kind == "d":
            ref = vic[-1]
            q1 = minbot - ref
        else:
            ref = min(t - self.span[t] for t in vic)
            q1 = ref - self.tops[-k - 1]
        if q1 < 1:
            return None
        return q1, ref, minbot

    def clean_amount(self, kind: str, k: int) -> int | None:
        """Smallest window amount whose landing coincides with no survivor.

        Computed by walking the survivor tops from the window's edge to the
        first gap; no victim can sit in the window.
        """
        frame = self.wipe_frame(kind, k)
        if frame is None:
            return None
        q1, ref, _minbot = frame
        amount = _LIMIT + 1
        tops = self.tops
        if kind == "d":
            i = bisect_left(tops, ref + amount)
            while i < len(tops) and tops[i] == ref + amount:
                amount += 1
                i += 1
        else:
            i = bisect_right(tops, ref - amount) - 1
            while i >= 0 and tops[i] == ref - amount:
                amount += 1
                i -= 1
        # Cannot exhaust: filling ``q1`` slots needs ``q1`` distinct survivor
        # tops, but ``q1`` is the gap to the nearest one.  47.2M legal wipe
        # frames, none ran out.  The return keeps the function total.
        if amount > _LIMIT + q1:
            return None  # pragma: no cover
        return amount

    def op(self, kind: str, k: int, amount: int) -> _FoldOp:
        """Name a wipe, flattening its victims' row chunks into the op."""
        vic = self._victims(kind, k)
        return (
            kind,
            k,
            amount,
            frozenset().union(*chain.from_iterable(self.ids[t] for t in vic)),
        )

    def rule_move(self) -> _FoldOp | None:
        """Name the one move the closed-form rules choose from this state.

        A fixed case analysis: (1) one class left, the everything-wipe;
        (2) an end group whose window holds a same-class wiped point, wipe onto
        the nearest (the conveyor); (3) a same-class run at an end, wipe it
        together; (4) spread at most 3002, double; (5) hop an end group by the
        first collision-free amount.  Dive side first, nearest target on ties --
        conventions the r <= 5 mining found confluent.
        """
        tops = self.tops
        m = len(tops)
        if len(self.count) == 1:
            return self.op("d", m, _LIMIT + 1)
        for kind in ("d", "u"):
            frame = self.wipe_frame(kind, 1)
            if frame is None:
                continue
            q1, ref, _minbot = frame
            vcls = self.cls[tops[0] if kind == "d" else tops[-1]]
            lst = self.by_cls.get(vcls, ())
            # Nearest same-class wiped point; the victim is at distance 0,
            # outside every window.
            if kind == "d":
                i = bisect_left(lst, ref + _LIMIT + 1)
                if i < len(lst) and lst[i] <= ref + _LIMIT + q1:
                    return self.op(kind, 1, lst[i] - ref)
            else:
                i = bisect_right(lst, ref - _LIMIT - 1) - 1
                if i >= 0 and lst[i] >= ref - _LIMIT - q1:
                    return self.op(kind, 1, ref - lst[i])
        k = 1
        while k < m and self.cls[tops[-1 - k]] == self.cls[tops[-1]]:
            k += 1
        if 1 < k < m:
            amount = self.clean_amount("u", k)
            # ``1 < k < m`` is the clean amount's own precondition.
            if amount is not None:  # pragma: no branch
                return self.op("u", k, amount)
        k = 1
        while k < m and self.cls[tops[k]] == self.cls[tops[0]]:
            k += 1
        if 1 < k < m:
            amount = self.clean_amount("d", k)
            # ``1 < k < m`` is the clean amount's own precondition.
            if amount is not None:  # pragma: no branch
                return self.op("d", k, amount)
        if self.can_double():
            return ("m", 0, 0, frozenset())
        for kind in ("d", "u"):
            amount = self.clean_amount(kind, 1)
            if amount is not None:
                return self.op(kind, 1, amount)
        return None

    def double(self) -> None:
        self.tops = [t * 2 for t in self.tops]
        self.bots = [b * 2 for b in self.bots]
        self.span = {t * 2: s * 2 for t, s in self.span.items()}
        self.cls = {t * 2: c for t, c in self.cls.items()}
        self.ids = {t * 2: i for t, i in self.ids.items()}
        self.by_cls = {c: [t * 2 for t in lst] for c, lst in self.by_cls.items()}

    def step(self, op: _FoldOp) -> bool:
        """Apply one concrete op, or ``False`` where the move algebra refuses it.

        The landing is inserted at ``ref +- amount``; the emitter mirrors every
        row and asserts at each step, so wrong arithmetic cannot emit.
        """
        kind, k, amount, _vids = op
        tops = self.tops
        if kind == "m":
            if not self.can_double():
                return False
            self.double()
            return True
        if k == len(tops):
            # The everything-wipe: legal only once a single class remains.
            if len(self.count) != 1:
                return False
            c = self.cls[tops[0]]
            ids = list(chain.from_iterable(self.ids[t] for t in tops))
            for t in list(tops):
                self._remove(t)
            self._insert(0, 0, c, ids)
            return True
        frame = self.wipe_frame(kind, k)
        if frame is None:
            return False
        q1, ref, minbot = frame
        if not _LIMIT + 1 <= amount <= _LIMIT + q1:
            return False
        vic = self._victims(kind, k)
        if kind == "d":
            landing = ref + amount
            hi = max(tops[-1], landing)
        else:
            landing = ref - amount
            hi = max(tops[-k - 1], landing)
        lo = min(minbot, landing)
        if hi - lo > 2 * _LIMIT:
            return False
        # A collision is a merge: same class only, onto a wiped point only
        # (a group with extent has rows at several values).
        c = self.cls[vic[0]]
        if landing in self.span and (self.cls[landing] != c or self.span[landing]):
            return False
        ids = list(chain.from_iterable(self.ids[t] for t in vic))
        for t in vic:
            self._remove(t)
        if landing in self.span:
            self.ids[landing].extend(ids)
        else:
            self._insert(landing, 0, c, ids)
        return True


def _fold_reduce(
    state: _FoldState,
    done: "Callable[[_FoldState], bool]",
    budget: int | None = None,
) -> list[_FoldOp] | None:
    """Run the rules to a ``done`` state, or ``None`` where they dead-end.

    Spanned groups are wiped first at the first collision-free amount.
    ``budget`` defaults to :data:`_FOLD_STEP_SLOPE`'s guard, never reached
    by the corpus.
    """
    ledger = _FoldLedger.from_state(state)
    if done is _fold_done:
        finished: Callable[[], bool] = ledger.is_threshold
    elif done is _cofactor_done:
        finished = ledger.is_cofactor_done
    else:  # pragma: no cover - no shipped caller
        finished = lambda: done(ledger.to_state())  # noqa: E731
    ops: list[_FoldOp] = []
    guard = 0
    while ledger.nspan and ledger.size > 1:
        guard += 1
        if guard > 2 * len(state) + 4:  # pragma: no cover - linear in groups
            break
        amount = ledger.clean_amount("d", 1)
        if amount is None:
            break
        wipe = ledger.op("d", 1, amount)
        if not ledger.step(wipe):  # pragma: no cover - a clean amount always applies
            break
        ops.append(wipe)
    if budget is None:
        budget = _FOLD_STEP_SLOPE * ledger.size + _FOLD_STEP_SLACK
    for _ in range(budget):
        if finished():
            return ops
        op = ledger.rule_move()
        if op is None:
            return None
        if not ledger.step(op):
            return None
        ops.append(op)
    return ops if finished() else None


#: Step budget ``slope * points + slack``; points open at one per run.
#: It is what guarantees a return: counts never rise and workspace-guarded
#: states are finite, but :func:`_fold_reduce` carries no ``seen`` set, so a
#: (never observed) cycle would loop without it.  It decides how long a
#: doomed descent runs, never what builds; the fold is the last route.
#:
#: Calibration (retired descent, exhaustive at four inputs): worst 78 steps
#: at 16 points vs 144 allowed (1.8x).  Worst pts->steps ratio peaks at 5.25
#: near 12 points; sampling wider gave 5.65 (five inputs, 17 points) and
#: rose with every widening, so the slope is chosen, not derived.  The rules
#: sit lower: worst 4.77 at 13 points, including the 997-group 11-input state.
#: Replacing the flat 400: byte-identical over 387 tables at n=3..8; at n=9
#: (359 steps used at 8) the flat budget built 1 of 3, this builds 3 of 3.
#:
#: Greedy cost is a function of the run-length word alone (127/127 words at
#: n=3, 32767/32767 at n=4, complement-invariant), as a *sequence*: only
#: 27 of 2248 rotation/reflection classes are cost-invariant, and sliding one
#: length-2 run through an alternating word moves cost 27 -> 78.
#:
#: Greedy path length is not a distance: vs BFS it is optimal on 4 of 196
#: three-input words (14 where 6 suffice).  The BFS cost has a closed form,
#: ``r`` = run count, a slot *long* when its run exceeds 1::
#:
#:     cost(word) = 2 * r - 3 - (r % 2) + [every middle slot is long]
#:
#: middle slots ``{(r - 1) // 2, r // 2}``; ``base(r)`` = 1, 2, 5, 6, 9, 10, 13
#: at r = 2..8.  Distance is from :func:`_fold`'s start state (65534/65534
#: signatures match the word-built one) over ``(top, span, class)`` with a
#: global visited set and :func:`_fold_moves` at ``kcap=None`` (binds only at
#: r >= 9, untested).  Measured over 1091 words, zero mismatches: exhaustive
#: r <= 6 at n=3 (119) plus two r == 7; exhaustive ``>1``-patterns r <= 5 at
#: n=4,5 (322, 468); 300 random at n=5,6; adversarial middle-slot pairs.
#: Delta pins: r=6 ``(1,1,2,1,1,10)`` and ``(1,1,1,2,1,10)`` cost 9, ``(1,1,2,2,1,9)``
#: costs 10; r=7 ``(1,1,1,2,1,1,25)`` costs 11 (depths 9-10 exhaust, 393s),
#: base(7)=10 proved by BFS on ``(2,1,1,1,1,1,1)`` / ``(1,1,1,1,1,1,2)`` (1.17M
#: states, 344s/195s) and IDDFS on ``(1,1,1,1,1,1,26)``.
#: Mechanism: only a wipe zeroes a span, wipes take ``asc[:k]``/``desc[:k]``
#: (8116/8116 contiguous), so a long middle run costs the extra move
#: (necessary on all 1005 reachable 3-point states; 462 one-move finishes as
#: control).  A ``k >= 2`` wipe does NOT need span-0 victims (414 of 840
#: have a spanned one); the span-0 requirement is in the landing.
#: base(r) = ``r - 1 + 2 * floor((r - 2) / 2)`` with ``floor((r - 2) / 2)``
#: doublings is a census, not a bound.  Unmeasured: ``>1``-pattern
#: sufficiency beyond r <= 5 (n=4,5) / r <= 6 (n=3); r >= 8 everywhere
#: (base(8)=13 is a prediction; BFS at r=7 is ~6 min, 1.2M states).
#:
#: Corrected records: ``(19,2,11)``/``(23,2,7)`` both cost 3, ``(34,20,10)``/
#: ``(10,20,34)`` both 3, ``(40,4,8,12)``/``(12,4,8,40)`` both 6 -- the old
#: "counterexamples" were greedy artifacts; ``(1,14,1)`` costs 3 vs
#: ``(1,1,14)`` 2 as the rule says; base(2)=1 at every arity.  ``3 * points``
#: fits n=3 exactly but fails at n=4 (10 points) and n=5.  Widening ``kcap``
#: 3 -> 6 is byte-identical (median 1.92, worst 5.10); the harness that
#: suggested otherwise started from 2**n points, not the run count.
#:
#: Plan length is not program length: a dive at 3004 costs 1490 chars from
#: rest and 4 when near, a doubling 751, the finish > 1000 (:func:`_sub_code`
#: is ``k // 2`` chars).  17 -> 6 ops saved 13%; optimising chars saves 60%+.
#: The char cost model is closed form (zero error on all 56 n=3 tables):
#: :meth:`_FoldEmitter.finish` solves ``need = (-(byte(hi) - byte(lo)) -
#: pos[lo]) % 256``, cost ``u // 2 + 31``.  Not complement-invariant: bytes
#: 48/49 shift the congruence by 2 (~127 chars); ``01100111`` 5424 vs 5306.
#:
#: Unshipped but verified: every three-run table builds from three greedy
#: rises, 3176-3185 chars vs 9838-10640 here, within 1-8 of optimum.
#: Failed generalisations (do not retry): reranking by chars looked -27.7%
#: and is +272% on tables all variants build (116/254 vs 206/254 coverage);
#: a greedy catalogue of optimal shapes saturates at 34 of 40; greedy on the
#: exact cost model builds 8 of 40 at -67%.  Needs a cost-to-go term.
_FOLD_STEP_SLOPE = 8
_FOLD_STEP_SLACK = 16


def _fold_served(r: int, delta: int, pat1: int) -> bool:
    """Whether the three-phase construction serves this run-length word.

    ``r`` runs and ``(delta, pat[1])``; a rejected word (every ``r >= 6``)
    falls to the rule construction.  The second clause is an identity, not
    a budget: for ``r`` of 2, 3, 4 the middle index set contains 1, so
    ``delta`` implies ``pat[1]`` and ``(r, 1, 0)`` is unbuildable; at
    ``r == 3`` the implication runs both ways.  Replaced a twelve-entry
    table; enumerating to ``r == 12`` reproduces it
    (``test_fold_served_is_reachability``).
    """
    if not 2 <= r <= 5:
        return False
    if r == 5:
        return True
    if delta and not pat1:
        return False
    return not (r == 3 and pat1 and not delta)


def _fold_skeleton(r: int, delta: int, pat1: int) -> tuple[tuple[str, int, str], ...]:
    """Plan the reduction of an ``r``-run word: peel, park, close.

    Peel the ends inward with alternating ``d1``/``u2`` at ``cmax``, park
    with one wipe at ``cmin`` then double, close with a landing then ``cmax``
    wipes to ``k == 2``; ``delta`` adds one peel.  Below four runs the plan
    is the peel alone.
    """
    if r == 2:
        opening: list[tuple[str, int, str]] = [("d" if pat1 else "u", 1, "cmax")]
        return tuple(opening + [("d", 1, "cmax")] * delta)
    if r == 3:
        if delta:
            return (("d", 1, "cmax"), ("d", 1, "cmax"), ("d", 2, "cmax"))
        return (("d", 1, "cmax"), ("u", 2, "cmax"))
    # One peel per run past the four park and close consume, plus delta.
    peels = r - 4 + delta
    peel = [("d", 1, "cmax") if i % 2 == 0 else ("u", 2, "cmax") for i in range(peels)]
    park: tuple[str, int, str]
    close: list[tuple[str, int, str]]
    if r == 5 and delta:
        park = ("u", 1, "cmin")
        close = [("u", 1, "cmax"), ("u", 1, "land2"), ("u", 2, "cmax")]
    elif r == 5:
        park = ("u", 2, "cmin")
        close = [("d", 1, "land1"), ("d", 1, "cmax"), ("u", 2, "cmax")]
    elif delta:
        park = ("d", 1, "cmin")
        close = [("d", 1, "cmax"), ("d", 1, "land2"), ("d", 2, "cmax")]
    elif pat1:
        park = ("u", 1, "cmin")
        close = [("d", 1, "land1"), ("d", 1, "cmax"), ("u", 2, "cmax")]
    else:
        park = ("d", 1, "cmin")
        close = [("d", 1, "cmax"), ("u", 1, "land2"), ("u", 2, "cmax")]
    return (*peel, park, ("m", 0, "m"), *close)


def _fold_geometry(
    state: _FoldState, kind: str, k: int
) -> tuple[int, int, list[tuple[int, int, str]], str] | None:
    """Return ``(cmin, cmax, survivor tops, victim class)`` for a wipe."""
    if kind == "d":
        asc = sorted(state, key=lambda t: t[0])
        vic, surv = asc[:k], asc[k:]
        if not surv:
            return None
        vt = vic[-1][0]
        q1 = min(p - s for p, s, _, _ in surv) - vt
        tops = [(p - vt, s, c) for p, s, c, _ in surv]
    else:
        desc = sorted(state, key=lambda t: -t[0])
        vic, surv = desc[:k], desc[k:]
        if not surv:
            return None
        vb = min(p - s for p, s, _, _ in vic)
        q1 = vb - max(p for p, _, _, _ in surv)
        tops = [(vb - p, s, c) for p, s, c, _ in surv]
    return _LIMIT + 1, _LIMIT + q1, tops, vic[0][2]


def _fold_resolve(
    state: _FoldState, kind: str, k: int, sym: str
) -> tuple[_FoldOp, _FoldState] | None:
    """Turn one symbolic step into a concrete move on ``state``.

    A landing is matched first by survivor index; ``cmax`` and ``cmin`` fall back.
    """
    want: int | None = None
    if sym != "m":
        geo = _fold_geometry(state, kind, k)
        if geo is None:
            return None
        cmin, cmax, tops, vcls = geo
        if sym.startswith("land"):
            j = int(sym[4:])
            if j >= len(tops):
                return None
            qt, qspan, qcls = tops[j]
            if qspan != 0 or qcls != vcls or not cmin <= qt <= cmax:
                return None
            want = qt
        else:
            want = cmax if sym == "cmax" else cmin
    for kk, k2, c, vids, nb in _fold_moves(state, kcap=None):
        if kk != kind or k2 != k:
            continue
        if sym == "m" or c == want:
            return (kk, k2, c, vids), nb
    return None


def _fold_construct(state: _FoldState) -> list[_FoldOp] | None:
    """Emit a plan from the state's run-length word, or ``None``.

    One geometry computation per op, read from :func:`_fold_skeleton`.
    """
    st = _fold_norm(list(state))
    if _fold_done(st):
        return []
    word = tuple(len(ids) for _p, _s, _c, ids in sorted(st, key=lambda t: -t[0]))
    pat = tuple(1 if x > 1 else 0 for x in word)
    r = len(pat)
    mids = {(r - 1) // 2, r // 2}
    delta = 1 if all(pat[i] for i in mids) else 0
    key = (r, delta, pat[1] if r > 1 else 0)
    if not _fold_served(*key):
        return None
    skel = _fold_skeleton(*key)
    ops: list[_FoldOp] = []
    for kind, k, sym in skel:
        got = _fold_resolve(st, kind, k, sym)
        if got is None:
            return None
        op, st = got
        ops.append(op)
    return ops if _fold_done(st) else None


def _fold_plan(state: _FoldState) -> list[_FoldOp] | None:
    """Plan a full reduction, or ``None`` where no rule applies.

    Words of at most five runs take the skeleton (byte-stable); the rest run
    :func:`_fold_rule_move` to two points.  The search and greedy descent are
    gone: over all 254 non-constant three-input tables, 200 four-input, 150
    five-input plus parity, majority and the alternator, the rules accept the
    same set, and every rules-built table re-executes at n = 3..6, 8, 10, 11
    and the twelve-input route.  A two-run state is a threshold state with
    an empty plan, which is why ``AND`` and majority are a few dozen characters.
    """
    if len(state) <= 2 and all(
        low[0] < high[0] - high[1] for high, low in pairwise(state)
    ):
        return []
    built = _fold_construct(state)
    if built is None:
        return _fold_reduce(state, _fold_done)
    # The skeleton plans to two points; the endgame needs only two runs,
    # so the plan is cut at the first threshold state it passes through.
    ledger = _FoldLedger.from_state(state)
    for index, op in enumerate(built):
        if ledger.is_threshold():
            return built[:index]
        if not ledger.step(op):  # pragma: no cover - the skeleton's own ops
            return built
    return built
