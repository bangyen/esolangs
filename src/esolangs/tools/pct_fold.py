"""Emit a %^2^-1 relocation fold, replaying every row as it goes.

The fold's emitting half: :class:`_FoldEmitter` mirrors every row's
accumulator and asserts after each character that the interpreter would agree,
so a plan from :mod:`esolangs.tools.pct_fold_plan` becomes a template only if
it really computes the table.
"""

from bisect import bisect_left, insort

from esolangs.tools.pct_codes import (
    _BYTE_ONE,
    _BYTE_ZERO,
    _HEADER_END,
    _LIMIT,
    _affine_code,
    _apply,
    _pad_pair,
    _sub_code,
    _sub_with,
)
from esolangs.tools.pct_fold_plan import (
    _COFACTOR_BRIDGE_POINTS,
    _FOLD_NARROW_STEP,
    _FOLD_STEP,
    _FOLD_STEP_SLACK,
    _FOLD_STEP_SLOPE,
    _FOLD_SUBSET_LADDER,
    _cofactor_done,
    _fold_norm,
    _fold_plan,
    _fold_reduce,
    _FoldKey,
    _FoldOp,
    _FoldState,
)


class _FoldEmitter:
    """Exact mirror of every row's accumulator, emitting body characters.

    Each method both appends the characters and applies their effect to all
    rows, asserting after every step that the interpreter would agree --
    which points get wiped, that nothing leaves the workspace, and finally
    that every row's value is congruent to its answer byte.

    The mirror is kept as a sorted list of positions under one lazy offset,
    so a uniform shift is one addition and the checks read the two ends;
    only the doubling rewrites every position.  A key is a row id: a raw
    row is its own key, and a landing that merges groups keeps the key of
    the largest, re-pointing the others' rows through ``self.group`` (a
    union-find, so a row's key costs a short chain).  ``self.chunks`` holds
    a group's rows as a list of frozensets, flattened only where a caller
    needs the set, so a landing onto a large group costs the victims and
    not the group.
    """

    def __init__(
        self, truth_table: str, n: int, weights: tuple[int, ...] | None = None
    ) -> None:
        self.table = truth_table
        self.rows = 2**n
        if weights is None:
            weights = _fold_uniform(n, _FOLD_STEP)
        start = _fold_positions(n, weights)
        self.body: list[str] = []
        self.load({r: (start[r], truth_table[r]) for r in range(self.rows)})

    def load(self, groups: "dict[_FoldKey, tuple[int, str]]") -> None:
        """Reset the mirror to ``groups``: key -> (position, class).

        A key is a row id or a frozenset of row ids; the group's key becomes
        its lowest row.  Positions are distinct -- two groups at one value
        are one group -- and that is asserted rather than assumed.
        """
        self.off = 0
        #: Stored position (actual minus ``off``), ascending.
        self.order: list[int] = []
        #: Stored position -> key, and its inverse.
        self.at: dict[int, int] = {}
        self.where: dict[int, int] = {}
        self.cls: dict[int, str] = {}
        self.chunks: dict[int, list[frozenset[int]]] = {}
        self.size: dict[int, int] = {}
        #: Row -> key, as a union-find parent map.
        self.group: dict[int, int] = {}
        for key, (value, c) in groups.items():
            members = key if isinstance(key, frozenset) else frozenset([key])
            root = min(members)
            if value in self.at:
                raise AssertionError(value)
            self.at[value] = root
            self.where[root] = value
            self.cls[root] = c
            self.chunks[root] = [members]
            self.size[root] = len(members)
            for row in members:
                self.group[row] = root
        self.order = sorted(self.at)

    # The tests and the staged routes read the mirror as key -> value.

    @property
    def pos(self) -> dict[int, int]:
        return {key: stored + self.off for stored, key in self.at.items()}

    def value(self, key: int) -> int:
        return self.where[key] + self.off

    def members(self, key: int) -> frozenset[int]:
        """Return the rows a key stands for, flattened."""
        return frozenset().union(*self.chunks[key])

    def find(self, row: int) -> int:
        """Return the key of ``row``'s current group, compressing the path."""
        root = row
        while self.group[root] != root:
            root = self.group[root]
        while self.group[row] != root:
            self.group[row], row = root, self.group[row]
        return root

    def lo(self) -> int:
        return self.order[0] + self.off

    def hi(self) -> int:
        return self.order[-1] + self.off

    def _sub(self, k: int) -> str:
        code = _sub_code(k)
        if code is None:
            raise AssertionError(k)
        return code

    def descend(self, k: int) -> None:
        if k == 0:
            return
        if k == 1:
            self.descend(3)
            self.plain_rise(2)
            return
        if k < 2:
            raise AssertionError("k >= 2")
        if not self.hi() <= _LIMIT:
            raise AssertionError("all(v <= _LIMIT for v in self.pos.values())")
        self.body.append(self._sub(k))
        self.off -= k

    def plain_rise(self, k: int) -> None:
        if k == 0:
            return
        if k == 1:
            self.plain_rise(3)
            self.descend(2)
            return
        if k < 2:
            raise AssertionError("k >= 2")
        if not (self.lo() >= -_LIMIT and self.hi() <= _LIMIT):
            raise AssertionError(
                "all(-_LIMIT <= v <= _LIMIT for v in self.pos.values())"
            )
        if not self.hi() + k <= _LIMIT:
            raise AssertionError("all(v + k <= _LIMIT for v in self.pos.values())")
        self.body.append("p" + self._sub(k) + "p")
        self.off += k

    def preshift(self, delta: int) -> None:
        if delta < 0:
            self.descend(-delta)
        elif delta > 0:
            self.plain_rise(delta)

    def double(self, *, next_is_rise: bool) -> None:
        top = self.hi()
        bot = self.lo()
        spread = top - bot
        if 2 * spread > 2 * _LIMIT:
            raise AssertionError("2 * spread <= 2 * _LIMIT")
        want_top = 1501
        if next_is_rise:
            # The next command sequence opens with ``p``, which wipes
            # anything below -3003, so the doubled state must fit both ways.
            want_top = max(spread - 1501, 0)
            if want_top > 1501:
                raise AssertionError(spread)
        self.preshift(want_top - top)
        if not 2 * self.hi() <= _LIMIT:
            raise AssertionError("all(2 * v <= _LIMIT for v in self.pos.values())")
        self.body.append("m")
        # Actual values double: stored ``s + off`` becomes ``2s + 2off``.
        self.at = {stored * 2: key for stored, key in self.at.items()}
        self.where = {key: stored * 2 for key, stored in self.where.items()}
        self.order = [stored * 2 for stored in self.order]
        self.off *= 2

    def _vic(self, vids: frozenset[int]) -> set[int]:
        """Return the keys whose rows are exactly ``vids``, or raise.

        Every row of ``vids`` belongs to some found key, so the keys' rows
        cover ``vids``; keys are disjoint, so covering it with the same
        total size is equality.  Costs the victims' rows, not the state.
        """
        if not vids:
            raise AssertionError(vids)
        vic = {self.find(row) for row in vids}
        if sum(self.size[key] for key in vic) != len(vids):
            raise AssertionError(vids)
        return vic

    def _survivor_lo(self, vic: set[int]) -> int | None:
        """Return the lowest value held by a key outside ``vic``."""
        skip = {self.where[key] for key in vic}
        for stored in self.order:
            if stored not in skip:
                return stored + self.off
        return None

    def _survivor_hi(self, vic: set[int]) -> int | None:
        skip = {self.where[key] for key in vic}
        for stored in reversed(self.order):
            if stored not in skip:
                return stored + self.off
        return None

    def _move(self, key: int, value: int) -> None:
        """Put ``key`` at ``value``, merging with whatever already sits there."""
        stored = self.where[key]
        del self.at[stored]
        del self.order[bisect_left(self.order, stored)]
        target = value - self.off
        self.where[key] = target
        if target in self.at:
            self._merge(self.at[target], key)
            return
        self.at[target] = key
        insort(self.order, target)

    def _merge(self, keep: int, other: int) -> None:
        """Absorb ``other`` into ``keep``, which stays at its position."""
        if self.cls[other] != self.cls[keep]:
            raise AssertionError("cross-class landing")
        if self.size[other] > self.size[keep]:
            # The larger group's key survives so the union-find stays short;
            # swap the *labels* so ``keep`` is the one at the position.
            stored = self.where[keep]
            self.at[stored] = other
            self.where[other] = stored
            keep, other = other, keep
        self.group[other] = keep
        self.chunks[keep].extend(self.chunks.pop(other))
        self.size[keep] += self.size.pop(other)
        del self.cls[other]
        del self.where[other]

    def dive(self, c: int, vids: frozenset[int]) -> None:
        vic = self._vic(vids)
        if len({self.cls[v] for v in vic}) != 1:
            raise AssertionError("len({self.cls[v] for v in vic}) == 1")
        vt = max(self.value(v) for v in vic)
        surv_lo = self._survivor_lo(vic)
        q1 = (surv_lo - vt) if surv_lo is not None else 40
        if not (_LIMIT + 1 <= c <= _LIMIT + q1):
            raise AssertionError((c, q1))
        d = c + vt
        if d < 2:
            self.preshift(2 - d)
            d = c + max(self.value(v) for v in vic)
        self.descend(d)
        below = set()
        for stored in self.order:
            if stored + self.off >= -_LIMIT:
                break
            below.add(self.at[stored])
        if below != vic:
            raise AssertionError((below, vic))
        self.body.append("pp")
        self._land(vic, 0)
        if not (self.lo() >= -_LIMIT and self.hi() <= _LIMIT):
            raise AssertionError("-_LIMIT <= self.pos[p] <= _LIMIT")

    def rise(self, c: int, vids: frozenset[int]) -> None:
        vic = self._vic(vids)
        if len({self.cls[v] for v in vic}) != 1:
            raise AssertionError("len({self.cls[v] for v in vic}) == 1")
        vb = min(self.value(v) for v in vic)
        surv_hi = self._survivor_hi(vic)
        q1 = (vb - surv_hi) if surv_hi is not None else 40
        if not (_LIMIT + 1 <= c <= _LIMIT + q1):
            raise AssertionError((c, q1))
        u = c - vb
        if u < 2:
            self.preshift(-(2 - u))
            u = c - min(self.value(v) for v in vic)
        if self.lo() < -_LIMIT:
            raise AssertionError("min(self.pos.values()) >= -_LIMIT")
        top = self._survivor_hi(vic)
        if top is not None and top + u > _LIMIT:
            raise AssertionError("all(self.pos[p] + u <= _LIMIT for p in surv)")
        self.body.append("p" + self._sub(u) + "p")
        self.off += u
        over = set()
        for stored in reversed(self.order):
            if stored + self.off <= _LIMIT:
                break
            over.add(self.at[stored])
        if over != vic:
            raise AssertionError((over, vic))
        # Any next command's pre-check resets the victims; one ``s`` makes
        # that flush explicit and costs a uniform -2 everyone absorbs.
        self.body.append("s")
        self._land(vic, 0)
        self.off -= 2

    def _land(self, vic: set[int], val: int) -> None:
        """Put the victims at ``val``, merging them and anything already there."""
        for v in vic:
            self._move(v, val)

    def byte(self, key: int) -> int:
        return _BYTE_ONE if self.cls[key] == "1" else _BYTE_ZERO

    def finish(self) -> None:
        """Set the one residue that matters and align the print.

        Two points remain, one per class (or one, for a constant table).
        Their final gap must be congruent to the difference of their answer
        bytes; the last relocation of the upper point has the whole
        lower-point gap as its window, which spans a full residue system
        once the gap exceeds 257, so exactly one amount in it qualifies.
        A uniform tail shift then puts the pair onto the bytes themselves.
        """
        if len(self.at) == 1:
            p = self.at[self.order[0]]
            t = (self.byte(p) - self.value(p)) % 256
            room = _LIMIT - self.value(p)
            while t > room:
                t -= 256
            self.preshift(t)
        else:
            lo, hi = (self.at[stored] for stored in self.order)
            if self.value(hi) - self.value(lo) < 258:
                self.preshift(-(self.value(lo) + 2600))
                u1 = max(_LIMIT + 1 - self.value(hi), 2)
                if self.value(lo) + u1 > _LIMIT:
                    raise AssertionError("self.pos[lo] + u1 <= _LIMIT")
                self.body.append("p" + self._sub(u1) + "ps")
                self.off += u1
                if self.value(hi) <= _LIMIT:
                    raise AssertionError("self.pos[hi] > _LIMIT")
                if self.value(lo) > _LIMIT:
                    raise AssertionError("self.pos[lo] <= _LIMIT")
                self._move(hi, 0)
                self.off -= 2
                lo, hi = (self.at[stored] for stored in self.order)
            gap = self.value(hi) - self.value(lo)
            if gap < 258:
                raise AssertionError(gap)
            need = (-(self.byte(hi) - self.byte(lo)) - self.value(lo)) % 256
            umin = max(_LIMIT + 1 - self.value(hi), 2)
            umax = _LIMIT - self.value(lo)
            u = next(
                (c0 for c0 in range(umin, umax + 1) if c0 % 256 == need),
                None,
            )
            if u is None:
                raise AssertionError((umin, umax, need))
            self.body.append("p" + self._sub(u) + "ps")
            self.off += u
            if self.value(hi) <= _LIMIT:
                raise AssertionError("self.pos[hi] > _LIMIT")
            if self.value(lo) > _LIMIT:
                raise AssertionError("self.pos[lo] <= _LIMIT")
            self._move(hi, 0)
            self.off -= 2
            lo, hi = (self.at[stored] for stored in self.order)
            t = (self.byte(hi) - self.value(hi)) % 256
            room = _LIMIT - self.value(hi)
            # Unreachable here, unlike in the one-point branch above: the
            # block just put ``hi`` at 0 and then shifted everything down
            # by 2, so ``room`` is exactly ``_LIMIT + 2`` while ``t`` is a
            # residue mod 256.  255 < 3005, so the lift never fires.  The
            # loop stays because the one-point branch's does, and the two
            # read as one rule.
            while t > room:  # pragma: no cover - room is _LIMIT + 2 > 255
                t -= 256
            self.preshift(t)
        for stored, p in self.at.items():
            if (stored + self.off) % 256 != self.byte(p) % 256:
                raise AssertionError(
                    (
                        stored + self.off,
                        self.cls[p],
                    )
                )
            if stored + self.off > _LIMIT:
                raise AssertionError("self.pos[p] <= _LIMIT")
        self.body.append("e")


def _fold_uniform(n: int, step: int) -> tuple[int, ...]:
    """Return the uniform ladder as a weight vector: ``acc = -step * r``."""
    return tuple(step * 2 ** (n - 1 - i) for i in range(n))


def _fold_setters(n: int, weights: tuple[int, ...]) -> list[tuple[str, str]]:
    """One subtracting branch per input; the hold matches it in width.

    Input ``i`` subtracts ``weights[i]`` when its bit is 1 and holds when it
    is 0.  Both branches must come out the same width or the program leaks
    its inputs through ``len()``.

    ``s`` subtracts 2, so an amount that is a multiple of 4 spells at an even
    width and the hold is that many ``p``.  The narrow ladder
    (:data:`_FOLD_NARROW_STEP`) gives its last input an amount of 2, whose
    cheapest spelling ``"s"`` is one character wide -- and **the identity has
    no odd-width spelling at all**, searched exhaustively over ``s``/``i``/
    ``p``/``m`` through width 6: an odd number of the only sign-flipping
    command cannot compose to ``+0``.  So a lone ``s`` can never be padded to
    match a hold, and the subtraction is *respelled* wider instead --
    ``iipssp`` subtracts 2 in six characters, against ``pppppp`` holding --
    which is the same respelling move :func:`_pad_pair`'s odd-gap refusal
    forces elsewhere in this module.

    **Two respellings, on disjoint ranges.**  The overshoot above negates,
    so it dies once ``amount`` reaches the reset line; a pure descent that
    trades ``s`` for ``i`` never rises and so has no such ceiling, but it
    has no even-width form for 1, 2, 3 or 7.  Between them every amount up
    to ``2 * _LIMIT + 2`` spells, which is the whole range a setter can be
    asked for -- positions span ``+-_LIMIT``, so the widest gap is 6006 and
    :func:`_interleaved_fold` asks for ``span + 2``.
    """
    out = []
    for i in range(n):
        amount = weights[i]
        if amount <= 0:
            raise AssertionError(amount)
        code = _sub_code(amount)
        if code is not None and len(code) % 2 == 0:
            out.append(("p" * len(code), code))
            continue
        # Odd (or unspellable) width: no hold exists there, so subtract the
        # same amount at the next even width.  Overshoot by ``k`` and add it
        # back through a ``p``-wrapped subtraction,
        # ``sub(amount + k) + "p" + sub(k) + "p"``.  This is the shorter of
        # the two respellings, but it only works while ``amount + k`` stays
        # inside the reset line; the descent below covers the rest.
        #
        # ``_sub_code`` alone never gets there: it spells with as many ``s``
        # as it can, so both halves shrink together and the total width stays
        # odd for every ``k``.  Spending ``i`` -- which subtracts 3, so two of
        # them move 6 in two characters where three ``s`` would take three --
        # is what changes the parity.  ``iipssp`` is the case that matters:
        # ``ii`` subtracts 6, ``pssp`` adds 4 back, six characters for a net
        # of 2, against ``pppppp`` holding.
        spellings = [
            over + "p" + back + "p"
            for over_i in range(5)
            for back_i in range(5)
            for k in range(2, 14)
            if (over := _sub_with(amount + k, over_i)) is not None
            and (back := _sub_with(k, back_i)) is not None
            and len(over + back) % 2 == 0
        ]
        widened = min(
            (c for c in spellings if _apply(0, c) == -amount), key=len, default=None
        )
        if widened is None:
            # The overshoot negates, and from 3002 up that is fatal: ``p``
            # leaves the accumulator at ``+(amount + k)``, above the 3003
            # reset line, so the next command zeroes it and the add-back
            # nets ``+k`` instead of ``-amount``.  Every one of the 1504
            # amounts in 3002..6008 fails that way, and ``span + 2`` in
            # :func:`_interleaved_fold` reaches them once the spread hits
            # 3000 -- where this used to raise rather than decline.
            #
            # Trading ``s`` for ``i`` at the amount itself needs no ``p``:
            # it only ever descends, so the reset cannot fire at any
            # magnitude.  Two ``i`` for three ``s`` moves the same 6 in one
            # character less, which is what reaches the other parity.  It
            # is tried second because the overshoot is the shorter spelling
            # where both apply, and every template that builds today is
            # built on it -- 1, 2, 3 and 7 have no even-width descent at
            # all and are exactly the amounts that still need it.
            widened = min(
                (
                    code
                    for threes in range(8)
                    if (code := _sub_with(amount, threes)) is not None
                    and len(code) % 2 == 0
                    and _apply(0, code) == -amount
                ),
                key=len,
                default=None,
            )
        if widened is None:
            raise AssertionError(amount)
        if _apply(0, widened) != -amount:
            raise AssertionError((amount, widened))
        out.append(("p" * len(widened), widened))
    return out


def _fold(truth_table: str, n: int) -> str | None:
    """Build a fold template, or ``None`` if no plan is found.

    The constructions above all place every row's value in a single pass
    and read the table's structure off a weighting, which is what bounded
    the deep band at five inputs: an additive weighting has ``n`` degrees
    of freedom against ``2**n`` residue constraints.  The fold instead
    treats the program as a sequence of *relocations*.  Rows start on a
    rigid ladder (``acc = -4r``); each wipe -- push a group over the reset
    line, top or bottom -- relocates it by exactly ``3004 + slack``, where
    the slack is bounded by the gap to its nearest survivor; the doubling
    ``m`` regrows gaps past 3004, which is what lets a landing split two
    survivors and change the groups' cyclic order (wipes alone cap the
    spread at 3003 and provably never can); and rows of one class are
    merged by landing them on the same value, which erases their history.
    The plan is one named move per state -- the case analysis of
    :func:`_fold_rule_move` -- and the emitted program is *checked*, not
    trusted: every step is mirrored on all ``2**n`` rows and asserted.

    Only the final two points carry a residue requirement -- their gap must
    be congruent to the difference of the answer bytes mod 256 -- and the
    last relocation's window spans a full residue system, so the residue
    work needs no weighting at all.  That is why the fold has no arity wall
    of its own below the workspace bound: the ladder must fit inside the
    6006 values a ``p`` can traverse.

    **Three ladders are tried**, and which one serves is what sets the reach
    -- see :func:`_fold_ladders`.  The two uniform spacings come first
    because every template that builds today is built on them; the packed
    ladder (:data:`_FOLD_SUBSET_LADDER`) is the fallback, and it is what
    carries eleven inputs, spending only the ``2**n + 1`` that distinctness
    costs against the uniform ladder's ``2 * (2**n - 1)``.

    Reach, measured rather than argued: every table at ``n <= 4``
    exhaustively, and samples at five through **eleven** that build and print
    correctly on the shipped interpreter.  Twelve is where the construction
    stops, and the end is *structural*: no ladder laying ``2**12`` distinct
    positions spans less than 4095, the doubling is offered only under a
    spread of 3002, and without the doubling the groups' cyclic order is
    provably invariant -- the search from such a state exhausts after fifteen
    states rather than running out of budget.
    """
    for weights in _fold_ladders(n):
        built = _fold_at(truth_table, n, weights)
        if built is not None:
            return built
    return None


def _fold_ladders(n: int) -> list[tuple[int, ...]]:
    """Return the ladders to try, in order, for an ``n``-input table.

    The two uniform ones come first because every template that already
    builds is built on them, so trying anything else ahead would rewrite
    output for tables that need no help.  The subset-sum ladder is the
    fallback that lifts the arity: see :data:`_FOLD_SUBSET_LADDER`.
    """
    out = [_fold_uniform(n, _FOLD_STEP), _fold_uniform(n, _FOLD_NARROW_STEP)]
    packed = _fold_subset_weights(n)
    if packed is not None:
        out.append(packed)
    return out


def _fold_subset_weights(n: int) -> tuple[int, ...] | None:
    """Return the packed distinct-subset-sum ladder, or ``None`` past its reach.

    See :data:`_FOLD_SUBSET_LADDER` for why this shape, and why ``2**n + 1``
    is the floor any such ladder pays.  ``n >= 2`` throughout: the fold is
    only ever reached above two inputs.
    """
    # The tail starts one past the head's total, which is what keeps every
    # subset sum distinct: a power exceeding the sum of everything below it
    # can never be matched by them.
    head = _FOLD_SUBSET_LADDER
    start = sum(head) - 1
    weights = (*head, *(start * 2**i for i in range(n - len(head))))
    return weights if sum(weights) <= _LIMIT else None


def _cofactor_class(truth_table: str, n: int, row: int, laid: int) -> str:
    """Return ``row``'s suffix cofactor after the first ``laid`` inputs.

    An interleaved build may merge two accumulator values only when every
    completion of their unlaid inputs has the same answer.  The substring is
    that exact future function; using the final output bit here would merge
    rows that a later placeholder still has to separate.
    """
    width = 2 ** (n - laid)
    prefix = row >> (n - laid)
    return truth_table[prefix * width : (prefix + 1) * width]


def _fold_to_cofactors(state: _FoldState) -> list[_FoldOp] | None:
    """Merge equal suffix cofactors, leaving distinct ones separate.

    This is deliberately a small-state bridge: it is used between
    placeholders, where equal cofactors have already reduced the live
    state.  The final two-answer reduction still goes through
    :func:`_fold_plan`.

    The size gate is unchanged and still costs no reach.  Exhaustively over
    ``n <= 4`` -- 33628 tables build -- no successful build ever hands this
    a state above eight points, and the constructed adversaries that grow
    the state on purpose (a function of only the first ``k`` inputs embedded
    at ``n = 8, 10, 12``, and a middle window whose growth starts late) top
    out at four.  A miss here aborts the candidate outright, so refusing a
    larger state changes no output -- only how fast a doomed arity gives up.

    Behind the gate the old best-first search is replaced by the same rules
    that plan the whole fold, aimed at :func:`_cofactor_done` -- one wiped
    point per distinct cofactor -- instead of two points.  Over every bridge
    state the instrumented routes hand in (658, from the documented
    adversaries plus all 256 three-input tables forced through the route)
    the rules and the search accept exactly the same set: 301 solved, zero
    lost, zero gained.
    """
    start = _fold_norm(list(state))
    if _cofactor_done(start):
        return []
    if len(start) > _COFACTOR_BRIDGE_POINTS:
        return None
    return _fold_reduce(start, _cofactor_done)


def _fold_span(state: _FoldState) -> int:
    """Return ``state``'s occupied top-to-bottom extent."""
    return max(point for point, _, _, _ in state) - min(
        point - extent for point, extent, _, _ in state
    )


def _split_setter(total: int) -> tuple[str, str, int, int] | None:
    """Spell an up/down setter pair whose moves sum to ``total``."""
    middle = total // 2
    for up in range(max(2, middle - 8), min(total - 1, middle + 8) + 1):
        down = total - up
        pair = _pad_pair(_affine_code(1, up), _affine_code(1, -down))
        if pair is not None:
            zero, one = pair
            return zero, one, up, down
    return None


def _centred_setter(span: int) -> tuple[str, str, int, int] | None:
    """Separate a span with equal-width upward and downward setters."""
    return _split_setter(span + 2)


def _interleaved_final_pair(truth_table: str, n: int) -> str | None:
    """Build a table by laying a prefix ladder and folding the final two inputs.

    The all-row fold ends at eleven inputs by counting: ``2**12`` distinct
    positions span at least 4095, past what any laid ladder can hold.  This
    route never holds all rows apart.  The first ``n - 2`` inputs lay as a
    ladder whose points carry four-row cofactors; the next input splits them
    into two-row cofactors -- at most four *distinct* ones -- which the fold
    merges class by class; the last input splits the survivors into answer
    bits for the ordinary two-class endgame.  Merging by cofactor class
    rather than answer bit is what keeps every wipe's victim block
    class-homogeneous, so the reduce is thousands of cheap merges rather
    than the one-per-doubling starvation an answer-keyed interleave hits.

    The prefix ladder is picked by the same rule the all-row fold uses: the
    narrow uniform ladder while its footprint fits the workspace (ten
    inputs, so twelve-input tables), and the packed distinct-subset-sum
    ladder past that (eleven, so thirteen).  Fourteen inputs would need a
    twelve-input prefix, and no ladder lays ``2**12`` distinct positions
    inside the footprint -- the same counting wall, one stage later.
    """
    prefix = n - 2
    narrow = _fold_uniform(prefix, _FOLD_NARROW_STEP)
    weights = narrow if sum(narrow) <= _LIMIT else _fold_subset_weights(prefix)
    if weights is None:
        return None
    setters = _fold_setters(prefix, weights)
    positions = _fold_positions(prefix, weights)
    emitter = _FoldEmitter.__new__(_FoldEmitter)
    emitter.table = truth_table
    emitter.rows = 2**n
    block = 2 ** (n - prefix)
    emitter.load(
        {
            frozenset(range(row * block, (row + 1) * block)): (
                positions[row],
                truth_table[row * block : (row + 1) * block],
            )
            for row in range(2**prefix)
        }
    )
    emitter.body = ["{X" + str(index) + "}" for index in range(prefix)]

    def lay(index: int, *, cofactor: bool) -> tuple[str, str] | None:
        lo = emitter.lo()
        hi = emitter.hi()
        span = hi - lo
        if weights is narrow:
            got = _centred_setter(span)
        else:
            # A compacted state's points can span past 3001, where disjoint
            # bands no longer fit the workspace -- and with class-many
            # points they are not needed.  Two children collide only when
            # their parents sit exactly ``up + down`` apart, so the first
            # even total that is no pair's distance splits collision-free,
            # the same computed value the wipe rules land on.  Odd totals
            # never spell: the identity has no odd-width hold.
            values = list(emitter.pos.values())
            dists = {b - a for a in values for b in values if b > a}
            got = None
            # The range holds more even totals than there are distances,
            # so a free one always exists and the loop always breaks --
            # and `_split_setter` spells every total it is handed here.
            for total in range(4, 2 * len(dists) + 8, 2):  # pragma: no branch
                if total in dists:
                    continue
                got = _split_setter(total)
                if got is not None:  # pragma: no branch
                    break
        if got is None:
            return None
        zero, one, up, down = got
        shift = -_LIMIT - lo + down
        if shift > _LIMIT - hi - up:
            return None
        emitter.preshift(shift)
        laid: dict[_FoldKey, tuple[int, str]] = {}
        occupied: dict[int, str] = {}
        for key, value in emitter.pos.items():
            rows = emitter.members(key)
            for bit, code in ((0, zero), (1, one)):
                picked = {row for row in rows if (row >> (n - 1 - index)) & 1 == bit}
                # No known table reaches this: a merged key would have to
                # hold rows agreeing on the bit being laid, and the reduce
                # merges by cofactor class, which splits on exactly that
                # bit.  320 random tables at three to ten inputs, every
                # documented shape, and the low-bit-ignoring families all
                # miss it.
                if not picked:  # pragma: no cover - see above
                    continue
                value2 = _apply(value, code)
                if not -_LIMIT <= value2 <= _LIMIT:
                    return None
                cls = (
                    _cofactor_class(truth_table, n, next(iter(picked)), index + 1)
                    if cofactor
                    else truth_table[next(iter(picked))]
                )
                if value2 in occupied and occupied[value2] != cls:
                    return None
                occupied[value2] = cls
                key2: _FoldKey = (
                    next(iter(picked)) if len(picked) == 1 else frozenset(picked)
                )
                laid[key2] = (value2, cls)
        emitter.load(laid)
        emitter.body.append("{X" + str(index) + "}")
        return zero, one

    def state() -> _FoldState:
        return _fold_norm(
            [
                (value, 0, emitter.cls[key], emitter.members(key))
                for key, value in emitter.pos.items()
            ]
        )

    def emit(ops: list[_FoldOp]) -> None:
        for index, (kind, _, amount, rows) in enumerate(ops):
            if kind == "m":
                emitter.double(
                    next_is_rise=index + 1 < len(ops) and ops[index + 1][0] == "u"
                )
            elif kind == "d":
                emitter.dive(amount, rows)
            else:
                emitter.rise(amount, rows)

    if weights is not narrow:
        # The packed ladder lays its rows at *unit* gaps, so every landing
        # window is one already-occupied amount and the first wipe has no
        # collision-free landing; the split below would double the points
        # and put the span past the doubling bound, freezing that jam in.
        # Compacted first -- one point per four-row cofactor, at most
        # sixteen -- the state still spans only the ladder, where the
        # doubling fires and regrows the gaps the conveyor needs, and every
        # later stage works on class-many points rather than row-many.
        compact = state()
        # Sixteen live classes rather than two: case 2's window only ever
        # serves its own class, so the conveyor hops more between merges --
        # measured 11.3 ops per starting point where the two-class corpus
        # fits slope 8.  Doubling the slope keeps the guard linear and the
        # refusal path intact.
        packed = _fold_reduce(
            compact,
            _cofactor_done,
            budget=2 * _FOLD_STEP_SLOPE * len(compact) + _FOLD_STEP_SLACK,
        )
        if packed is None:
            return None
        emit(packed)
    first = lay(prefix, cofactor=True)
    if first is None:
        return None
    setters.append(first)
    partial = _fold_reduce(state(), _cofactor_done)
    if partial is None:
        return None
    emit(partial)
    second = lay(prefix + 1, cofactor=False)
    if second is None:
        return None
    setters.append(second)
    final = _fold_plan(state())
    if final is None:
        return None
    emit(final)
    emitter.finish()
    header = ";".join(
        f"{index}={zero}|{one}" for index, (zero, one) in enumerate(setters)
    )
    return header + _HEADER_END + "".join(emitter.body)


def _interleaved_fold(truth_table: str, n: int) -> str | None:
    """Try a placeholder/fold/placeholder build before the all-row fallback.

    Every ``{Xi}`` appears once and in name order, but unlike :func:`_fold_at`
    its setter is emitted immediately before the cofactor fold it enables.
    The emitter mirrors every raw row, so a returned candidate is checked at
    every reset and landing just like the shipped ladder path.

    The current bridge deliberately accepts only compactable intermediate
    states; it is an executable replacement skeleton, not yet the large-state
    gap controller.  A miss lets the established fold try its ladders.
    """
    if n in (12, 13):
        staged = _interleaved_final_pair(truth_table, n)
        # Every twelve- and thirteen-input table the suite builds is served
        # by the pair; a miss would fall through to the ladders below.
        if staged is not None:  # pragma: no branch
            return staged
    setters: list[tuple[str, str]] = []
    rows = frozenset(range(2**n))
    emitter = _FoldEmitter.__new__(_FoldEmitter)
    emitter.table = truth_table
    emitter.rows = 2**n
    emitter.load({rows: (0, truth_table)})
    emitter.body = []

    for index in range(n):
        # A live cofactor that takes the same suffix on both branches does not
        # need a new rung at all, and identity branches keep a late ignored
        # input from re-expanding a compacted state merely to collapse it
        # again.  Where a split remains, one current span plus a
        # gap of two keeps the 0 and 1 bands disjoint without paying a global
        # binary weight for inputs already folded away.
        splits = False
        for group_key in emitter.pos:
            raw = emitter.members(group_key)
            children = {_cofactor_class(truth_table, n, row, index + 1) for row in raw}
            if len(children) > 1:
                splits = True
                break
        if splits:
            span = emitter.hi() - emitter.lo()
            zero, one = _fold_setters(1, (span + 2,))[0]
        else:
            zero = one = "pp"
        setters.append((zero, one))
        laid: dict[_FoldKey, tuple[int, str]] = {}
        # A previously merged cofactor splits only on this input.  Rows taking
        # the same branch retain one identical suffix cofactor, which is the
        # inductive fact the merge below asserts rather than assumes.
        by_value: dict[tuple[int, str], set[int]] = {}
        for group_key, value in emitter.pos.items():
            raw = emitter.members(group_key)
            for bit in (0, 1):
                picked = {row for row in raw if (row >> (n - 1 - index)) & 1 == bit}
                if not picked:  # pragma: no cover - both branches always populated
                    # A group is a *union* of rows -- it starts as all of them
                    # and only ever merges -- so it is never filtered on an
                    # input it has not consumed yet, and both values of that
                    # input are always present.  Measured over 24186 groups
                    # (all n=2 and n=3 tables, 400 random tables at n=4..6):
                    # none was constant on the bit being split.
                    continue
                code = one if bit else zero
                new_value = _apply(value, code)
                if not -_LIMIT <= new_value <= _LIMIT:
                    return None
                suffixes = {
                    _cofactor_class(truth_table, n, row, index + 1) for row in picked
                }
                if len(suffixes) != 1:  # pragma: no cover - the merge invariant
                    # This is the inductive fact the comment above names, and
                    # it holds by construction: groups are keyed by their
                    # suffix cofactor, so a group's rows already share one,
                    # and splitting it on the next input refines that key
                    # rather than mixing two.  Measured over 1772 tables (all
                    # n=2 and n=3, 500 random at n=4..6): never violated.  The
                    # check stays as the assertion that keeps it honest.
                    return None
                cls = next(iter(suffixes))
                by_value.setdefault((new_value, cls), set()).update(picked)
        # A position collision across unequal cofactors would erase a future
        # distinction before the planner can see it.
        occupied: dict[int, str] = {}
        for (value, cls), members in by_value.items():
            if value in occupied and occupied[value] != cls:
                return None
            occupied[value] = cls
            coalesced_key: _FoldKey = (
                next(iter(members)) if len(members) == 1 else frozenset(members)
            )
            laid[coalesced_key] = (value, cls)
        emitter.load(laid)
        emitter.body.append("{X" + str(index) + "}")

        items = [
            (value, 0, emitter.cls[key], emitter.members(key))
            for key, value in emitter.pos.items()
        ]
        partial = _fold_to_cofactors(_fold_norm(items))
        if partial is None:
            return None
        for kind, _, amount, row_ids in partial:
            if kind == "m":
                emitter.double(next_is_rise=False)
            elif kind == "d":
                emitter.dive(amount, row_ids)
            else:
                emitter.rise(amount, row_ids)

    final_items = [
        (value, 0, emitter.cls[key], emitter.members(key))
        for key, value in emitter.pos.items()
    ]
    # After the last placeholder a suffix is one answer bit, so the existing
    # two-class plan and residue endgame apply unchanged.
    final = _fold_plan(_fold_norm(final_items))
    if final is None:  # pragma: no cover - a done state is never refused
        # Every state reaching here is already ``_fold_done`` (see below), and
        # ``_fold_plan`` on a done state returns the empty plan rather than
        # refusing: ``_fold_reduce`` checks the done condition before it looks
        # for a move.  Measured over 4000 constructed done states: never
        # ``None``.  The check stays as the caller's half of the contract.
        return None
    # ``final`` is always empty, so this loop never has a body to run: by the
    # last placeholder every row has been merged onto its cofactor's single
    # point, which is exactly ``_fold_done``, and ``_fold_plan`` returns the
    # empty plan for a state that already satisfies it.  Measured: every one
    # of 164 states reaching ``_fold_plan`` here was already done on arrival
    # (all n=2 and n=3 tables exhaustively, random tables at n=4..11).  The
    # loop stays because the emptiness is a property of the *state*, not of
    # this call -- a future stage that left work behind would need it.
    for kind, _, amount, row_ids in final:  # pragma: no cover
        if kind == "m":
            emitter.double(next_is_rise=False)
        elif kind == "d":
            emitter.dive(amount, row_ids)
        else:
            emitter.rise(amount, row_ids)
    emitter.finish()
    header = ";".join(
        f"{index}={zero}|{one}" for index, (zero, one) in enumerate(setters)
    )
    return header + _HEADER_END + "".join(emitter.body)


#: A two-sided ladder was built and **removed once measured**, the same way
#: the positive-ladder band was.  One weight is made negative -- an *adding*
#: setter, spelled ``p sub(k) p``, whose inner subtraction must come out even
#: so the ``p``-repeated hold is an identity rather than a negation -- which
#: moves half the rows above zero.  That doubles the *positions* available,
#: ``[-_LIMIT, _LIMIT]`` rather than ``[-_LIMIT, 0]``, and at twelve inputs
#: it lays 4096 distinct rows peaking at 2050, comfortably inside 3003.
#:
#: It still serves nothing, because **positions are not the binding
#: resource**: the plan needs the state's *span*, and 4096 distinct integers
#: span at least 4095 wherever they sit.  A wipe relocates by at least 3004
#: and the guard refuses a state spanning more than ``2 * _LIMIT``, so a
#: 4099-wide start has only two legal moves and the descent dies at once;
#: the doubling is offered only under ``spread * 2 <= 2 * _LIMIT - 2``, which
#: a span past 3002 can never satisfy, and the doubling is what this module
#: proves is needed to reorder groups at all.  Measured: 0 of 18 tables
#: across five arities are served by the straddle ladder and not by the
#: packed one.  Straddling therefore buys room the construction cannot spend.


def _fold_positions(n: int, weights: tuple[int, ...]) -> list[int]:
    """Where each row's accumulator sits after the setters have run.

    Input ``i`` subtracts ``weights[i]`` when its bit is 1, so row ``r`` lands
    on minus the sum of the weights its bits select.  The uniform ladder is
    the special case ``weights[i] == step * 2 ** (n - 1 - i)``, which is what
    makes row order and position order agree there; a general weighting
    breaks that, which is why callers must sort.
    """
    out = []
    for r in range(2**n):
        total = 0
        for i in range(n):
            if (r >> (n - 1 - i)) & 1:
                total += weights[i]
        out.append(-total)
    return out


def _fold_at(truth_table: str, n: int, weights: tuple[int, ...]) -> str | None:
    """Build a fold template on a given ladder, or ``None``.

    **The ladder is bounded by ``_LIMIT``, not ``2 * _LIMIT``.**  The plan
    state is relative -- :func:`_fold_moves` allows a *span* of ``2 * _LIMIT``
    because a state may sit anywhere in ``[-_LIMIT, _LIMIT]`` -- but the
    emitter lays the rows at absolute positions starting from a zero
    accumulator, so the ladder itself has to fit in ``[-_LIMIT, _LIMIT]``.
    Checking only the relative bound lets the planner spend thousands of moves on
    a geometry the emitter then refuses on its first op: the alternating
    table at eleven inputs plans 2833 ops on a 4094-wide uniform ladder and
    asserts immediately.

    **Rows are grouped by position, not by row index.**  On a uniform ladder
    the two orders agree, so the original code walked ``range(2**n)`` and
    coalesced neighbours; on a weighted ladder they do not, and grouping by
    index would build a state whose "runs" are not contiguous in the geometry
    the plan reasons about.  Sorting first makes the same construction work
    for both, and the uniform case is unchanged because sorting a ladder that
    is already ordered is the identity.
    """
    pos = _fold_positions(n, weights)
    # Two rows sharing a position are merged before the plan starts and can
    # never be separated again, so every ladder offered is a distinct-sum
    # one.  Asserted rather than guarded: a ladder that collides is a bug in
    # :func:`_fold_ladders`, not a table this construction declines.
    if len(set(pos)) != len(pos):
        raise AssertionError((n, weights))
    if max(abs(p) for p in pos) > _LIMIT:
        return None
    order = sorted(range(2**n), key=lambda r: -pos[r])
    runs: list[list[int]] = []
    for r in order:
        if runs and truth_table[runs[-1][-1]] == truth_table[r]:
            runs[-1].append(r)
        else:
            runs.append([r])
    state = [
        (
            pos[rn[0]],
            pos[rn[0]] - pos[rn[-1]],
            truth_table[rn[0]],
            frozenset(rn),
        )
        for rn in runs
    ]
    ops = _fold_plan(_fold_norm(state))
    if ops is None:
        return None
    emitter = _FoldEmitter(truth_table, n, weights)
    for idx, (kind, _, c, vids) in enumerate(ops):
        if kind == "m":
            emitter.double(next_is_rise=(idx + 1 < len(ops) and ops[idx + 1][0] == "u"))
        elif kind == "d":
            emitter.dive(c, vids)
        else:
            emitter.rise(c, vids)
    emitter.finish()
    header = ";".join(
        f"{k}={zero}|{one}" for k, (zero, one) in enumerate(_fold_setters(n, weights))
    )
    placeholders = "".join("{X" + str(k) + "}" for k in range(n))
    return header + _HEADER_END + placeholders + "".join(emitter.body)
