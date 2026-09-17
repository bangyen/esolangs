"""Boolean-function generator for Vandevelo.

The program reads the inputs, then hangs -- ``loop -> loop?`` evaluated
lazily never terminates -- exactly when the table entry is 1.  Every value
a Vandevelo program can bind is affine in the inputs (``==``/``!=`` are
XNOR/XOR over nil), and only ``::`` chains evaluate conditionally, so a
guard line hangs on an affine coset of inputs and a whole program hangs on
a union of cosets.  The generator therefore emits one guard line per coset
of an affine cover of the table's 1-set.

The cover is an affine-cube peel.  A cube is grown by iterated popular
differences: pick the direction ``v`` maximising ``|B & (B ^ v)|``,
intersect, repeat while a pair remains; the working sets along that chain
are exactly the places the partial cube fits, so the chain finds cubes of
dimension about ``log2(log2(T))`` that no local search sees.  The counting
behind the choice is Cohen--Shinkar's (ECCC TR14-099): while the remainder
has density ``eps``, the chain from the most popular direction reaches
dimension ``d(eps) = log2(n) - log2(log2(1/eps)) - 2``, so a peel that
only ever takes cubes of at least that dimension ends in ``1 + 9 * 2**n /
n`` clauses, and the guard parts across all clauses total ``O(2**n)``.

The peel does not restart per cube.  Every set it scores is kept and
updated as points leave: the root holds the pair set ``S(v) = B & (B ^
v)`` for a pool of :data:`_CANDIDATES` directions; below each pooled
direction hangs a node with its own candidates and a greedy sub-chain,
built on demand and kept while it has points.  Harvesting is deep-first
in phases: phase ``d`` takes every coset at the deepest level of whichever
chain is at least ``d`` deep, and drops to ``d - 1`` only when the chain
from the most popular root direction, brought up to date at every level,
falls short of ``d`` -- that chain has Cohen--Shinkar's dimension, so the
phase never drops below ``d(eps)`` while the density is ``eps``, which is
what the clause bound needs.  The pool is rechosen from the remainder's nearest existing
differences once a fixed fraction of it has gone; below density
``1 / max(_CANDIDATES, n)`` the remainder is sparse and each cube is grown
at its lowest point from that point's nearest differences instead.

Time is linear in the table by construction: a node costs its candidate
count times its size to build, and is either harvested entirely (charged
to its points, once per level) or dropped when a pool refresh retires
its direction (at most the pool's size of them per refresh); removing a
point updates the pool and every node holding it at the candidate count
each; a refresh follows a fixed fraction of removals, so the pool's cost
``T * ln(_CANDIDATES / 2)`` in all and a node's a constant per point it
loses; the sparse tail costs a constant per point.  Two terms sit
outside that: the proof's exact fallback -- when no scored direction
reaches the pigeonhole average on a dense working set, the most popular
one is found by autocorrelation, ``n * 2**n`` a call, none on random
dense tables to n=14 and one at n=15 -- and the dual-basis core below,
at most ``sqrt(2**(dim + 1))`` inputs, so under ``sqrt(n)`` per clause
at the peel's dimensions and 2% of the build at n=15.  The per-cube peel
this replaces rescanned the remainder for every cube, ``Theta(T**2 /
word)``; this one measures x1.7--2.3 per added input over n=10..15 at
0.93--1.02 of its size.  Dense random tables measure 8.4--9.5 characters
per entry at n=8..13.

A cube's guard needs one part per constraint, and any basis of the cube's
dual space will do.  :func:`_constraints` builds one from short relations:
all but at most ``1 + 2**((dim + 1) / 2)`` constraints are parities of at
most four inputs, the rest come from reduced elimination at most ``dim +
1`` wide, so a clause's constraints weigh at most ``4 * n + (dim + 1) * (1
+ 2**((dim + 1) / 2))`` inputs in total.  Single-input constraints test
the input name directly and wider ones live in strict register bindings
(``A ~> a?``, ``A ~> A? != b?``) that later clauses morph one toggle at a
time instead of respelling; a fresh register costs one line per input of
its parity and a morph strictly fewer, so upkeep never exceeds the total
constraint weight.  Summed over the peel, ``4 * n`` per clause is ``4 * n
+ 36 * 2**n`` by the clause bound, and the second term is at most ``4 *
2**dim`` per clause, hence ``4 * 2**n`` over the disjoint cubes.  Register
upkeep is therefore O(T) -- under ``40 * 2**n + 4 * n`` lines -- and its
measured share stays under half of the emitted text.  The bank holds at
most ``n**2`` registers (:func:`_bank_cap`), so a register name is never
longer than two input names and a full bank respells its least recently
used free register at the same cost as a fresh one; a clause looks for a
register to reuse or morph among the :data:`_SCAN` most recently used, so
the lookup is a constant per constraint.  The reduced-echelon basis alone
would not give the weight bound: on a cube whose columns spread over
``2**dim`` values it weighs ``n * dim / 2`` however the pivots are chosen,
which is ``Theta(T log log T)`` at the ``log2(n)`` dimensions the peel
produces.
"""

from __future__ import annotations

import heapq
from itertools import islice

from esolangs.tools.helpers import _validate_truth_table

__all__ = ["vandevelo"]


_ALPHABET = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMOPQRSTUVWXYZ0123456789_&*$"
_RESERVED = {"Inp", "Nil", "l", "loop"}

# Directions scored per node: the parent's best _INHERIT plus fresh nearest
# differences inside the node.  The peel is exact with any cap -- a missed
# direction only costs cover -- and the proof's fallback covers the dense
# regime.  48 is the per-cube scan's cap, kept so the covers compare.
_CANDIDATES = 48
_INHERIT = 24
# A node's candidates are rechosen once this fraction of its points has
# gone; the pool likewise.  Each refresh costs the node's size times the
# candidates replaced, so the charge per removed point is a constant.
_REFRESH = 0.25
# Registers examined when a clause looks for one to reuse or morph: the
# bank stays under this to n=13 (about 2**(n/2) live registers), so the
# cap costs nothing measured; a cap of 48 cost 5--8% there.
_SCAN = 3 * _CANDIDATES


def _bank_cap(n: int) -> int:
    """Live registers allowed for an ``n``-input table.

    Uncapped, the bank grows with the peel -- 7 registers at n=6 to 117 at
    n=13, about ``2**(n/2)`` -- and names for that many registers would put
    a factor of ``n`` on every reference.  ``n**2`` keeps a register name
    within twice an input name's length, always leaves a free register (a
    clause binds at most ``n - 1``), and never binds at measured sizes;
    ``n`` or ``2 * n`` would cost 40% and 23% at n=13 in forced respelling.
    """
    return n * n


def _name(index: int) -> str:
    """Return the ``index``th shortest non-reserved Vandevelo name."""
    base = len(_ALPHABET)
    value = index + 1
    chars = []
    while value:
        value, digit = divmod(value - 1, base)
        chars.append(_ALPHABET[digit])
    return "".join(reversed(chars))


def _points(mask: int) -> list[int]:
    """Set bit positions of ``mask``, ascending."""
    out = []
    while mask:
        low = mask & -mask
        out.append(low.bit_length() - 1)
        mask ^= low
    return out


def _nearest(
    points: set[int], pivot: int, seen: set[int], n: int, cap: int
) -> list[int]:
    """Return the ``cap`` nearest differences from ``pivot`` inside ``points``.

    Smallest by ``(bit_count, value)``, skipping ``seen``: the differences
    are walked in that order -- each weight's values ascending, by Gosper's
    next-permutation step -- testing membership, so a dense set yields its
    head after about ``cap / density`` probes.  When four times ``cap``
    probes have not filled the list the set is sparse and the whole of it
    is listed instead, at its size; the answer is the same either way.
    """
    limit = 1 << n
    out: list[int] = []
    probes = 0
    for weight in range(1, n + 1):
        v = (1 << weight) - 1
        while v < limit:
            probes += 1
            if probes > 4 * cap:
                break
            if (pivot ^ v) in points and v not in seen:
                out.append(v)
                if len(out) == cap:
                    return out
            low = v & -v
            ripple = v + low
            v = ripple | (((v ^ ripple) >> 2) // low)
        else:
            continue
        break
    if len(out) < cap:
        extra = heapq.nsmallest(
            cap - len(out),
            (
                (v.bit_count(), v)
                for v in (pivot ^ p for p in points)
                if v and v not in seen and v not in out
            ),
        )
        out.extend(v for _, v in extra)
    return out


def _popularities(points: set[int], n: int) -> list[int]:
    """``P[v] = |S & (S ^ v)|`` for every ``v``, one autocorrelation.

    Walsh--Hadamard transform of the indicator, squared pointwise, and
    transformed back: exact integers throughout, ``n * 2**n`` additions.
    """
    size = 1 << n
    vec = [1 if x in points else 0 for x in range(size)]
    span = 1
    while span < size:
        for start in range(0, size, span * 2):
            for i in range(start, start + span):
                low, high = vec[i], vec[i + span]
                vec[i], vec[i + span] = low + high, low - high
        span *= 2
    vec = [value * value for value in vec]
    span = 1
    while span < size:
        for start in range(0, size, span * 2):
            for i in range(start, start + span):
                low, high = vec[i], vec[i + span]
                vec[i], vec[i + span] = low + high, low - high
        span *= 2
    return [value >> n for value in vec]


class _Node:
    """A working set along a chain, with the pair sets of its candidates.

    ``points`` is ``S``; ``cands[v]`` is ``S & (S ^ v)`` for each scored
    direction ``v``; ``span`` is the subspace spanned by the chain's
    directions down to here; ``child`` is the greedy continuation, kept
    while it has points; ``removed`` counts points gone since the
    candidates were chosen.
    """

    __slots__ = ("cands", "child", "parent", "points", "removed", "span", "v")

    def __init__(
        self, v: int, points: set[int], span: set[int], parent: _Node | None
    ) -> None:
        self.v = v
        self.points = points
        self.cands: dict[int, set[int]] = {}
        self.span = span
        self.child: _Node | None = None
        self.parent = parent
        self.removed = 0


def _score(node: _Node, dirs: list[int]) -> None:
    """Add the pair set of each direction in ``dirs`` to the node."""
    pts = node.points
    for v in dirs:
        if v in node.span or v in node.cands:
            continue
        node.cands[v] = {p for p in pts if (p ^ v) in pts}


def _best(node: _Node) -> tuple[int | None, int]:
    """Return the candidate with the largest pair set, if any has a pair."""
    best_v, best_c = None, 1
    for v, c in node.cands.items():
        m = len(c)
        if m > best_c or (m == best_c and best_v is not None and v < best_v):
            best_v, best_c = v, m
    return best_v, best_c


def _ensure_popular(node: _Node, n: int) -> None:
    """Apply the proof's fallback: score the exact most popular direction.

    Only on a dense set (``|S| >= 2**n / n``) whose best scored direction
    misses the pigeonhole average ``|S|**2 / 2**n``, so that the chain
    takes a direction at least as popular as Cohen--Shinkar's telescoping
    needs.
    """
    size = len(node.points)
    total = 1 << n
    if size * n < total:
        return
    _, best_c = _best(node)
    if best_c * total >= size * size:
        return
    popular = _popularities(node.points, n)
    best_v = None
    for v in range(1, total):
        if popular[v] > best_c and v not in node.span and v not in node.cands:
            best_v, best_c = v, popular[v]
    if best_v is not None:
        _score(node, [best_v])


def _remove(node: _Node, p: int) -> None:
    """Take ``p`` out of the node, its pair sets, and its chain below."""
    if p not in node.points:
        return
    node.points.discard(p)
    node.removed += 1
    for w, c in node.cands.items():
        if p in c:
            c.discard(p)
            c.discard(p ^ w)
    child = node.child
    if child is not None:
        _remove(child, p)
        _remove(child, p ^ child.v)


def _grow(alive: set[int], pivot: int, cands: list[int]) -> tuple[list[int], list[int]]:
    """Grow a cube at ``pivot`` inside ``alive``: the sparse tail's rule.

    A candidate is viable while it is outside the cube's span and its
    copy of the cube lies inside ``alive``; each step keeps the viable
    direction that leaves the most others viable, a one-step lookahead
    that costs the candidate count squared per point of the cube.
    """
    dirs: list[int] = []
    cube = [pivot]
    inside = {pivot}
    viable = [v for v in cands if (pivot ^ v) in alive]
    while viable:
        best_v, best_s = viable[0], -1
        for v in viable:
            new = [p ^ v for p in cube]
            s = sum(1 for w in viable if w != v and all((p ^ w) in alive for p in new))
            if s > best_s:
                best_v, best_s = v, s
        new = [p ^ best_v for p in cube]
        cube += new
        inside.update(new)
        dirs.append(best_v)
        viable = [
            w
            for w in viable
            if w != best_v
            and (pivot ^ w) not in inside
            and all((p ^ w) in alive for p in new)
        ]
    return dirs, cube


class _Peel:
    """The phased deep-first peel over one table's 1-set."""

    def __init__(self, ones: set[int], n: int) -> None:
        self.n = n
        self.root = _Node(0, ones, {0}, None)
        self.nodes: dict[int, _Node] = {}  # pooled direction -> its node
        self.tried: set[int] = set()  # directions scored this phase
        self.cubes: list[tuple[int, list[int]]] = []
        self.since = 0  # points removed since the pool was refreshed
        _score(self.root, _nearest(ones, min(ones), {0}, n, _CANDIDATES))
        _ensure_popular(self.root, n)

    def make_child(self, parent: _Node, v: int) -> _Node:
        """Build the node for direction ``v`` below ``parent``.

        Its set is the parent's pair set for ``v``, scored on the parent's
        best ``_INHERIT`` directions plus fresh nearest differences inside
        it.
        """
        span = parent.span | {s ^ v for s in parent.span}
        child = _Node(v, set(parent.cands[v]), span, parent)
        pts = child.points
        ranked = sorted(parent.cands.items(), key=lambda kv: (-len(kv[1]), kv[0]))
        dirs = [w for w, _ in ranked if w != v][:_INHERIT]
        fresh = _nearest(
            pts, min(pts), set(dirs) | span, self.n, _CANDIDATES - len(dirs)
        )
        _score(child, dirs + fresh)
        _ensure_popular(child, self.n)
        return child

    def refresh(self, node: _Node) -> None:
        """Replace the node's pairless candidates with fresh nearest differences."""
        node.removed = 0
        for v in [v for v, c in node.cands.items() if len(c) < 2]:
            del node.cands[v]
            if node is self.root:
                self.nodes.pop(v, None)
                self.tried.discard(v)
        pts = node.points
        seen = set(node.cands) | node.span
        _score(
            node, _nearest(pts, min(pts), seen, self.n, _CANDIDATES - len(node.cands))
        )
        _ensure_popular(node, self.n)

    def extend(self, node: _Node) -> int:
        """Build the greedy chain below ``node`` as far as it goes; its depth."""
        depth = 0
        cur = node
        while True:
            if cur.child is not None and cur.child.points:
                cur = cur.child
                depth += 1
                continue
            cur.child = None
            if cur is not node and cur.removed >= _REFRESH * len(cur.points):
                self.refresh(cur)
            best_v, _ = _best(cur)
            if best_v is None:
                return depth
            cur.child = self.make_child(cur, best_v)
            cur = cur.child
            depth += 1

    def take(self, p: int) -> None:
        """Remove ``p`` from the remainder and every set holding it."""
        _remove(self.root, p)
        for node in self.nodes.values():
            pts = node.points
            if p in pts:
                _remove(node, p)
            if p ^ node.v in pts:
                _remove(node, p ^ node.v)
        self.since += 1

    def harvest(self, node: _Node) -> None:
        """Take every coset at the deepest level of the node's chain."""
        chain = [node]
        while chain[-1].child is not None and chain[-1].child.points:
            chain.append(chain[-1].child)
        leaf = chain[-1]
        dirs = [x.v for x in chain]
        span = sorted(leaf.span)
        for p in sorted(leaf.points):
            if p not in leaf.points:
                continue
            coset = [p ^ s for s in span]
            self.cubes.append((min(coset), list(dirs)))
            for q in coset:
                self.take(q)

    def certify(self) -> _Node | None:
        """Bring the chain the proof speaks for up to date and return it.

        From the most popular root direction, at each level the most
        popular candidate of the current set, with the exact fallback at
        each.  Levels whose direction is still the most popular are kept;
        the chain is rebuilt below the first that is not.
        """
        best_v, _ = _best(self.root)
        if best_v is None:
            return None
        # Every pooled direction with a pair has a node by now: the phase
        # scores each once, and a dropped node forgets it was scored.
        node = cur = self.nodes[best_v]
        while True:
            self.refresh(cur)
            best_w, _ = _best(cur)
            if best_w is None:
                cur.child = None
                return node
            child = cur.child
            if child is None or child.v != best_w or not child.points:
                child = cur.child = self.make_child(cur, best_w)
            cur = child

    def run(self) -> list[tuple[int, list[int]]]:
        """Peel the whole 1-set; returns ``(base, dirs)`` per cube."""
        root = self.root
        n = self.n
        sparse_at = (1 << n) // max(_CANDIDATES, n)
        depth_target = n + 1
        tried = self.tried
        pool: list[int] = []
        while root.points:
            if len(root.points) <= sparse_at:
                self.sparse(pool)
                continue
            if self.since >= _REFRESH * len(root.points):
                self.since = 0
                self.refresh(root)
            for v in [v for v, node in self.nodes.items() if not node.points]:
                del self.nodes[v]
                tried.discard(v)
            # 1. the deepest chain at least depth_target deep
            best: _Node | None = None
            best_key: tuple[int, int, int] | None = None
            for v, node in self.nodes.items():
                if node.removed >= _REFRESH * len(node.points):
                    self.refresh(node)
                depth = self.extend(node) + 1
                if depth >= depth_target:
                    key = (depth, len(node.points), -v)
                    if best_key is None or key > best_key:
                        best, best_key = node, key
            if best is not None:
                self.harvest(best)
                continue
            # 2. score one more pooled direction this phase -- the exact
            # most popular one first, if the pool has fallen below average
            _ensure_popular(root, n)
            pick = None
            for v, c in sorted(root.cands.items(), key=lambda kv: (-len(kv[1]), kv[0])):
                if len(c) < 2:
                    break
                if v not in self.nodes and v not in tried:
                    pick = v
                    break
            if pick is not None:
                tried.add(pick)
                self.nodes[pick] = self.make_child(root, pick)
                if depth_target > n:
                    depth_target = self.extend(self.nodes[pick]) + 1
                continue
            # 3. drop the phase, but only past a chain the proof speaks for
            proven = self.certify()
            if proven is not None and self.extend(proven) + 1 >= depth_target:
                self.harvest(proven)
                continue
            if depth_target > 1:
                depth_target -= 1
                tried.clear()
                continue
            p = min(root.points)
            self.cubes.append((p, []))
            self.take(p)
        return self.cubes

    def sparse(self, pool: list[int]) -> None:
        """One cube of the sparse tail, grown at the remainder's lowest point."""
        alive = self.root.points
        pivot = min(alive)
        cands = list(pool)
        cands += _nearest(alive, pivot, {0, *pool}, self.n, _CANDIDATES - len(cands))
        dirs, cube = _grow(alive, pivot, cands)
        self.cubes.append((pivot, dirs))
        for q in cube:
            alive.discard(q)
        # The last cubes' directions lead the next candidate list, so
        # consecutive clauses share constraints and the bank morphs.
        pool[:] = (dirs + [v for v in pool if v not in dirs])[:_INHERIT]


def _echelon(dirs: list[int], n: int) -> list[int]:
    """Reduced-echelon basis of the constraint space of ``span(dirs)``.

    Reduced elimination keeps each dual to one free coordinate plus bits on
    the ``len(dirs)`` pivots, so no vector is wider than ``dim + 1``.  Only
    the completion step of :func:`_constraints` needs it.
    """
    pivots: dict[int, int] = {}
    for row in dirs:
        cur = row
        for bit, prow in pivots.items():
            if cur >> bit & 1:
                cur ^= prow
        if not cur:  # pragma: no cover - the peel only keeps independent dirs
            # A dependent direction would reduce to zero and take the pivot
            # key to -1, quietly corrupting the dual basis and so the guard.
            raise AssertionError("dependent direction reached elimination")
        hi = cur.bit_length() - 1
        for bit in pivots:
            if pivots[bit] >> hi & 1:
                pivots[bit] ^= cur
        pivots[hi] = cur
    duals = []
    for free in (b for b in range(n) if b not in pivots):
        w = 1 << free
        for bit, prow in pivots.items():
            if prow >> free & 1:
                w ^= 1 << bit
        duals.append(w)
    return duals


def _constraints(base: int, dirs: list[int], n: int) -> list[tuple[int, int]]:
    """Dual constraints pinning ``base + span(dirs)``: ``(parity, value)``.

    A constraint is a set of inputs whose ``dirs``-columns (the vector of
    the set's bits across the directions) sum to zero, and any basis of
    those sets pins the cube.  This one is built from short relations:
    inputs are scanned in order and kept in a *core* while no one-to-four
    of the core's columns sum to zero; every other input's column is, by
    maximality, a sum of at most three core columns, giving it a relation
    of weight at most four that no other relation shares its bit with.
    The core's pairwise column sums are distinct and nonzero in
    ``2**dim - 1`` values, so it holds at most ``1 + 2**((dim + 1) / 2)``
    inputs, and the ``|core| - dim`` relations still missing come from
    the reduced-echelon basis, each at most ``dim + 1`` wide.

    A cube's constraints therefore weigh at most
    ``4 * n + (dim + 1) * (1 + 2**((dim + 1) / 2))`` in total, against
    ``(n - dim) * (dim + 1)`` for the echelon basis alone, which is what
    the module docstring's O(T) upkeep bound sums.
    """
    dim = len(dirs)
    cols = [sum((v >> j & 1) << i for i, v in enumerate(dirs)) for j in range(n)]
    # Sums of one to three core columns, mapped to the set of inputs summed.
    sums: dict[int, int] = {}
    core: list[int] = []
    duals: list[int] = []
    for j, col in enumerate(cols):
        if col == 0:
            duals.append(1 << j)
        elif col in sums:
            duals.append(sums[col] | 1 << j)
        else:
            singles = [(cols[c], 1 << c) for c in core]
            pairs = [(a ^ b, x | y) for a, x in singles for b, y in singles if x < y]
            for value, inputs in [(col, 1 << j)] + [
                (col ^ a, 1 << j | x) for a, x in singles + pairs
            ]:
                sums.setdefault(value, inputs)
            core.append(j)
    # A short relation's leading bit is its own input -- the core inputs it
    # sums are all earlier -- so the relations are independent as they
    # stand.  Complete to a basis from the echelon duals, keeping each only
    # when it is independent of what came before.
    reduced = {w.bit_length() - 1: w for w in duals}
    for w in _echelon(dirs, n):
        cur = w
        while cur and (cur.bit_length() - 1) in reduced:
            cur ^= reduced[cur.bit_length() - 1]
        if cur:
            reduced[cur.bit_length() - 1] = cur
            duals.append(w)
    if len(duals) != n - dim:  # pragma: no cover - a basis has n - dim rows
        raise AssertionError("constraint basis has the wrong rank")
    return [(w, (w & base).bit_count() % 2) for w in duals]


def vandevelo(truth_table: str, width: int | None = None) -> str:
    """Build a Vandevelo program computing ``truth_table`` by termination."""
    n = _validate_truth_table(truth_table)
    compact = width is not None
    names = [_name(index) for index in range(n)]
    lines = (
        [f"{names[index]}~>Inp?" for index in range(n)]
        if compact
        else [f"{names[index]} ~> Inp?" for index in range(n)]
    )
    lines.append("l->l?" if compact else "loop -> loop?")
    loop = "l?" if compact else "loop?"

    def ref(bit: int) -> str:
        # Index bit ``bit`` is the (n-1-bit)th input read: rows are spelled
        # most-significant-first, and the first read is the top bit.
        return names[n - 1 - bit]

    ones = {row for row, entry in enumerate(truth_table) if entry == "1"}
    cubes = _Peel(ones, n).run() if ones else []

    bank: dict[str, int] = {}
    next_register = n
    for base, dirs in cubes:
        parts = []
        used: set[str] = set()
        for w, value in _constraints(base, dirs, n):
            if w.bit_count() == 1:
                part = ref(w.bit_length() - 1)
            else:
                recent = list(islice(reversed(bank.items()), _SCAN))
                exact = next(
                    (r for r, held in recent if held == w and r not in used),
                    None,
                )
                if exact is not None:
                    register = exact
                    bank[register] = bank.pop(register)  # most recently used
                else:
                    nearest: str | None = None
                    distance = w.bit_count()
                    for r, held in recent:
                        if r in used:
                            continue
                        d = (held ^ w).bit_count()
                        if d < distance:
                            nearest, distance = r, d
                    if nearest is not None:
                        register = nearest
                        toggles = _points(bank.pop(register) ^ w)
                    elif len(bank) < _bank_cap(n):
                        register = _name(next_register)
                        next_register += 1
                        toggles = _points(w)
                    else:
                        # Bank full: respell the least recently used free
                        # register, which costs what a fresh one would.
                        register = next(r for r in bank if r not in used)
                        del bank[register]
                        toggles = _points(w)
                    if nearest is None:
                        first, toggles = ref(toggles[0]), toggles[1:]
                        lines.append(
                            f"{register}~>{first}?"
                            if compact
                            else f"{register} ~> {first}?"
                        )
                    for b in toggles:
                        lines.append(
                            f"{register}~>{register}?!={ref(b)}?"
                            if compact
                            else f"{register} ~> {register}? != {ref(b)}?"
                        )
                    bank[register] = w
                used.add(register)
                part = register
            if value:
                parts.append(f"{part}?")
            else:
                parts.append(f"{part}?==Nil?" if compact else f"{part}? == Nil?")
        lines.append(
            "::".join([*parts, loop]) if compact else " :: ".join([*parts, loop])
        )
    return "\n".join(lines)
