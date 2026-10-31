"""The code emitter of the Malbolge build.

The emitter writes into a ``code`` dict at a code pointer ``c`` while a data
pointer ``d`` tracks where execution will point: every instruction advances
both by one.  :class:`_Planner` knows the walked cells' values, so it steers
``d`` by the chain-valued scan-greedy rule (:class:`_ScanGreedy`), and it
tracks the accumulator and the walked cells' contents across the writes it
emits.
"""

from __future__ import annotations

from bisect import bisect_left, insort

from esolangs.languages.malbolge.interpreter import _crazy

from .isa import _ACTIVE, _char_for, _g, _rot


def _valid_chars(address: int) -> list[int]:
    return [_char_for(op, address) for op in _ACTIVE]


#: The ``g``-cycle successor on the pointer region: ``succ(x) = g(x) + 1``.
_SUCC = {x: _g(x) + 1 for x in range(34, 128)}
#: Each pointer-region cell's ``g``-cycle and its index on it.  A function
#: of ``g`` alone, so it is built once for every build.
_CYCLE: dict[int, tuple[tuple[int, ...], int]] = {}
for _x in range(34, 128):
    if _x not in _CYCLE:
        _cyc, _y = [], _x
        while _y not in _CYCLE and _y not in _cyc:
            _cyc.append(_y)
            _y = _SUCC[_y]
        for _i, _v in enumerate(_cyc):
            _CYCLE[_v] = (tuple(_cyc), _i)
#: The ceiling-branch landing ``min(_valid_chars(a)) + 1`` per address ``a``
#: at or above the ceiling, as the walk cost prices it (such addresses are
#: never in a build's data); filled lazily, a function of the address alone.
_WRAP_LANDING: dict[int, int] = {}
#: An evaluation cap no real cost reaches, standing in for infinity.
_INF = 1 << 30
#: ``_g`` over the walked region, tabulated once (it has period 94).
_G_TAB = tuple(_g(a) for a in range(1024))
#: The set byte in a step-predicate bytearray, for ``bytes.find``.
_ONE = b"\x01"
#: The walk-cost list per ``(target, ceiling)``: a pure function of the
#: two, shared by every navigation over any memory with that target.
_WALK_ALL: dict[tuple[int, int], list[int]] = {}
#: The ``g``-cycle distance to a target per position on its cycle: a
#: pure function of the target, shared likewise (read-only).
_TARGET_DIST: dict[int, dict[int, int]] = {}
#: Navigations by (target, ceiling, jump table).  A navigation's every
#: input is a function of those three -- the walk costs and cycle data
#: of the target, and tables all derived from the jump landings (a
#: cell's value is its landing minus one, so the unwritten/free tables
#: are determined too) -- and most writes a planner makes leave the
#: jump table unchanged, so one navigation serves many gotos, across
#: builds as well as within one.  Its memoised evaluations are pure
#: functions of the key, so sharing them changes no decision.
_NAV_CACHE: dict[tuple[int, int, bytes, tuple[tuple[int, int], ...]], _ScanGreedy] = {}
#: The step-predicate translation tables per target: byte ``v`` (a jump
#: landing, 1..255) maps to 1 when a cell landing on ``v`` satisfies the
#: predicate for that target, in ``_ScanGreedy``'s order (le, win32,
#: win94, cycle, over).  Pure functions of the target, shared likewise.
_PRED_TABLES: dict[int, tuple[bytes, bytes, bytes, bytes, bytes]] = {}


def _pred_tables(target: int) -> tuple[bytes, bytes, bytes, bytes, bytes]:
    """Return ``target``'s predicate translation tables, cached."""
    tables = _PRED_TABLES.get(target)
    if tables is None:
        cycle = set(_CYCLE.get(target, ((), 0))[0])
        tables = (
            bytes(1 if 1 <= v <= target else 0 for v in range(256)),
            bytes(1 if 1 <= v <= target and v > target - 32 else 0 for v in range(256)),
            bytes(1 if 1 <= v <= target and v > target - 94 else 0 for v in range(256)),
            bytes(1 if v in cycle else 0 for v in range(256)),
            bytes(1 if v > target else 0 for v in range(256)),
        )
        if len(_PRED_TABLES) > 4096:
            _PRED_TABLES.clear()
        _PRED_TABLES[target] = tables
    return tables


class _MemTables:
    """The target-independent navigation tables over a planner's ``mem``.

    ``jump`` is the landing per cell (``None`` when the cell's jump is
    unusable); ``jb`` holds the landings as bytes (0 where unusable, and
    for the few landings at or above 256, which live in ``big`` instead);
    ``unwritten`` marks cells still holding their ``g`` value; ``free``
    groups those cells by ``g`` value, sorted; ``jump_qs`` is the sorted
    list of usable jump cells.  A planner builds its tables once and
    re-derives the one changed cell on each write it makes to ``mem``,
    so a ``goto`` never rescans the memory.
    """

    def __init__(self, mem: dict[int, int | None], ceiling: int) -> None:
        self.ceiling = ceiling
        jump: list[int | None] = [None] * ceiling
        jb = bytearray(ceiling)
        big: dict[int, int] = {}
        unwritten = bytearray(ceiling)
        free: list[list[int]] = [[] for _ in range(128)]
        jump_qs: list[int] = []
        for q, value in mem.items():
            if value is None or not 0 <= q < ceiling or value + 1 >= ceiling:
                continue
            landing = value + 1
            jump[q] = landing
            jump_qs.append(q)
            if landing <= 255:
                jb[q] = landing
            else:
                big[q] = landing
            if value == _G_TAB[q]:
                unwritten[q] = 1
                free[value].append(q)
        jump_qs.sort()
        for cells in free:
            if len(cells) > 1:
                cells.sort()
        self.jump = jump
        self.jb = jb
        self.big = big
        self.unwritten = unwritten
        self.free = free
        self.jump_qs = jump_qs

    def key(self) -> tuple[bytes, tuple[tuple[int, int], ...]]:
        """Return the jump table as a hashable snapshot.

        ``jb`` holds every landing below 256 and ``big`` the rest, so
        the pair determines the jump table exactly.
        """
        return bytes(self.jb), tuple(sorted(self.big.items()))

    def update(self, cell: int, value: int | None) -> None:
        """Re-derive ``cell``'s entries after ``mem[cell]`` became ``value``."""
        ceiling = self.ceiling
        if not 0 <= cell < ceiling:
            return
        jump = self.jump
        old = jump[cell]
        new = None if value is None or value + 1 >= ceiling else value + 1
        if old != new:
            jump[cell] = new
            if new is None:
                self.jb[cell] = 0
                self.big.pop(cell, None)
                del self.jump_qs[bisect_left(self.jump_qs, cell)]
            elif old is None:
                insort(self.jump_qs, cell)
                if new <= 255:
                    self.jb[cell] = new
                else:
                    self.big[cell] = new
            elif new <= 255:
                self.jb[cell] = new
                self.big.pop(cell, None)
            else:
                self.jb[cell] = 0
                self.big[cell] = new
        is_unwritten = value is not None and value == _G_TAB[cell]
        if bool(self.unwritten[cell]) != is_unwritten:
            self.unwritten[cell] = 1 if is_unwritten else 0
            cells = self.free[_G_TAB[cell]]
            if is_unwritten:
                insort(cells, cell)
            else:
                del cells[bisect_left(cells, cell)]


class _Emitter:
    """A code dict under construction, at code pointer ``c``, data pointer ``d``."""

    def __init__(self, start: int, d: int, code: dict[int, str] | None = None) -> None:
        self.code: dict[int, str] = {} if code is None else code
        self.c = start
        self.d = d

    def raw(self, op: str) -> None:
        """Emit ``op`` at the code pointer; both pointers advance by one."""
        self.code[self.c] = op
        self.c += 1
        self.d += 1


class _ScanGreedy:
    """One ``goto``'s chain-valued scan-greedy navigation state.

    The rule (docs/limitations.md, "Searches kept"): from the current position
    ``p``, scan the cells ``q`` in ``[p, p + 32]`` whose jump landing
    ``L = mem[q] + 1`` is usable; price each by ``(q - p + 1) + V(L)`` and
    jump via the cheapest (ties to the smallest ``q``) when that beats the
    forward-walk cost ``W`` from ``p``; otherwise walk to the target.
    Repeat at most 16 jumps, never jumping from a position twice.

    ``V(L)``, a landing's value, is the minimum of: (a) the walk cost from
    ``L``; (b) cycle-follow along ``L``'s ``g``-cycle; (c) one more jump
    within 3 cells, then walk; (d) the deterministic chains ``C0``,
    ``Coff1``, ``Coff2``, ``Coff3``, ``Cunwr``, ``Cwin32``, ``Cwin94``,
    ``Cle``, ``Ccyc``, ``Cover``, ``Cback``, ``Cskip`` and ``Cscan4``
    started at ``L`` (a chain's value is the least over its visited
    positions ``y`` of elapsed + walk cost from ``y``); (e) an F3 hop from
    ``L``; (f) cycle-hops ``k = 1..5`` from ``L``; (g) one more jump within
    21 cells finished by the least of walk, the ``C0`` chain and
    cycle-follow.  ``Cscan4``'s step jumps from the cell in
    ``[current, current + 4]`` minimising ``(q - current + 1) + U`` of its
    landing (ties to the smallest ``q``), where ``U(z)`` is the least of
    the walk cost from ``z``, cycle-follow from ``z`` and one more jump
    within 3 cells of ``z`` then walk.

    ``mem`` does not change during a ``goto``, so the jump table, the walk
    costs, the step-predicate candidate lists and every chain/value
    evaluation are computed once per call and memoised here.  The
    target-independent tables are the planner's :class:`_MemTables`,
    shared across its gotos and updated on each of its writes; the walk
    costs and cycle distances are pure functions of the target, cached
    across calls.
    """

    def __init__(
        self,
        mem: dict[int, int | None],
        target: int,
        *,
        ceiling: int,
        tables: _MemTables | None = None,
    ) -> None:
        self.mem = mem
        self.target = target
        self.ceiling = ceiling
        if tables is None:
            tables = _MemTables(mem, ceiling)
        # The target-independent tables are the planner's own, kept
        # current across its writes; nothing writes ``mem`` during a
        # ``goto``, so they are this call's snapshot as they stand.
        # The lists themselves are copied: a navigation is cached by
        # its jump table (see ``_Planner.goto``), so it must not see
        # the planner's later writes through shared lists.
        self.jump = jump = list(tables.jump)
        self._jump_qs = list(tables.jump_qs)
        self._free = [list(cells) for cells in tables.free]
        # The step predicates for this target are a ``translate`` of
        # the landing bytes by the target's cached tables (the first
        # qualifying cell at/after a position is then a C-speed
        # ``bytes.find``), with the few landings at or above 256 --
        # which the byte form cannot hold -- set exactly afterwards.
        le_t, win32_t, win94_t, cycle_t, over_t = _pred_tables(target)
        jb = tables.jb
        le = bytearray(jb).translate(le_t)
        win32 = bytearray(jb).translate(win32_t)
        win94 = bytearray(jb).translate(win94_t)
        cycle_cells = bytearray(jb).translate(cycle_t)
        over = bytearray(jb).translate(over_t)
        if tables.big:
            on_cycle = set(_CYCLE.get(target, ((), 0))[0])
            for q, landing in tables.big.items():
                le[q] = 1 if landing <= target else 0
                win32[q] = 1 if landing <= target and landing > target - 32 else 0
                win94[q] = 1 if landing <= target and landing > target - 94 else 0
                cycle_cells[q] = 1 if landing in on_cycle else 0
                over[q] = 1 if landing > target else 0
        self._le_pred = le
        self._predicates = (
            bytes(tables.unwritten),
            win32,
            win94,
            cycle_cells,
            over,
        )
        # The walk cost from every position: forward if the target is
        # ahead, else up to the least a >= ceiling whose ceiling-branch
        # landing is at most the target (one a per target), branch, up.
        # A pure function of (target, ceiling), so it is shared.
        walk_key = (target, ceiling)
        walk_all = _WALK_ALL.get(walk_key)
        if walk_all is None:
            if target >= ceiling:
                walk_all = [target - pos for pos in range(ceiling)]
            else:
                a = ceiling
                while self._landing(a) > target:
                    a += 1
                wrap = 1 + (target - self._landing(a))
                walk_all = [
                    target - pos if pos <= target else (a - pos) + wrap
                    for pos in range(ceiling)
                ]
            if len(_WALK_ALL) > 4096:
                _WALK_ALL.clear()
            _WALK_ALL[walk_key] = walk_all
        self._walk_all = walk_all
        # The target's cycle distances, shared likewise.
        target_dist = _TARGET_DIST.get(target)
        if target_dist is None:
            target_dist = {}
            if target in _CYCLE:
                cycle, index = _CYCLE[target]
                target_dist = {
                    cell: (index - i) % len(cycle) for i, cell in enumerate(cycle)
                }
            if len(_TARGET_DIST) > 4096:
                _TARGET_DIST.clear()
            _TARGET_DIST[target] = target_dist
        self._target_dist = target_dist
        # The per-landing memos, as ceiling-sized tables: -1 stands for
        # "not computed" where a result is never negative, and -2 where
        # -1 itself encodes a computed ``None``.
        self._value: list[int] = [-1] * ceiling
        self._value_floor: list[int] = [0] * ceiling
        self._u: list[int] = [-1] * ceiling
        self._u_floor: list[int] = [0] * ceiling
        self._cycle: list[int] = [-2] * ceiling
        self._second3: list[int] = [-2] * ceiling
        self._finish: list[int | None] = [None] * ceiling
        self._finish_floor: list[int] = [0] * ceiling
        self._chain0: list[int] = [-1] * ceiling
        self._chain0_floor: list[int] = [0] * ceiling
        self._first_le: list[int] = [-1] * ceiling
        self._first_le_floor: list[int] = [0] * ceiling
        self._f3: list[int] = [-2] * ceiling
        # Cycle-follow for every cell on the target's cycle, in one
        # backward pass: a cell follows iff its jump lands on the next
        # cycle cell and that cell follows (the target itself is 0).
        if target in _CYCLE:
            cycle, index = _CYCLE[target]
            cyc_tab = self._cycle
            cyc_tab[target] = 0
            for d in range(1, len(cycle)):
                cell = cycle[(index - d) % len(cycle)]
                succ = cycle[(index - d + 1) % len(cycle)]
                cyc_tab[cell] = d if cyc_tab[succ] >= 0 and jump[cell] == succ else -1
        self._mark = [0] * ceiling
        self._stamp = 0
        # The chain steps, memoised per (chain, position): a step is a
        # pure function of the position within this call.
        # -2 uncomputed, -1 undefined.  Allocated on first use.
        self._step_next: list[int] | None = None
        self._step_cost: list[int] | None = None
        walk_all = self._walk_all
        # Cycle-hops: per k, the hop cell's g value and the cost from its
        # landing on (cycle steps, then walk), which the position only
        # shifts by the walk to the hop cell.
        self._hops: list[tuple[list[int], int] | None] = []
        for k in range(1, 6):
            hop: tuple[list[int], int] | None = None
            if target in _CYCLE:
                cycle, index = _CYCLE[target]
                pred = cycle[(index - k) % len(cycle)]
                want = pred - 1
                if 33 <= want <= 126:
                    cost, cur = 0, pred
                    while cost < k and cur != target and jump[cur] == _SUCC[cur]:
                        cur = jump[cur]  # type: ignore[assignment]
                        cost += 1
                    hop = (self._free[want], cost + walk_all[cur])
            self._hops.append(hop)

    @staticmethod
    def _landing(a: int) -> int:
        if a not in _WRAP_LANDING:
            _WRAP_LANDING[a] = min(_valid_chars(a)) + 1
        return _WRAP_LANDING[a]

    # -- the walk cost (statement clause 1's W, and clause (a)) ----------
    def walk(self, pos: int) -> int:
        """Return the forward-walk cost from ``pos`` to the target."""
        return self._walk_all[pos]

    def exact(self, landing: int) -> int:
        """Return the memoised exact ``V(landing)``, or -1 if uncomputed."""
        return self._value[landing]

    # -- clause (b): cycle-follow -----------------------------------------
    def cycle_follow(self, pos: int, cap: int = _INF) -> int | None:
        """Return the jump-self steps along the ``g``-cycle to the target.

        Valid only if ``pos`` and the target share a cycle and every cycle
        cell on the way still holds its ``g`` value (its jump lands on the
        next cycle element).  Cells on the target's cycle are resolved in
        ``__init__``; with a finite ``cap`` the validation of any other
        cell stops at ``cap`` steps and returns ``cap`` -- callers only
        ever take a minimum against ``cap``, so the distinction between
        "at least ``cap``" and "invalid" is invisible to them, and the
        capped result is not memoised.
        """
        result = self._cycle[pos]
        if result == -2:
            result = -1
            dist = self._target_dist.get(pos)
            if dist is not None:
                x = pos
                for steps in range(dist):
                    if steps >= cap:
                        return cap
                    if self.jump[x] != _SUCC[x]:
                        break
                    x = self.jump[x]  # type: ignore[assignment]
                else:
                    if x == self.target:
                        result = dist
            self._cycle[pos] = result
        return None if result < 0 else result

    # -- clause (c): one more jump within 3 cells, then walk --------------
    def second3(self, pos: int) -> int | None:
        """Return the least ``(q - pos + 1) + walk`` over jumps near ``pos``."""
        best = self._second3[pos]
        if best == -2:
            best = -1
            jump, walk_all = self.jump, self._walk_all
            for q in range(pos, min(pos + 3, self.ceiling - 1) + 1):
                landing = jump[q]
                if landing is None:
                    continue
                value = (q - pos + 1) + walk_all[landing]
                if best < 0 or value < best:
                    best = value
            self._second3[pos] = best
        return None if best < 0 else best

    # -- clause (g)'s finish: least of walk, C0 chain, cycle-follow ---------
    def finish(self, pos: int, cap: int = _INF) -> int:
        """Return ``min(the clause-(g) finish at ``pos``, cap)``, memoised.

        A result below its cap is exact and memoised, as is a floor when
        the cap cuts the evaluation short (the same discipline as
        :meth:`value`).
        """
        exact = self._finish[pos]
        if exact is not None:
            return min(exact, cap)
        if self._finish_floor[pos] >= cap:
            return cap
        best = min(cap, self._walk_all[pos])
        best = min(best, self.chain0(pos, best))
        follow = self.cycle_follow(pos, best)
        if follow is not None and follow < best:
            best = follow
        if best < cap:
            self._finish[pos] = best
        else:
            self._finish_floor[pos] = cap
        return best

    # -- the C0 chain and the Cle chain (clause (d), standalone forms) -----
    def chain0(self, pos0: int, cap: int = _INF) -> int:
        """Return ``min(the jump-self chain's value from ``pos0``, cap)``.

        The chain's own cost cap is 20.  A result below ``cap`` is exact
        and memoised, as is a floor when ``cap`` cuts the walk short.
        """
        exact = self._chain0[pos0]
        if exact >= 0:
            return min(exact, cap)
        if self._chain0_floor[pos0] >= cap:
            return cap
        jump, walk_all, mark = self.jump, self._walk_all, self._mark
        self._stamp += 1
        stamp = self._stamp
        best = min(cap, walk_all[pos0])
        pos, cost = pos0, 0
        while (
            mark[pos] != stamp and jump[pos] is not None and cost < 20 and cost < best
        ):
            mark[pos] = stamp
            pos = jump[pos]  # type: ignore[assignment]
            cost += 1
            value = cost + walk_all[pos]
            if value < best:
                best = value
        if best < cap:
            self._chain0[pos0] = best
        else:
            self._chain0_floor[pos0] = cap
        return best

    def first_le(self, pos0: int, cap: int = _INF) -> int:
        """Return ``min(the ``Cle`` chain's value from ``pos0``, cap)``.

        Each step jumps from the first cell at/after the current whose
        landing is at most the target; the chain's own cost cap is 30.
        A result below ``cap`` is exact and memoised, as is a floor when
        ``cap`` cuts the walk short.
        """
        exact = self._first_le[pos0]
        if exact >= 0:
            return min(exact, cap)
        if self._first_le_floor[pos0] >= cap:
            return cap
        jump, walk_all, mark = self.jump, self._walk_all, self._mark
        le = self._le_pred
        self._stamp += 1
        stamp = self._stamp
        best = min(cap, walk_all[pos0])
        pos, cost = pos0, 0
        while mark[pos] != stamp and cost < 30 and cost < best:
            mark[pos] = stamp
            found = le.find(_ONE, pos)
            if found < 0:
                break
            cost += (found - pos) + 1
            pos = jump[found]  # type: ignore[assignment]
            value = cost + walk_all[pos]
            if value < best:
                best = value
        if best < cap:
            self._first_le[pos0] = best
        else:
            self._first_le_floor[pos0] = cap
        return best

    # -- clause (e): an F3 hop ----------------------------------------------
    def f3(self, pos: int) -> int | None:
        """Return an F3 hop's cost from ``pos``, or ``None``.

        The first unwritten cell at/after ``pos`` with ``g = target - 1``;
        its jump lands exactly on the target.
        """
        result = self._f3[pos]
        if result == -2:
            result = -1
            want = self.target - 1
            if 33 <= want <= 126:
                cells = self._free[want]
                i = bisect_left(cells, pos)
                if i < len(cells):
                    result = (cells[i] - pos) + 1
            self._f3[pos] = result
        return None if result < 0 else result

    def _chains_value(self, landing: int, cap: int) -> int:
        """Return ``min(cap, *the clause-(d) chain values at ``landing``)``.

        Each chain is walked from ``landing`` (least over its visited
        positions ``y`` of elapsed + walk cost from ``y``; cost cap 64;
        stops when its step is undefined or a position repeats).  A walk
        also stops once its elapsed cost reaches the smaller of ``cap``
        and its own best prefix: every later prefix costs at least the
        elapsed cost, so none can fall below either -- the minimum the
        caller needs is unchanged.  The chains, in order: ``C0`` jump
        from the current cell; ``Coff1``/``Coff2``/``Coff3`` from
        current + k; ``Cunwr`` from the first unwritten cell at/after
        current; ``Cwin32``/``Cwin94`` from the first cell whose landing
        lies in (target - 32, target] / (target - 94, target]; ``Ccyc``
        from the first cell whose landing lies on target's ``g``-cycle;
        ``Cover`` from the first cell whose landing is > target;
        ``Cback`` from the first cell whose landing is < current;
        ``Cskip`` from the first of current, current+1, current+2 with
        a usable jump; ``Cscan4`` from the cell in
        [current, current + 4] minimising (q - current + 1) + U of its
        landing, ties to the smallest q.
        """
        walk_all, mark, jump = self._walk_all, self._mark, self.jump
        predicates = self._predicates
        jump_qs = self._jump_qs
        step_next, step_cost = self._step_next, self._step_cost
        if step_next is None or step_cost is None:
            step_next = [-2] * (12 * self.ceiling)
            step_cost = [0] * (12 * self.ceiling)
            self._step_next, self._step_cost = step_next, step_cost
        ceiling = self.ceiling
        top = ceiling - 1
        best = cap
        for index in range(12):
            self._stamp += 1
            stamp = self._stamp
            chain_best = walk_all[landing]
            pos, cost = landing, 0
            base = index * ceiling
            while (
                mark[pos] != stamp and cost < 64 and cost < best and cost < chain_best
            ):
                mark[pos] = stamp
                # Chain ``index``'s step from ``pos`` (the rules are in
                # this method's docstring): a step is a pure function
                # of the position within this call, so each is computed
                # once and memoised in ``_step_next``/``_step_cost``;
                # ``nxt`` stays ``None`` when the step is undefined.
                ni = base + pos
                memo = step_next[ni]
                if memo >= 0:
                    step, nxt = step_cost[ni], memo
                elif memo == -1:
                    break
                else:
                    step, nxt = 0, None
                    if index == 0:  # C0: jump from the current cell
                        nxt = jump[pos]
                        step = 1
                    elif index <= 3:  # Coffk: jump from current + k
                        src = pos + index
                        nxt = jump[src] if src <= top else None
                        step = index + 1
                    elif index <= 8:  # first qualifying cell at/after current
                        q = predicates[index - 4].find(_ONE, pos)
                        nxt = jump[q] if q >= 0 else None
                        step = q - pos + 1
                    elif index == 9:  # Cback: first landing before current
                        i = bisect_left(jump_qs, pos)
                        while i < len(jump_qs):
                            q = jump_qs[i]
                            cand = jump[q]
                            if cand is not None and cand < pos:
                                step, nxt = q - pos + 1, cand
                                break
                            i += 1
                    elif index == 10:  # Cskip: first usable of current..+2
                        for q in (pos, pos + 1, pos + 2):
                            cand = jump[q] if q <= top else None
                            if cand is not None:
                                step, nxt = q - pos + 1, cand
                                break
                    else:  # Cscan4
                        scanned = self._scan4_step(pos)
                        if scanned is not None:
                            step, nxt = scanned
                    step_next[ni] = -1 if nxt is None else nxt
                    step_cost[ni] = step
                if nxt is None:
                    break
                cost += step
                pos = nxt
                value = cost + walk_all[pos]
                if value < chain_best:
                    chain_best = value
            if chain_best < best:
                best = chain_best
                if not best:
                    break
        return best

    def _scan4_step(self, pos: int) -> tuple[int, int] | None:
        """Return ``Cscan4``'s step from ``pos``.

        The cell in ``[pos, pos + 4]`` minimising ``(q - pos + 1) + U``
        of its landing, ties to the smallest ``q``.
        """
        pick: tuple[int, int, int] | None = None
        jump, u_tab, walk_all = self.jump, self._u, self._walk_all
        u_floor = self._u_floor
        for q in range(pos, min(pos + 4, self.ceiling - 1) + 1):
            landing = jump[q]
            if landing is None:
                continue
            step = q - pos + 1
            if pick is not None and step >= pick[0]:
                break  # the score only grows with q from here
            # ``U(landing)``: least of walk, cycle-follow and one more
            # jump within 3 cells then walk.  Only its value below the
            # incumbent score can matter, so it is evaluated with that
            # as its cap (exact below the cap, a floor at it).
            cap = _INF if pick is None else pick[0] - step
            u = u_tab[landing]
            if u >= 0:
                if u > cap:
                    u = cap
            elif u_floor[landing] >= cap:
                u = cap
            else:
                u = min(cap, walk_all[landing])
                follow = self.cycle_follow(landing, u)
                if follow is not None and follow < u:
                    u = follow
                second = self.second3(landing)
                if second is not None and second < u:
                    u = second
                if u < cap:
                    u_tab[landing] = u
                else:
                    u_floor[landing] = cap
            score = step + u
            if pick is None or score < pick[0]:
                pick = (score, q, landing)
        return None if pick is None else (pick[1] - pos + 1, pick[2])

    # -- V, a landing's value --------------------------------------------------
    def value(self, landing: int, cap: int = _INF) -> int:
        """Return ``min(V(landing), cap)``: ``V`` is clauses (a)..(g)'s least.

        With the default cap this is ``V`` exactly.  A finite ``cap`` --
        the outer scan passes the score a candidate must beat -- lets
        the chain walks stop as soon as they cannot fall below it, which
        changes nothing the caller can observe; a result that lands
        below its cap is exact and memoised, as is a floor when the cap
        cuts the evaluation short.
        """
        exact = self._value[landing]
        if exact >= 0:
            return min(exact, cap)
        if self._value_floor[landing] >= cap:
            return cap
        # Each term is evaluated against the running ``best`` as its
        # cap: a term's capped value is its exact value whenever that
        # value could lower ``best``, and a value no caller can
        # distinguish from it otherwise.  The terms' order is free
        # (the result is their minimum), so the cheap hops (f) run
        # before the (g) scan to tighten the caps it passes on.
        best = min(cap, self._walk_all[landing])  # (a)
        follow = self.cycle_follow(landing, best)  # (b)
        if follow is not None and follow < best:
            best = follow
        second = self.second3(landing)  # (c)
        if second is not None and second < best:
            best = second
        best = min(best, self.chain0(landing, best))  # (d), C0 standalone
        best = min(best, self.first_le(landing, best))  # (d), Cle standalone
        hop3 = self.f3(landing)  # (e)
        if hop3 is not None and hop3 < best:
            best = hop3
        for hop in self._hops:  # (f), the cycle-hops k = 1..5
            if hop is not None:
                cells, rest = hop
                i = bisect_left(cells, landing)
                if i < len(cells):
                    term = (cells[i] - landing) + 1 + rest
                    if term < best:
                        best = term
        if best > 1:  # (g): every term is a step (>= 1) plus a finish (>= 0)
            finish = self._finish
            jump = self.jump
            for q in range(landing, min(landing + 21, self.ceiling - 1) + 1):
                landing2 = jump[q]
                if landing2 is not None:
                    step = q - landing + 1
                    if step >= best:
                        break
                    fin = finish[landing2]
                    if fin is None:
                        fin = self.finish(landing2, best - step)
                    term = step + fin
                    if term < best:
                        best = term
                        if best <= 1:
                            break
        if best > 1:  # a chain value below 1 would need walk == 0 above
            best = self._chains_value(landing, best)  # (d), the named chains
        if best < cap:
            # No term was cut short above ``best`` (each chain's skipped
            # prefixes cost at least the cap it was given, which is at
            # least ``best``), so ``best`` is ``V`` exactly.
            self._value[landing] = best
        else:
            self._value_floor[landing] = cap
        return best


class _Planner(_Emitter):
    """Emitter steering ``d`` by the chain-valued scan-greedy rule.

    ``mem`` maps walked addresses to their known values (``None`` once
    written to an unknown value); ``a`` is the accumulator ``A`` when the ops
    so far have determined it, else ``None``; ``data`` maps store addresses
    above the code to source characters, which a ``j`` from there reads to
    come back below the walked region.  Knowing ``mem``/``a`` is only an
    optimisation: a cell whose value is still known stays usable as a ``j``
    target, so the rule sees the shortcuts the run-time pointers provide.
    No path may step to ``ceiling`` or beyond.
    """

    def __init__(
        self,
        start: int,
        d: int,
        mem: dict[int, int | None],
        data: dict[int, int],
        *,
        ceiling: int,
        a: int | None = None,
    ) -> None:
        super().__init__(start, d)
        self.mem = mem
        self.data = data
        self.ceiling = ceiling
        self.a = a
        self._tables = _MemTables(mem, ceiling)

    def raw(self, op: str) -> None:
        cell = self.d
        super().raw(op)
        if op in "p*":
            value = self._written(op, cell)
            self.mem[cell] = value
            self._tables.update(cell, value)
        elif op == "/":
            self.a = None

    def _written(self, op: str, cell: int) -> int | None:
        """Return the new value of ``cell`` after ``op``, or ``None`` if unknown."""
        old = self.mem.get(cell)
        if op == "*":
            if isinstance(old, int):
                self.a = _rot(old)
            else:
                self.a = None
        elif isinstance(old, int) and isinstance(self.a, int):
            self.a = _crazy(self.a, old)
        else:
            self.a = None
        return self.a

    def _emit(self, op: str) -> None:
        """Write ``op`` at the code pointer (``d`` is set when ``goto`` ends)."""
        self.code[self.c] = op
        self.c += 1

    def _walk_to(self, pos: int, target: int) -> int:
        """Emit the forward walk from ``pos`` to ``target``; return ``target``."""
        while pos != target:
            if pos >= self.ceiling:
                char = self.data.setdefault(pos, min(_valid_chars(pos)))
                self.raw("j")
                self.d = char + 1
                pos = char + 1
            elif pos < target:
                for _ in range(target - pos):
                    self._emit("o")
                pos = target
            else:
                a = self.ceiling
                while self.data.get(a, min(_valid_chars(a))) + 1 > target:
                    a += 1
                for _ in range(a - pos):
                    self._emit("o")
                pos = a
        return pos

    def goto(self, target: int) -> None:
        """Steer ``d`` to ``target`` by the chain-valued scan-greedy rule.

        Fixed prefix: from ``d >= ceiling``, one ``j`` through the data
        cell there.  Then repeat (at most 16 jumps; a position is never
        jumped from twice -- on a repeat, or if no jump qualifies, finish
        by walking): scan ``q`` in ``[p, p + 32]`` with a usable jump
        landing ``L != p``, price ``(q - p + 1) + V(L)`` with
        :class:`_ScanGreedy`'s ``V``, ties to the smallest ``q``; jump via
        the cheapest when it beats the walk cost from ``p``, else walk.
        """
        if self.d >= self.ceiling:
            char = self.data.setdefault(self.d, min(_valid_chars(self.d)))
            self.raw("j")
            self.d = char + 1
        if self.d == target:
            return
        jb_key, big_key = self._tables.key()
        key = (target, self.ceiling, jb_key, big_key)
        nav = _NAV_CACHE.get(key)
        if nav is None:
            nav = _ScanGreedy(
                self.mem, target, ceiling=self.ceiling, tables=self._tables
            )
            if len(_NAV_CACHE) >= 512:
                _NAV_CACHE.clear()
            _NAV_CACHE[key] = nav
        jump = nav.jump
        pos, jumps, seen = self.d, 0, set()
        while pos != target:
            # Walking is always available at ``best_score``; a candidate
            # only matters with a strictly smaller score (a tie walks, as
            # does a tie between candidates, which keeps the smallest q),
            # so every value evaluation is capped at what it must beat.
            best_score = nav.walk(pos)
            best: tuple[int, int] | None = None
            if pos not in seen and jumps <= 16:
                seen.add(pos)
                for q in range(pos, min(pos + 32, self.ceiling - 1) + 1):
                    landing = jump[q]
                    if landing is None or landing == pos:
                        continue
                    step = q - pos + 1
                    if step >= best_score:
                        break
                    cap = best_score - step
                    exact = nav.exact(landing)
                    if exact >= 0:
                        # ``value``'s memoised-exact fast path.
                        score = step + (exact if exact < cap else cap)
                    else:
                        score = step + nav.value(landing, cap)
                    if score < best_score:
                        best_score, best = score, (q, landing)
            if best is not None:
                q, landing = best
                for _ in range(q - pos):
                    self._emit("o")
                self._emit("j")
                pos = landing
                jumps += 1
            else:
                pos = self._walk_to(pos, target)
        self.d = target

    def op(self, op: str, target: int) -> None:
        """Steer ``d`` to ``target`` and emit ``op`` there."""
        self.goto(target)
        self.raw(op)

    def hub(self, pointer: int, value: int) -> None:
        """``j`` through ``pointer`` (holding ``value``) to ``value + 1``."""
        self.goto(pointer)
        self.raw("j")
        self.d = value + 1
