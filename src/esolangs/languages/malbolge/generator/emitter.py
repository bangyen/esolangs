"""The code emitter of the Malbolge build.

The emitter writes into a ``code`` dict at a code pointer ``c`` while a data
pointer ``d`` tracks where execution will point: every instruction advances
both by one.  :class:`_Planner` knows the walked cells' values, so it steers
``d`` by the chain-valued scan-greedy rule (:class:`_ScanGreedy`), and it
tracks the accumulator and the walked cells' contents across the writes it
emits.
"""

from __future__ import annotations

from bisect import bisect_left

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


def _cycdist(a: int, b: int) -> int | None:
    """Return the steps along ``succ`` from ``a`` to ``b``, if one cycle."""
    if a not in _CYCLE or b not in _CYCLE:
        return None
    ca, ia = _CYCLE[a]
    cb, ib = _CYCLE[b]
    if ca != cb:
        return None
    return (ib - ia) % len(ca)


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
    evaluation are computed once per call and memoised here.
    """

    def __init__(
        self, mem: dict[int, int | None], target: int, *, ceiling: int
    ) -> None:
        self.mem = mem
        self.target = target
        self.ceiling = ceiling
        # One pass builds the jump table, the walk costs' inputs, the
        # candidate sources per step predicate (the first qualifying cell
        # at/after a position is a bisect, not a scan) and ``_free``, the
        # unwritten cells (mem == g) grouped by g value for the F3 hops.
        jump: list[int | None] = [None] * ceiling
        on_cycle = set(_CYCLE.get(target, ((), 0))[0])
        # Step predicates as bytearrays: the first qualifying cell
        # at/after a position is a C-speed ``bytes.find`` over the frozen
        # copy made at the end of this pass.
        self._unwritten = bytearray(ceiling)
        self._le = bytearray(ceiling)
        self._win32 = bytearray(ceiling)
        self._win94 = bytearray(ceiling)
        self._cycle_cells = bytearray(ceiling)
        self._over = bytearray(ceiling)
        self._free: list[list[int]] = [[] for _ in range(128)]
        get = mem.get
        unwritten = self._unwritten
        le, win32, win94 = self._le, self._win32, self._win94
        cycle_cells, over = self._cycle_cells, self._over
        free = self._free
        group_free = target <= 127  # only then can F3 / cycle-hops fire
        for q in range(ceiling):
            value = get(q)
            if value is None or value + 1 >= ceiling:
                continue
            landing = value + 1
            jump[q] = landing
            if value == _G_TAB[q]:
                unwritten[q] = 1
                if group_free:
                    free[value].append(q)
            if landing <= target:
                le[q] = 1
                if landing > target - 32:
                    win32[q] = 1
                if landing > target - 94:
                    win94[q] = 1
            else:
                over[q] = 1
            if landing in on_cycle:
                cycle_cells[q] = 1
        self.jump = jump
        self._predicates = (
            bytes(self._unwritten),
            bytes(self._win32),
            bytes(self._win94),
            bytes(self._cycle_cells),
            bytes(self._over),
        )
        # The walk cost from every position: forward if the target is
        # ahead, else up to the least a >= ceiling whose ceiling-branch
        # landing is at most the target (one a per target), branch, up.
        if target >= ceiling:
            self._walk_all = [target - pos for pos in range(ceiling)]
        else:
            a = ceiling
            while self._landing(a) > target:
                a += 1
            wrap = 1 + (target - self._landing(a))
            self._walk_all = [
                target - pos if pos <= target else (a - pos) + wrap
                for pos in range(ceiling)
            ]
        self._value: dict[int, int] = {}
        self._value_floor: dict[int, int] = {}
        self._chain_floor: dict[tuple[int, int], int] = {}
        self._u: dict[int, int] = {}
        self._cycle: dict[int, int | None] = {}
        self._second3: dict[int, int | None] = {}
        self._finish: list[int | None] = [None] * ceiling
        self._chain0: dict[int, int] = {}
        self._first_le: dict[int, int] = {}
        self._chain: dict[tuple[int, int], int] = {}
        self._f3: dict[int, int | None] = {}
        self._mark = [0] * ceiling
        self._stamp = 0
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

    # -- clause (b): cycle-follow -----------------------------------------
    def cycle_follow(self, pos: int) -> int | None:
        """Return the jump-self steps along the ``g``-cycle to the target.

        Valid only if ``pos`` and the target share a cycle and every cycle
        cell on the way still holds its ``g`` value (its jump lands on the
        next cycle element).
        """
        if pos not in self._cycle:
            dist = _cycdist(pos, self.target)
            result: int | None = None
            if dist is not None:
                x = pos
                for _ in range(dist):
                    if self.jump[x] != _SUCC[x]:
                        break
                    x = self.jump[x]  # type: ignore[assignment]
                else:
                    result = dist if x == self.target else None
            self._cycle[pos] = result
        return self._cycle[pos]

    # -- clause (c): one more jump within 3 cells, then walk --------------
    def second3(self, pos: int) -> int | None:
        """Return the least ``(q - pos + 1) + walk`` over jumps near ``pos``."""
        if pos not in self._second3:
            best: int | None = None
            for q in range(pos, min(pos + 3, self.ceiling - 1) + 1):
                landing = self.jump[q]
                if landing is None:
                    continue
                value = (q - pos + 1) + self._walk_all[landing]
                if best is None or value < best:
                    best = value
            self._second3[pos] = best
        return self._second3[pos]

    # -- clause (g)'s finish: least of walk, C0 chain, cycle-follow ---------
    def finish(self, pos: int) -> int:
        """Return the clause-(g) finish at ``pos``, memoised."""
        best = self._finish[pos]
        if best is None:
            best = self._walk_all[pos]
            best = min(best, self.chain0(pos))
            follow = self.cycle_follow(pos)
            if follow is not None:
                best = min(best, follow)
            self._finish[pos] = best
        return best

    # -- U, the Cscan4 step's depth-1 value --------------------------------
    def u_value(self, pos: int) -> int:
        """Return ``U(pos)``: least of walk, cycle-follow, second jump + walk."""
        if pos not in self._u:
            best = self._walk_all[pos]
            follow = self.cycle_follow(pos)
            if follow is not None and follow < best:
                best = follow
            second = self.second3(pos)
            if second is not None and second < best:
                best = second
            self._u[pos] = best
        return self._u[pos]

    # -- the C0 chain and the Cle chain (clause (d), standalone forms) -----
    def chain0(self, pos0: int) -> int:
        """Return the jump-self chain's value from ``pos0`` (cost cap 20)."""
        if pos0 not in self._chain0:
            jump, walk_all, mark = self.jump, self._walk_all, self._mark
            self._stamp += 1
            stamp = self._stamp
            best = walk_all[pos0]
            pos, cost = pos0, 0
            while (
                mark[pos] != stamp
                and jump[pos] is not None
                and cost < 20
                and cost < best
            ):
                mark[pos] = stamp
                pos = jump[pos]  # type: ignore[assignment]
                cost += 1
                value = cost + walk_all[pos]
                if value < best:
                    best = value
            self._chain0[pos0] = best
        return self._chain0[pos0]

    def first_le(self, pos0: int) -> int:
        """Return the ``Cle`` chain's value from ``pos0`` (cost cap 30).

        Each step jumps from the first cell at/after the current whose
        landing is at most the target.
        """
        if pos0 not in self._first_le:
            jump, walk_all, mark = self.jump, self._walk_all, self._mark
            le = bytes(self._le)
            self._stamp += 1
            stamp = self._stamp
            best = walk_all[pos0]
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
            self._first_le[pos0] = best
        return self._first_le[pos0]

    # -- clause (e): an F3 hop ----------------------------------------------
    def f3(self, pos: int) -> int | None:
        """Return an F3 hop's cost from ``pos``, or ``None``.

        The first unwritten cell at/after ``pos`` with ``g = target - 1``;
        its jump lands exactly on the target.
        """
        if pos not in self._f3:
            want = self.target - 1
            result: int | None = None
            if 33 <= want <= 126:
                cells = self._free[want]
                i = bisect_left(cells, pos)
                if i < len(cells):
                    result = (cells[i] - pos) + 1
            self._f3[pos] = result
        return self._f3[pos]

    # -- clause (f): cycle-hops ----------------------------------------------
    def cycle_hop(self, pos: int, k: int) -> int | None:
        """Return the cycle-hop ``k`` cost from ``pos``, or ``None``.

        An F3-style hop landing on the cycle element ``k`` steps before
        the target, then jump-self steps along the cycle (each must land
        exactly on the next cycle element), then walk.
        """
        hop = self._hops[k - 1]
        if hop is None:
            return None
        cells, rest = hop
        i = bisect_left(cells, pos)
        if i == len(cells):
            return None
        return (cells[i] - pos) + 1 + rest

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
        walk_all, mark = self._walk_all, self._mark
        best = cap
        for index in range(12):
            self._stamp += 1
            stamp = self._stamp
            chain_best = walk_all[landing]
            pos, cost = landing, 0
            while (
                mark[pos] != stamp and cost < 64 and cost < best and cost < chain_best
            ):
                mark[pos] = stamp
                nxt = self._chain_step(index, pos)
                if nxt is None:
                    break
                step, pos = nxt
                cost += step
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
        for q in range(pos, min(pos + 4, self.ceiling - 1) + 1):
            landing = self.jump[q]
            if landing is None:
                continue
            score = (q - pos + 1) + self.u_value(landing)
            if pick is None or score < pick[0]:
                pick = (score, q, landing)
        return None if pick is None else (pick[1] - pos + 1, pick[2])

    def _chain_step(self, index: int, pos: int) -> tuple[int, int] | None:
        """Return chain ``index``'s step from ``pos`` as ``(cost, landing)``."""
        jump = self.jump
        top = self.ceiling - 1
        if index == 0:  # C0: jump from the current cell
            landing = jump[pos]
            return None if landing is None else (1, landing)
        if index <= 3:  # Coffk: jump from current + k
            landing = jump[pos + index] if pos + index <= top else None
            return None if landing is None else (index + 1, landing)
        if index <= 8:  # Cunwr, Cwin32, Cwin94, Ccyc, Cover: first qualifying
            q = self._predicates[index - 4].find(_ONE, pos)
            landing = jump[q] if q >= 0 else None
            return None if landing is None else (q - pos + 1, landing)
        if index == 9:  # Cback: first landing before the current cell
            for q in range(pos, self.ceiling):
                landing = jump[q]
                if landing is not None and landing < pos:
                    return (q - pos + 1, landing)
            return None
        if index == 10:  # Cskip: first usable of current, +1, +2
            for q in (pos, pos + 1, pos + 2):
                landing = jump[q] if q <= top else None
                if landing is not None:
                    return (q - pos + 1, landing)
            return None
        return self._scan4_step(pos)  # Cscan4

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
        if landing in self._value:
            return min(self._value[landing], cap)
        if self._value_floor.get(landing, 0) >= cap:
            return cap
        best = min(cap, self._walk_all[landing])  # (a)
        for term in (
            self.cycle_follow(landing),  # (b)
            self.second3(landing),  # (c)
            self.chain0(landing),  # (d), C0's standalone form
            self.first_le(landing),  # (d), Cle's standalone form
            self.f3(landing),  # (e)
        ):
            if term is not None and term < best:
                best = term
        finish = self._finish
        for q in range(landing, min(landing + 21, self.ceiling - 1) + 1):  # (g)
            landing2 = self.jump[q]
            if landing2 is not None:
                fin = finish[landing2]
                if fin is None:
                    fin = self.finish(landing2)
                term = (q - landing + 1) + fin
                if term < best:
                    best = term
        for k in range(1, 6):  # (f)
            term = self.cycle_hop(landing, k)
            if term is not None and term < best:
                best = term
        if best:
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

    def raw(self, op: str) -> None:
        cell = self.d
        super().raw(op)
        if op in "p*":
            self.mem[cell] = self._written(op, cell)
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
        nav = _ScanGreedy(self.mem, target, ceiling=self.ceiling)
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
                    landing = nav.jump[q]
                    if landing is None or landing == pos:
                        continue
                    step = q - pos + 1
                    if step >= best_score:
                        break
                    score = step + nav.value(landing, best_score - step)
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
