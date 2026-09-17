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

#: One point of a fold plan: ``(top, span, cls, rows)`` -- the group's highest
#: row value relative to the state's top, how far its rows extend below it
#: (0 once it has been wiped and its rows merged), its class, and the rows.
_FoldPoint = tuple[int, int, str, frozenset[int]]
_FoldState = tuple[_FoldPoint, ...]

#: One move: ``(kind, k, c, victims)`` -- ``"m"`` doubles, ``"d"``/``"u"``
#: wipe the bottom/top ``k`` groups with relocation amount ``c``.
_FoldOp = tuple[str, int, int, frozenset[int]]

#: The largest bridge state :func:`_fold_to_cofactors` will search.  Measured,
#: not chosen: exhaustively over ``n <= 4`` the 33628 tables that build never
#: hand the bridge more than eight points, and the adversaries built to grow
#: the state (a function of the first ``k`` inputs embedded at ``n = 8, 10,
#: 12``) top out at four.  Above this a doomed arity used to get expensive --
#: a 512-point state burned the retired best-first bridge's 50000-state cap
#: for 192s -- while contributing no build, so it is declined instead of
#: paid for.
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

    Two points at one value are indistinguishable forever after, so a
    collision is a merge -- legal only within a class, and only between
    already-wiped points (a group with extent has rows at *several* values,
    so an "equal top" is not an equal anything).
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

    The algebra is relative: a wipe relocates its victims by exactly
    ``3004 + slack`` (the reset line is at 3003 and a landing is at 0), so a
    dive of the bottom ``k`` groups maps each survivor ``q_i`` above the
    victims to ``q_i - c`` for any ``c`` in ``[3004, 3003 + q_1]`` -- the
    window is the gap to the nearest survivor's *bottom*, and every choice
    of absolute placement realises every ``c`` in it.  Rises mirror.  The
    doubling ``m`` scales every gap and is what lets a gap outgrow 3004,
    without which a landing can never split two survivors (each wipe caps
    the spread at 3003, so the cyclic order of the groups would be invariant
    and any table whose runs alternate four or more times would be out of
    reach -- an exhaustive search over wipe-only plans finds exactly that).
    """
    m = len(state)
    kmax = m if (kcap is None or m <= 8) else min(m, kcap)
    top_all = max(p for p, _, _, _ in state)
    bot_all = min(p - s for p, s, _, _ in state)
    spread = top_all - bot_all
    # Doubling needs the whole state inside [-3003, 3003] afterwards, and an
    # odd spread of 3003 has no integer placement, hence the -2.
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
            # The span check above is the merge's own precondition, so a
            # pair that passes it always merges.
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

    A :data:`_FoldState` is rebuilt, re-sorted and rebased on every step by
    the tuple functions below, which is what made the dense build quadratic
    (x4.2 per added input, 1360 steps over a 530-point state at ten inputs).
    Nothing a rule reads needs the whole state: the ends, the gap to the
    nearest survivor, the first free amount in a window, the nearest
    same-class wiped point.  So the points live here in *absolute* position
    -- rebasing is cosmetic, every rule is a difference -- as a sorted list
    of tops with dicts keyed by top, and a wipe removes its ``k`` victims
    from one end and inserts one landing.  Only the doubling touches every
    point, and a plan has a dozen of those.

    Row ids are *chunks*: a point's ``ids`` is a list of frozensets that a
    landing extends by one, and it is flattened only when the point becomes
    a victim and the op has to name its rows.  The conveyor merges hundreds
    of victims onto one point, so copying that point's rows per landing was
    the other quadratic term.

    ``to_state`` and ``from_state`` are the bridge to the tuple form the
    tests and the small-state skeleton use; the ops it emits are the same
    ``_FoldOp`` tuples, and :func:`_fold_step`, :func:`_fold_rule_move` and
    :func:`_fold_clean_amount` are now one-step views of this class.
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
        # Tops are distinct: the start state lays every run at its own
        # position and a landing that coincides with a survivor merges.
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

        What the emitter's endgame prints from, so a plan may stop here
        rather than merging each class onto one point; the extents are
        required gone because two spanned runs can interleave, which the
        boundary count alone cannot see.
        """
        return self.nspan == 0 and self.bounds <= 1

    def is_cofactor_done(self) -> bool:
        """One wiped point per live class."""
        return self.nspan == 0 and len(self.count) == len(self.tops)

    def spread(self) -> int:
        return self.tops[-1] - self.bots[0]

    def can_double(self) -> bool:
        # Doubling needs the whole state inside [-3003, 3003] afterwards,
        # and an odd spread of 3003 has no integer placement, hence the -2.
        return 0 < self.spread() * 2 <= 2 * _LIMIT - 2

    def _victims(self, kind: str, k: int) -> list[int]:
        return self.tops[:k] if kind == "d" else self.tops[-k:]

    def wipe_frame(self, kind: str, k: int) -> tuple[int, int, int] | None:
        """Return ``(q1, ref, survivors' lowest bottom)`` or ``None``.

        ``ref`` is the victims' reference edge -- their top for a dive,
        their lowest bottom for a rise -- and ``q1`` the gap from it to the
        nearest survivor, which is the relocation window's width.  A
        survivor's *bottom* counts: one whose extent reaches past the
        victims leaves no window at all.
        """
        m = len(self.tops)
        if k >= m or k < 1:
            return None
        vic = self._victims(kind, k)
        vcls = self.cls[vic[0]]
        if any(self.cls[t] != vcls for t in vic):
            return None
        # The survivors' lowest bottom: walk the bottom multiset past the
        # victims' own bottoms, which is O(k) since it stops at the first
        # value no victim owns.
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

        The window is a full interval, so the first free value in it is a
        computed amount, not a searched one: the survivor tops are walked
        upward (downward for a rise) from the window's edge and the walk
        stops at the first gap, which costs the occupied run, not the state.
        No victim can sit in the window -- a dive's victims are below its
        reference edge and a rise's above -- so the whole top list serves.
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
        # The window cannot be exhausted: it has ``q1`` slots and the
        # occupied set is the survivor tops, which are distinct positions,
        # so filling it needs ``q1`` survivors -- while ``q1`` is itself the
        # gap to the *nearest* survivor, and packing that many in collapses
        # it to 1.  Measured over 47.2M legal wipe frames (sizes 2-4, both
        # directions, every k, mixed spans and classes): no window ever ran
        # out.  The return stays as the total function's last arm.
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

        A fixed case analysis, not a ranking: each case either applies --
        and then fully determines its move -- or falls through to the next.

        1. One class left: the everything-wipe finishes.
        2. An end group whose landing window holds a same-class wiped point:
           wipe it onto the nearest such point, which is a merge.  This is
           the workhorse -- on a grown ladder it runs as a conveyor, merging
           one group per op until the windows empty.
        3. A same-class run of groups at an end: wipe them together at the
           first collision-free amount, which merges the run onto one point.
        4. Spread at most 3002: double.  Growth is what pushes same-class
           gaps past the 3003 line so case 2's windows fill; it is also the
           only reorder the language has (see :func:`_fold_moves`).
        5. Otherwise hop an end group by the first collision-free amount.
           On a state wider than 3004 the hop lands inside the pack,
           compressing the spread back under the doubling bound.

        Cases 2 and 5 try the dive side first; ties inside a case take the
        nearest target.  Both choices are conventions -- the r <= 5 mining
        recorded on :func:`_fold_skeleton` found rank ties to be confluent,
        and the acceptance sweeps re-measure that end to end.
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
            # The nearest same-class wiped point in the window, by bisect:
            # the victim itself is span 0 of that class but sits at distance
            # 0, outside every window.
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

        A wipe relocates its victims by ``amount`` and merges them onto one
        wiped point -- in absolute terms the survivors stay and the landing
        is inserted at ``ref + amount`` (dive) or ``ref - amount`` (rise) --
        the doubling scales everything, and the same span guard applies.
        Divergence from the interpreter is caught downstream either way:
        the emitter mirrors every row and asserts at each step, so a plan
        built on wrong arithmetic cannot emit.
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
        # Two points at one value are indistinguishable forever after, so a
        # collision is a merge -- legal only within a class, and only onto
        # an already-wiped point (a group with extent has rows at *several*
        # values, so an "equal top" is not an equal anything).
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


def _fold_step(state: _FoldState, op: _FoldOp) -> _FoldState | None:
    """Apply one concrete op to a tuple state, or ``None`` where it is refused."""
    ledger = _FoldLedger.from_state(state)
    return ledger.to_state() if ledger.step(op) else None


def _fold_clean_amount(state: _FoldState, kind: str, k: int) -> int | None:
    """:meth:`_FoldLedger.clean_amount` on a tuple state."""
    return _FoldLedger.from_state(state).clean_amount(kind, k)


def _fold_rule_move(state: _FoldState) -> _FoldOp | None:
    """:meth:`_FoldLedger.rule_move` on a tuple state."""
    return _FoldLedger.from_state(state).rule_move()


def _fold_reduce(
    state: _FoldState,
    done: "Callable[[_FoldState], bool]",
    budget: int | None = None,
) -> list[_FoldOp] | None:
    """Run the rules to a ``done`` state, or ``None`` where they dead-end.

    The extent pre-pass comes first, as it always has: a group with extent
    can be neither a landing target nor a merge, so every spanned group is
    wiped once -- at the first collision-free amount rather than a fixed
    ``cmin``, for the same reason as case 5 above.  ``budget`` defaults to
    the derived latency guard recorded on :data:`_FOLD_STEP_SLOPE`; the
    corpus never reaches it, and a rules dead-end returns ``None`` through
    the same refusal path the search used.

    The two shipped ``done`` predicates are read off the ledger's counters;
    any other callable is given the tuple state it expects, at the cost of
    materialising it per step.
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


#: The rule construction's step budget, as ``slope * points + slack``
#: rather than a flat number.  **The starting point count is the run
#: count** -- the fold opens with one point per run of the sorted table, so
#: a budget written against points is written against the table's own
#: structure.
#:
#: **The budget is what guarantees a return.**  Two of the retired
#: descent's termination facts still hold -- ``_fold_merge`` only ever
#: coalesces points, so the count never rises, and every move guards the
#: workspace, so the states at a fixed count are finitely many -- but the
#: third leg was its ``seen`` set, and :func:`_fold_reduce` carries none.
#: The rules are deterministic, so a revisited state would be a true cycle;
#: none was observed anywhere the construction was measured, but nothing
#: forbids one, and the budget converts that possibility into the same
#: ``None`` refusal every other dead end takes.
#:
#: So the slope only has to be generous enough not to cut a reduction short,
#: and its calibration predates the rules: on the retired descent's walks
#: **four inputs was enumerated rather than sampled**: folding all 65534
#: non-constant four-input tables gives a worst of 78 steps at 16 points,
#: against the 144 this budget allows there -- 1.8x headroom over an
#: exhaustive population, not a lucky sample.  The whole ``pts -> steps``
#: table is regular: the maximum climbs smoothly with the point count and
#: the worst ratio peaks at **5.25** around 12 points, then falls away.
#:
#: Sampling at wider arities agrees (worst 5.65 at five inputs, at 17
#: points) and, importantly, does *not* converge downward -- the worst
#: observed ratio rose with every widening, 4.25 through 5.65.  That is why
#: the slope is not presented as derived: it is a bound chosen to sit well
#: above an observed peak that small states, not large ones, produce.  The
#: rules sit further under it than the descent did -- their worst observed
#: ratio is 4.77, at 13 points, over the same corpora plus the 997-group
#: eleven-input state -- so the bound carries over unshrunk.  What makes
#: that acceptable is the termination argument above -- the budget does not
#: decide what builds, only how long a doomed descent runs -- plus the fold
#: being the last route tried, so a loose budget costs refusal latency and
#: nothing on a table that builds.
#:
#: **What the cost actually depends on is the run-length word**, and that is
#: exhaustive rather than sampled: writing each table as its sequence of run
#: lengths, every one of the 127 distinct words at three inputs and all
#: 32767 at four map to a *single* step count, with no exceptions.  Since
#: 65534 tables share those 32767 words in pairs -- a table and its
#: complement -- the cost is complement-invariant too, and nothing about the
#: table beyond the word matters.
#:
#: The dependence is on the word as a *sequence*, not as a multiset: only 27
#: of the 2248 rotation-and-reflection classes at four inputs are
#: cost-invariant.  Position is what moves it.  Holding the point count,
#: run count and class sizes fixed and sliding one length-2 run through an
#: otherwise alternating word takes the cost from 27 steps to 78 -- the same
#: table shape, three times the work, decided by where the defect sits.  The
#: worst tables in the whole four-input enumeration are exactly that: near
#: alternating with a single late defect.
#:
#: **All of the above is about the greedy descent's path length, which is
#: not an invariant of anything.**  It is one policy's walk, tie-broken by
#: the order :func:`_fold_moves` yields and carrying a ``seen`` set that
#: makes each step depend on the whole history, so it is not even a graph
#: distance.  Comparing it against one -- a breadth-first search over
#: signatures with a global visited set -- it is *optimal on 4 of 196*
#: three-input words, and can be 14 steps where 6 suffice.  Some words the
#: descent takes 9 steps on are 2 steps from done.
#:
#: Against the true distance the structure is completely different.  Within
#: a fixed run count the optimal cost takes exactly **two adjacent values**
#: (spread 1, against the greedy spread of 9), and it does *not* depend on
#: the exact run lengths at all -- only on which runs exceed 1, with zero
#: ambiguity at every run count.  So the incompressibility this docstring
#: used to record is a fact about the heuristic, not about the fold: the
#: exact lengths that "matter without limit" matter only to greedy's walk.
#:
#: **The optimal cost has a closed form.**  Writing ``r`` for the run count
#: and calling a slot *long* when its run exceeds 1::
#:
#:     cost(word) = 2 * r - 3 - (r % 2) + [every middle slot is long]
#:
#: where the *middle* slots are ``{(r - 1) // 2, r // 2}`` -- one slot for
#: odd ``r``, two for even.  The first three terms are ``base(r)``, the
#: minimum cost at that run count: 1, 2, 5, 6, 9, 10, 13 at ``r = 2..8``.
#: The bracket is the ``delta``, which is 0 or 1, so the two-adjacent-values
#: spread above is exactly this term.
#:
#: **Definitions, because the quantity is what the prior investigation got
#: wrong.**  ``cost`` is the breadth-first distance from the start state --
#: one point per run, at ``-_FOLD_STEP * first_row`` with span
#: ``_FOLD_STEP * (len - 1)`` -- to a :func:`_fold_done` state, over
#: ``(top, span, class)`` signatures with a *global* visited set, generating
#: successors with :func:`_fold_moves` at ``kcap=None``.  ``kcap`` does not
#: bind below nine points (``kmax = m if m <= 8``), so this is the shipped
#: move set for every word measured; at ``r >= 9`` the retired descent's
#: ``kcap=3`` was a different graph and is not covered by this rule.
#:
#: The harness's start state is the same object :func:`_fold` builds, and
#: that is checked rather than assumed: over all 65534 non-constant
#: four-input tables, the state constructed from the run-length word alone
#: has the identical signature to the one built from the table, 65534
#: of 65534.  Those tables carry only 32767 distinct words -- a table and its
#: complement share one -- which is where the cost's complement-invariance
#: comes from.
#:
#: Measured over **1091 words with zero mismatches**: exhaustive at three
#: inputs for ``r <= 6`` (all 119 words) plus two of the seven ``r == 7``
#: words, the ones with the defect at either end; exhaustive
#: over ``>1``-patterns at four and five inputs for ``r <= 5``, each pattern
#: carried by several words that vary *where* the mass sits (the axis that
#: killed the earlier candidates), 322 and 468 words; 300 uniformly random
#: words at five and six inputs; and an adversarial round on the shapes the
#: rule is most likely to get wrong -- pairs differing only at a middle slot,
#: extreme mass contrasts, the same pattern at 8, 16, 32 and 64 rows.
#:
#: The delta is pinned at the run counts where its shape changes.  At
#: ``r == 6`` the middle is a *pair* of slots and the conjunction is what
#: matters: at four inputs ``(1, 1, 2, 1, 1, 10)`` and ``(1, 1, 1, 2, 1, 10)``
#: each cost 9 with one middle slot long, while ``(1, 1, 2, 2, 1, 9)`` costs
#: 10 with both.  At ``r == 7`` the middle is the single slot 3, and
#: ``(1, 1, 1, 2, 1, 1, 25)`` costs exactly 11 -- depths 9 and 10 exhaust
#: with no solution and depth 11 finds a plan (393s) -- so the ``+1`` is
#: present at a run count no other measurement reached.  It is measured
#: against ``base(7) == 10``, which is itself proved twice: a full BFS on
#: ``(2, 1, 1, 1, 1, 1, 1)`` and on ``(1, 1, 1, 1, 1, 1, 2)`` at three inputs
#: (1.17M states, 344s and 195s), and an iterative deepening on
#: ``(1, 1, 1, 1, 1, 1, 26)`` at five that finds nothing at depth 9 and a
#: plan at depth 10.
#:
#: **The delta's mechanism, re-derived.**  A one-move finish from three
#: points requires an untouched span-0 point, and *only a wipe zeroes a
#: span*: the wipe collapses its victims to ``(0, 0, cls, ids)`` while every
#: survivor keeps its span, and :func:`_fold_merge` refuses to coalesce
#: anything whose span is nonzero.  Since every wipe takes ``asc[:k]`` or
#: ``desc[:k]`` -- 8116 of 8116 moves checked contiguous, none interior -- a
#: long *middle* run is the one group no prefix or suffix reaches without
#: dragging a neighbour, so it costs the extra move.  Verified as a
#: necessary condition on all 1005 reachable three-point states, with 462 of
#: them admitting a one-move finish as a positive control.
#:
#: The earlier telling of this mechanism was wrong in one detail worth
#: keeping straight: a ``k >= 2`` wipe does *not* require span-0 victims
#: (414 of 840 partial sweeps observed have a spanned victim).  The span-0
#: requirement lives in the landing, not the sweep.
#:
#: The ``base(r)`` half is regularity rather than proof.  Censusing optimal
#: plans gives ``r - 1 + 2 * floor((r - 2) / 2)`` moves, split as
#: ``floor((r - 2) / 2)`` doublings and the rest wipes -- ``(1, 15)`` is one
#: ``d``; ``(1, 1, 14)`` is ``d`` then ``u``; ``(1, 1, 1, 13)`` is
#: ``d, m, d, u, u``; ``(1, 1, 1, 1, 1, 11)`` is four ``d``, two ``m``,
#: three ``u``.  A doubling is what lets a landing split two survivors, so
#: the count tracks how often the cyclic order must be broken.  That is a
#: mechanism sketch, not a lower-bound argument: the closed form is
#: validated by measurement, and the ``m``-count is observed rather than
#: derived.
#:
#: **Four recorded counterexamples were greedy artifacts, and the record is
#: corrected here.**  Every pair below was measured against the descent's
#: path length, not against a distance, and under BFS each pair *agrees*:
#: ``(19, 2, 11)`` and ``(23, 2, 7)`` both cost 3; ``(34, 20, 10)`` and
#: ``(10, 20, 34)`` both cost 3; ``(40, 4, 8, 12)`` and ``(12, 4, 8, 40)``
#: both cost 6.  So the cums-mod-4-with-cap key and the ``min(x, K)``
#: recodings were never falsified against the true cost -- and the middle
#: -slot rule's supposed death at four inputs was the same mistake:
#: ``(1, 14, 1)`` costs 3 where ``(1, 1, 14)`` costs 2, exactly as the rule
#: says, against the claim that all 3-run words there cost 2 alike.  The
#: recorded ``base`` table was wrong too: ``base(2) = 1`` at every arity, not
#: 0 at four inputs -- a two-run word always has a run longer than 1, so its
#: start state has a nonzero span and cannot already be done.
#:
#: What this does *not* say: the ``>1``-pattern is sufficient only where it
#: was measured (``r <= 5`` at four and five inputs, ``r <= 6`` at three),
#: and ``r >= 8`` is untested at every arity -- ``base(8) = 13`` is the
#: closed form's prediction, not a measurement.  A full BFS at seven runs
#: costs about six minutes and 1.2M states, so the ladder above that is a
#: compute question rather than an open one.
#:
#: One law was found and refuted: ``3 * points`` bounds the exhaustive
#: three-input maxima exactly, with the bound attained.  It does not survive
#: -- four inputs violate it at ten points and five inputs reach 5.65 -- so
#: the tight small-arity fit is a coincidence of small states rather than
#: the shape of the algorithm.
#:
#: One thing measured and *rejected*: widening ``kcap`` from 3 to 6 in the
#: descent's move generation.  A re-implemented harness suggested it removed
#: long plateaus, but that harness started from ``2**n`` points where the
#: real descent starts from the run count, so it was not this algorithm.
#: Instrumenting the shipped beam gives byte-identical ratios at both values
#: -- median 1.92, worst 5.10 either way -- so the widening buys nothing.
#:
#: Substituting it for the flat 400 is a **no-op where 400 was enough**: over
#: 387 tables at three through eight inputs the emitted programs are
#: byte-identical, every one re-executed on the interpreter.  Where 400 was
#: *not* enough it lifts an arity, which is the point -- eight inputs already
#: used 359 steps, so nine overran the flat budget and built 1 of 3 random
#: tables, where the derived bound builds 3 of 3 and prints all 512 rows.
#:
#: What it is not any more is *arity-capping* by accident.
#: **Plan length is not program length, and for size it is close to the
#: wrong objective.**  Ops have wildly different prices: within one plan a
#: dive at 3004 costs 1490 characters from a resting accumulator and 4 when
#: the accumulator is already near, a doubling costs 751, and the finish
#: over a thousand.  The charge is the arithmetic distance travelled,
#: spelled in unary -- :func:`_sub_code` is ``k // 2`` characters -- so op
#: count barely correlates with emitted length.  Cutting a plan from 17 ops
#: to 6 was measured to save 13% of characters; optimising characters
#: directly saves 60% and more.
#:
#: **The cost model is closed form**, verified to zero error on all 56
#: constructible three-input tables.  Each op is priced by mirroring the
#: emitter's position updates, and :meth:`_FoldEmitter.finish` solves a
#: single congruence -- ``need = (-(byte(hi) - byte(lo)) - pos[lo]) % 256``,
#: whose unique in-window solution ``u`` costs ``u // 2 + 31``.  A candidate
#: plan can therefore be priced without emitting it.
#:
#: That model explains a fact worth recording: character cost is **not**
#: complement-invariant, though plan length is.  The answer bytes are 48 and
#: 49, so which class lands on top flips a ``+-1`` and moves the congruence
#: by 2 mod 256 -- about 127 characters.  ``01100111`` costs 5424 where its
#: complement ``10011000`` costs 5306.
#:
#: **One construction ships nothing yet but is verified:** every three-run
#: table builds from three greedy rises, no search -- 3176 to 3185
#: characters against this generator's 9838 to 10640, within 1 to 8 of the
#: enumerated optimum, each program executed on the interpreter with every
#: row correct at one fill width.  The cost is nearly independent of the run
#: lengths and of the arity.
#:
#: Three attempts to generalise that failed, recorded so they are not
#: retried.  Reranking this descent by characters instead of point count
#: looked like a 27.7% win and is **272% worse** on tables all variants
#: build -- the apparent saving was selection bias from abandoning hard
#: tables, at 116/254 coverage against 206/254.  A fixed catalogue of the
#: observed optimal shapes, walked greedily, saturates at 34 of 40 however
#: wide the amount branching.  And greedy on the exact cost model builds 8
#: of 40 at a mean of **-67%**.  Exact edge weights are not enough without a
#: cost-to-go term; the choice of move is not greedily determined.
_FOLD_STEP_SLOPE = 8
_FOLD_STEP_SLACK = 16


#: Which run-length words the three-phase construction serves.  ``r`` is the
def _fold_served(r: int, delta: int, pat1: int) -> bool:
    """Whether the three-phase construction serves this run-length word.

    ``r`` is the number of runs and the pair is ``(delta, pat[1])``; a word
    this rejects falls through to the rule construction, which is what
    happens for every ``r >= 6``.

    The second clause is not a budget but an identity.  ``delta`` is set
    when every middle index ``{(r - 1) // 2, r // 2}`` of the pattern is
    ``1``, and for ``r`` of 2, 3 and 4 that index set *contains* index 1 --
    so ``delta`` implies ``pat[1]``, and the three keys ``(2, 1, 0)``,
    ``(3, 1, 0)`` and ``(4, 1, 0)`` name states that cannot be built.  The
    converse does not hold and the clause is one-directional: ``(2, 0, 1)``
    and ``(4, 0, 1)`` are both reachable, because a middle index other than
    1 can be the ``0`` that clears ``delta``.  At ``r == 3`` the only middle
    *is* index 1, so there the implication runs both ways and ``(3, 0, 1)``
    is unreachable too.  At ``r == 5`` the middles are ``{2}`` alone, which
    frees index 1 entirely.

    This replaced a twelve-entry table of exactly these keys.  The set was
    recorded as a corpus measurement -- "the four combinations absent here
    never arise" -- but nothing about it depends on a corpus: enumerating
    every pattern to ``r == 12`` reproduces the tabulated set exactly, and
    the four absences are structural.  ``test_fold_served_is_reachability``
    re-derives it.
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

    *Peel* the ends inward with alternating ``d1``/``u2`` wipes at ``cmax``,
    *park* with one wipe at ``cmin`` and then double, and *close* with a wipe
    onto a landing followed by ``cmax`` wipes ending at ``k == 2``.  ``delta``
    -- set when the middle runs are long -- adds one peel step, which is the
    ``+1`` of the cost form.  The first move's direction follows which side
    carries the long run: dive when it sits low, rise when high.

    Below four runs the ends meet before the workspace runs out, so there is
    nothing to park and the plan is the peel alone.
    """
    if r == 2:
        opening: list[tuple[str, int, str]] = [("d" if pat1 else "u", 1, "cmax")]
        return tuple(opening + [("d", 1, "cmax")] * delta)
    if r == 3:
        if delta:
            return (("d", 1, "cmax"), ("d", 1, "cmax"), ("d", 2, "cmax"))
        return (("d", 1, "cmax"), ("u", 2, "cmax"))
    # One peel per run past the four the park and close consume, plus one
    # more for delta, alternating direction from the dive that starts it.
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
    """Return ``(cmin, cmax, survivor tops, victim class)`` for a wipe.

    Mirrors the window :func:`_fold_moves` computes, so a symbolic amount can
    be resolved against a state without enumerating that state's moves.
    """
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

    A landing is the semantic content of a step -- it is the merge -- so it
    is matched first, by the survivor index the symbol names; the index is
    what transfers between words of one pattern.  ``cmax`` and ``cmin`` fall
    back in that order.
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

    No enumeration, no beam and no backtracking: the plan is read from
    :func:`_fold_skeleton` and each amount is solved against the live
    state, so the work is one geometry computation per op.  Returns ``None``
    when the pattern is not tabulated or a step does not resolve, and the
    caller falls through to the rule construction.
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

    The plan is *constructed* either way now.  Where the table's run-length
    word is one :func:`_fold_served` accepts -- every word of at most
    five runs -- the skeleton names the plan outright, byte-stable with what
    always shipped.  Everywhere else :func:`_fold_reduce` runs the rules of
    :func:`_fold_rule_move` to two points.  The best-first search and the
    greedy descent that stood here are gone: over every state compared --
    all 254 non-constant three-input tables, 200-table four-input and
    150-table five-input samples plus parity, majority and the alternator
    at each -- the rules and the descent accept exactly the same set, and
    every rules-built table re-executes on the interpreter at one fill
    width, three through six inputs, plus eight, ten, eleven, and the
    twelve-input interleaved route.

    A state of at most two runs is a threshold state -- one class wholly
    below the other, whatever the runs' extents, provided the extents do
    not overlap -- and the emitter's endgame prints it directly, so the
    plan is empty.  That is what makes ``AND``, majority and every minterm
    a few dozen characters: on the popcount ladder they open as two runs.
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
