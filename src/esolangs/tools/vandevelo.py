"""Boolean-function generator for Vandevelo.

The program reads the inputs, then hangs -- ``loop -> loop?`` evaluated
lazily never terminates -- exactly when the table entry is 1.  Every value
a Vandevelo program can bind is affine in the inputs (``==``/``!=`` are
XNOR/XOR over nil), and only ``::`` chains evaluate conditionally, so a
guard line hangs on an affine coset of inputs and a whole program hangs on
a union of cosets.  The generator therefore emits one guard line per coset
of an affine cover of the table's 1-set. Affine tables, single cosets and their
complements bypass the peel after geometric doubling checks.

A test for 0 is ``x? == Nil?``, eight characters and four steps over a
bare ``x?``, so the guards are spelled to need it rarely.  A register
takes whichever polarity its clause wants -- its last toggle is ``==``
rather than ``!=`` -- and an input most of whose tests ask for 0 is read
negated (``~!>``) when the rows reaching those tests agree.  A guard's
bare tests run first, and a test every row reaching it passes -- the
far side of an earlier one-test guard -- is dropped.  Over the
three-input tables these take 30,476 steps to 22,669 and 26,438
characters to 23,425.

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
what the clause bound needs.  Every level of that chain, and of the
first chain, which sets the opening phase, passes :func:`_assure`, so its
direction holds at least half the average popularity: the quotient density
then obeys ``eps' >= eps**2 / 4``, so ``log2(1 / eps) + 2`` at most doubles
a level, and the chain reaches cubes of more than ``n / (2 * (log2(1 / eps)
+ 2))`` points.  Summing over the density bands ``(2**-(i+1), 2**-i]``
gives at most ``16 * 2**n / n`` dense clauses, and the sparse tail adds at
most ``2**n / n``, for every table.  The pool is rechosen from the
remainder's nearest existing differences once a fixed fraction of it has
gone; below density
``1 / max(_CANDIDATES, n)`` the remainder is sparse and each cube is grown
at its lowest point from that point's nearest differences instead,
filled from its successors in row order when the probes fall short.

The proposed linear-time charge covers candidate upkeep: a node costs its candidate
count times its size to build, and is either harvested entirely (charged
to its points, once per level) or dropped when a pool refresh retires
its direction (at most the pool's size of them per refresh); removing a
point updates the pool and every node holding it at the candidate count
each; a refresh follows a fixed fraction of removals, so the pool's cost
``T * ln(_CANDIDATES / 2)`` in all and a node's a constant per point it
loses; the sparse tail costs a constant per point -- its order is
threaded once in O(T), and a cube's probes, window and growth are
bounded by the candidate count.  The sampled fallback
fits the same charge: when no scored direction reaches the pigeonhole
average on a dense working set, it scores :data:`_SAMPLES` uniform pair
differences, ``_SAMPLES * |S|`` work, as many candidates more.  It is a
heuristic; :func:`_assure` carries the bound, and on measured tables it
never has to compute.  The per-cube peel this replaces rescanned the
remainder for every cube, ``Theta(T**2 / word)``; this one measures
x1.7--2.3 per added input over n=10..15 at 0.93--1.02 of its size.
Dense tables measure 7.3--8.7 characters per entry at n=8..11.

The charge fails on near-full tables.  "Once per level" assumes chains of
bounded depth.  With ``k`` zeros, level ``l`` of the first chain misses at
most ``k * 2**l`` points, so it keeps two cosets for ``n - log2(k) - 1``
levels, and building each visits all of ``|S|``: at least ``T * (n -
log2(k) - 2)`` work.  Three or eight zeros measure 845--1090 ``n * T`` of
scoring at n=10..15; random tables of density 0.1 to 0.9 stay flat at
13--4,500 ``T``.  The dual-basis core below is a second term outside the
charge, at most ``sqrt(2**(dim + 1))`` inputs a clause and 2% of the build
at n=15.

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
upkeep is therefore O(T) lines -- under ``40 * 2**n + 4 * n`` lines -- and its
measured share stays under half of the emitted text.  The bank holds at
most ``n**2`` registers (:func:`_bank_cap`), so a register name is never
longer than two input names and a full bank respells its least recently
used free register at the same cost as a fresh one; a clause looks for a
register to reuse or morph among the :data:`_SCAN` most recently used, so
the lookup is a constant per constraint.  The reduced-echelon basis alone
would not give the weight bound: on a cube whose columns spread over
``2**dim`` values it weighs ``n * dim / 2`` however the pivots are chosen,
which is ``Theta(T log log T)`` at the ``log2(n)`` dimensions the peel
produces. Identifier lengths are ``O(log n)``, so this argument bounds
characters by ``O(T log n)``, not ``O(T)``. Removing that factor is open.
"""

from __future__ import annotations

import heapq
import random
from itertools import islice

from esolangs.tools.helpers import _validate_truth_table, short_name

__all__ = ["vandevelo"]


_ALPHABET = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMOPQRSTUVWXYZ0123456789_&*$"
_RESERVED = {"Inp", "Nil", "l", "loop"}
_COMPLEMENT = str.maketrans("01", "10")

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
# Pair differences drawn when no candidate reaches half the pigeonhole
# average; each clears it with probability at least a half.
_SAMPLES = 8


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


def _points(mask: int) -> list[int]:
    """Set bit positions of ``mask``, ascending."""
    out = []
    while mask:
        low = mask & -mask
        out.append(low.bit_length() - 1)
        mask ^= low
    return out


def _nearest(
    points: set[int], pivot: int, seen: set[int], n: int, cap: int, *, scan: bool = True
) -> list[int]:
    """Return the ``cap`` nearest differences from ``pivot`` inside ``points``.

    Smallest by ``(bit_count, value)``, skipping ``seen``: the differences
    are walked in that order -- each weight's values ascending, by Gosper's
    next-permutation step -- testing membership, so a dense set yields its
    head after about ``cap / density`` probes.  When four times ``cap``
    probes have not filled the list the set is sparse and the whole of it
    is listed instead, at its size; the answer is the same either way.
    With ``scan`` off the probes' finds are returned as they stand.
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
    if scan and len(out) < cap:
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


class _Node:
    """A working set along a chain, with the pair sets of its candidates.

    ``points`` is ``S``; ``cands[v]`` is ``|S & (S ^ v)|`` for each scored
    direction ``v`` -- the pair *size*, not the pair set, because a removal
    only ever drops two entries from it and keeping the set cost two
    ``discard`` calls a direction a point.  ``span`` is the subspace spanned
    by the chain's directions down to here; ``child`` is the greedy
    continuation, kept while it has points; ``removed`` counts points gone
    since the candidates were chosen.
    """

    __slots__ = ("cands", "child", "parent", "points", "removed", "span", "v")

    def __init__(
        self, v: int, points: set[int], span: set[int], parent: _Node | None
    ) -> None:
        self.v = v
        self.points = points
        self.cands: dict[int, int] = {}
        self.span = span
        self.child: _Node | None = None
        self.parent = parent
        self.removed = 0


def _score(node: _Node, dirs: list[int]) -> None:
    """Add the pair size of each direction in ``dirs`` to the node."""
    pts = node.points
    for v in dirs:
        if v in node.span or v in node.cands:
            continue
        node.cands[v] = _pairs(pts, v)


def _pairs(pts: set[int], v: int) -> int:
    """Return ``|S & (S ^ v)|``."""
    count = 0
    for p in pts:
        if (p ^ v) in pts:
            count += 1
    return count


def _pairset(node: _Node, v: int) -> set[int]:
    """Return ``S & (S ^ v)``, recomputed only when a child is built."""
    pts = node.points
    return {p for p in pts if (p ^ v) in pts}


def _best(node: _Node) -> tuple[int | None, int]:
    """Return the candidate with the largest pair set, if any has a pair."""
    best_v, best_c = None, 1
    for v, c in node.cands.items():
        m = c
        if m > best_c or (m == best_c and best_v is not None and v < best_v):
            best_v, best_c = v, m
    return best_v, best_c


def _ensure_popular(node: _Node, n: int) -> None:
    """Apply the proof's fallback: score a sampled half-average direction.

    Only on a dense set (``|S| >= 2**n / n``) whose best scored direction
    misses half the pigeonhole average ``|S|**2 / 2**n``.  The difference
    ``a ^ b`` of a uniform pair is a direction drawn by popularity, and the
    directions under half the average hold under ``2**n * |S|**2 / 2**(n+1)``
    of the ``|S|**2`` pairs, so each draw clears half the average with
    probability at least a half.  :data:`_SAMPLES` draws cost what scoring
    that many candidates does; the first to clear joins the candidates.
    """
    size = len(node.points)
    total = 1 << n
    if size * n < total:
        return
    _, best_c = _best(node)
    if best_c * total >= size * size:
        return
    pts = list(node.points)
    # Seeded by the set, so the program is a function of the table.
    rng = random.Random(size)  # nosec B311
    best_v = None
    for _ in range(_SAMPLES):
        v = rng.choice(pts) ^ rng.choice(pts)
        if v in node.span or v in node.cands:
            continue
        count = _pairs(node.points, v)
        if count > best_c:
            best_v, best_c = v, count
    if best_v is not None:
        node.cands[best_v] = best_c


def _assure(node: _Node, n: int) -> None:
    """Make the node's best candidate reach half the pigeonhole average.

    The node's points are a union of ``q`` cosets of its span, of dimension
    ``j``, and the directions outside the span hold ``|S| * (|S| - 2**j)``
    of its ordered pairs.  When no candidate reaches half that over the
    ``2**n - 2**j`` such directions -- or none has a pair while ``q >= 2``
    -- the most popular one is computed exactly in the quotient and joins
    the candidates: by pair differences of the coset representatives, or by
    a Walsh--Hadamard transform when there are more pairs than the
    transform's ``m * 2**m`` steps (``m = n - j``).  Only the chains the
    clause bound speaks for call this, so it is a guarantee, not a search.
    """
    size = len(node.points)
    j = len(node.span).bit_length() - 1
    if size >> j < 2:
        return
    _, best_c = _best(node)
    if best_c > 1 and 2 * best_c * ((1 << n) - (1 << j)) >= size * (size - (1 << j)):
        return
    dirs = []
    cur: _Node | None = node
    while cur is not None and cur.parent is not None:
        dirs.append(cur.v)
        cur = cur.parent
    pivots: dict[int, int] = {}
    for row in dirs:
        for bit, prow in pivots.items():
            if row >> bit & 1:
                row ^= prow
        hi = row.bit_length() - 1
        for bit in pivots:
            if pivots[bit] >> hi & 1:
                pivots[bit] ^= row
        pivots[hi] = row
    free = [b for b in range(n) if b not in pivots]
    reps = set()
    for p in node.points:
        for bit, prow in pivots.items():
            if p >> bit & 1:
                p ^= prow
        reps.add(sum(1 << i for i, b in enumerate(free) if p >> b & 1))
    m = len(free)
    ordered = sorted(reps)
    if len(ordered) ** 2 <= m << m:
        pairs: dict[int, int] = {}
        for i, a in enumerate(ordered):
            for b in ordered[i + 1 :]:
                pairs[a ^ b] = pairs.get(a ^ b, 0) + 2
    else:
        # Autocorrelation of the indicator: square its transform, invert.
        f = [0] * (1 << m)
        for x in ordered:
            f[x] = 1
        f = _walsh([c * c for c in _walsh(f)])
        pairs = {u: c >> m for u, c in enumerate(f) if u}
    u, count = min(pairs.items(), key=lambda kv: (-kv[1], kv[0]))
    v = sum(1 << b for i, b in enumerate(free) if u >> i & 1)
    node.cands[v] = count << j


def _walsh(f: list[int]) -> list[int]:
    """Unnormalised Walsh--Hadamard transform, in place."""
    h = 1
    while h < len(f):
        for start in range(0, len(f), 2 * h):
            for k in range(start, start + h):
                f[k], f[k + h] = f[k] + f[k + h], f[k] - f[k + h]
        h *= 2
    return f


def _remove(node: _Node, p: int) -> None:
    """Take ``p`` out of the node, its pair sets, and its chain below."""
    if p not in node.points:
        return
    node.points.discard(p)
    node.removed += 1
    # ``cands[w]`` counts ``q`` with ``q`` and ``q ^ w`` both in the set;
    # dropping ``p`` removes the entries ``q = p`` and ``q = p ^ w`` -- two
    # exactly when ``p ^ w`` is still present, since neither counts alone.
    for w in node.cands:
        if (p ^ w) in node.points:
            node.cands[w] -= 2
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
        child = _Node(v, _pairset(parent, v), span, parent)
        pts = child.points
        ranked = sorted(parent.cands.items(), key=lambda kv: (-kv[1], kv[0]))
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
        for v in [v for v, c in node.cands.items() if c < 2]:
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

    def extend(self, node: _Node, *, certain: bool = False) -> int:
        """Build the greedy chain below ``node`` as far as it goes; its depth.

        A ``certain`` chain has :func:`_assure` at every level, so it is
        one the clause bound speaks for.
        """
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
            if certain:
                _assure(cur, self.n)
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
        popular candidate of the current set, with the sampled fallback at
        each.  Levels whose direction is still the most popular are kept;
        the chain is rebuilt below the first that is not.
        """
        _assure(self.root, self.n)
        best_v, _ = _best(self.root)
        if best_v is None:
            return None
        # Every pooled direction with a pair has a node by now: the phase
        # scores each once, and a dropped node forgets it was scored --
        # unless :func:`_assure` has just added it.
        if best_v not in self.nodes:
            self.tried.add(best_v)
            self.nodes[best_v] = self.make_child(self.root, best_v)
        node = cur = self.nodes[best_v]
        while True:
            self.refresh(cur)
            _assure(cur, self.n)
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
        while root.points:
            if len(root.points) <= sparse_at:
                self.sparse()
                break
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
            # 2. score one more pooled direction this phase -- a sampled
            # popular one first, if the pool has fallen below average
            _ensure_popular(root, n)
            if depth_target > n:
                _assure(root, n)
            pick = None
            for v, c in sorted(root.cands.items(), key=lambda kv: (-kv[1], kv[0])):
                if c < 2:
                    break
                if v not in self.nodes and v not in tried:
                    pick = v
                    break
            if pick is not None:
                tried.add(pick)
                self.nodes[pick] = self.make_child(root, pick)
                if depth_target > n:
                    depth_target = self.extend(self.nodes[pick], certain=True) + 1
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

    def sparse(self) -> None:
        """Peel the sparse tail, one cube at the remainder's lowest point.

        The remainder is threaded in ascending order once, by a walk over
        the rows, so the lowest point is the head and a removal unlinks in
        constant time.  When the nearest differences fall short of the
        candidate count -- a sparse set is where they do -- the pivot's
        next points in that order fill the list, instead of a scan of the
        whole remainder per cube.
        """
        alive = self.root.points
        # Point ``p`` is slot ``p + 1``; slot 0 heads the list.
        nxt = [0] * ((1 << self.n) + 2)
        prv = [0] * ((1 << self.n) + 2)
        last = 0
        for p in range(1 << self.n):
            if p in alive:
                nxt[last], prv[p + 1] = p + 1, last
                last = p + 1
        nxt[last] = 0
        pool: list[int] = []
        while nxt[0]:
            pivot = nxt[0] - 1
            cands = list(pool)
            seen = {0, *pool}
            cands += _nearest(
                alive, pivot, seen, self.n, _CANDIDATES - len(cands), scan=False
            )
            slot = nxt[pivot + 1]
            while slot and len(cands) < _CANDIDATES:
                v = pivot ^ (slot - 1)
                if v not in seen and v not in cands:
                    cands.append(v)
                slot = nxt[slot]
            dirs, cube = _grow(alive, pivot, cands)
            self.cubes.append((pivot, dirs))
            for q in cube:
                alive.discard(q)
                before, after = prv[q + 1], nxt[q + 1]
                nxt[before], prv[after] = after, before
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


def _affine_form(table: str, n: int) -> tuple[int, int] | None:
    """Return the XOR mask and constant, checking all rows in O(T) work."""
    first = table[0]
    mask = sum(1 << bit for bit in range(n) if table[1 << bit] != first)
    expected = first
    for bit in range(n):
        expected += expected.translate(_COMPLEMENT) if mask & (1 << bit) else expected
    return (mask, int(first)) if expected == table else None


def _affine_coset(table: str, ones: set[int]) -> tuple[int, list[int]] | None:
    """Return a basis for an affine 1-set, with O(T) membership work."""
    size = len(ones)
    if not size or size & (size - 1):
        return None
    base = min(ones)
    points = {base}
    dirs = []
    for row, entry in enumerate(table):
        if entry == "0" or row in points:
            continue
        direction = row ^ base
        extension = {point ^ direction for point in points}
        if len(points) * 2 > size or any(table[point] != "1" for point in extension):
            return None
        points.update(extension)
        dirs.append(direction)
    return base, dirs


def vandevelo(truth_table: str, width: int | None = None) -> str:
    """Build a Vandevelo program computing ``truth_table`` by termination."""
    n = _validate_truth_table(truth_table)
    compact = width is not None
    names = [short_name(index, _ALPHABET) for index in range(n)]
    affine = _affine_form(truth_table, n)
    if affine is None:
        ones = {row for row, entry in enumerate(truth_table) if entry == "1"}
        coset = _affine_coset(truth_table, ones)
        excluded = None
        if coset is None:
            zeros = set(range(1 << n)) - ones
            excluded = _affine_coset(truth_table.translate(_COMPLEMENT), zeros)
        if excluded is not None:
            equations = _constraints(*excluded, n)
            cover = [[(mask, value ^ 1)] for mask, value in equations]
            # The first failed equation partitions the complement, even
            # though earlier failures let its redundant prefix tests go.
            dims = [n - index - 1 for index in range(len(equations))]
        else:
            cubes = (
                [coset] if coset is not None else (_Peel(ones, n).run() if ones else [])
            )
            cover = _pruned([_constraints(base, dirs, n) for base, dirs in cubes])
            dims = [len(dirs) for _, dirs in cubes]
    else:
        mask, offset = affine
        if mask:
            cover, dims = [[(mask, offset ^ 1)]], [n - 1]
        elif offset:
            cover, dims = [[]], [n]
        else:
            cover, dims = [], []
    flips = _flips(cover, dims, n)
    lines = []
    for index in range(n):
        # A flipped input is read negated, so its ``== Nil`` tests go.
        arrow = "~!>" if flips >> (n - 1 - index) & 1 else "~>"
        lines.append(
            f"{names[index]}{arrow}Inp?" if compact else f"{names[index]} {arrow} Inp?"
        )
    lines.append("l->l?" if compact else "loop -> loop?")
    loop = "l?" if compact else "loop?"

    def ref(bit: int) -> str:
        # Index bit ``bit`` is the (n-1-bit)th input read: rows are spelled
        # most-significant-first, and the first read is the top bit.
        return names[n - 1 - bit]

    # A register holds its parity XOR its own polarity, and a clause that
    # (re)binds it sets that polarity -- a ``==`` toggle in place of ``!=``
    # -- so the test it makes is a bare ``r?``.
    bank: dict[str, tuple[int, int]] = {}
    next_register = n
    for constraints in cover:
        parts = []
        used: set[str] = set()
        for w, value in constraints:
            # The constraint over the reads as spelled, flipped inputs and all.
            value ^= (w & flips).bit_count() & 1
            if w.bit_count() == 1:
                part, polarity = ref(w.bit_length() - 1), 0
            else:
                recent = list(islice(reversed(bank.items()), _SCAN))
                exact = next(
                    (r for r, held in recent if held[0] == w and r not in used),
                    None,
                )
                if exact is not None:
                    register = exact
                    polarity = bank.pop(register)[1]
                    bank[register] = (w, polarity)  # most recently used
                else:
                    nearest: str | None = None
                    distance = w.bit_count()
                    for r, (held, _) in recent:
                        if r in used:
                            continue
                        d = (held ^ w).bit_count()
                        if d < distance:
                            nearest, distance = r, d
                    if nearest is not None:
                        register = nearest
                        held, polarity = bank.pop(register)
                        toggles = _points(held ^ w)
                    elif len(bank) < _bank_cap(n):
                        register = short_name(next_register, _ALPHABET)
                        next_register += 1
                        toggles, polarity = _points(w), 0
                    else:
                        # Bank full: respell the least recently used free
                        # register, which costs what a fresh one would.
                        register = next(r for r in bank if r not in used)
                        del bank[register]
                        toggles, polarity = _points(w), 0
                    if nearest is None:
                        first, toggles = ref(toggles[0]), toggles[1:]
                        lines.append(
                            f"{register}~>{first}?"
                            if compact
                            else f"{register} ~> {first}?"
                        )
                    # Every rebinding toggles at least once; the last toggle
                    # sets the polarity that makes this test pass on a 1.
                    for i, b in enumerate(toggles):
                        op = "!="
                        if i == len(toggles) - 1 and polarity == value:
                            op, polarity = "==", polarity ^ 1
                        lines.append(
                            f"{register}~>{register}?{op}{ref(b)}?"
                            if compact
                            else f"{register} ~> {register}? {op} {ref(b)}?"
                        )
                    bank[register] = (w, polarity)
                used.add(register)
                part = register
            # The test passes when the variable equals ``value ^ polarity``.
            if value ^ polarity:
                parts.append(f"{part}?")
            else:
                parts.append(f"{part}?==Nil?" if compact else f"{part}? == Nil?")
        # A bare test costs one step and a ``== Nil`` five, and each part
        # stops about half the rows still evaluating: cheap parts go first.
        parts.sort(key=lambda part: part.endswith("Nil?"))
        lines.append(
            "::".join([*parts, loop]) if compact else " :: ".join([*parts, loop])
        )
    return "\n".join(lines)


def _pruned(cover: list[list[tuple[int, int]]]) -> list[list[tuple[int, int]]]:
    """Drop the tests every row reaching their clause passes.

    A clause left with one test hangs every row that reaches it on that
    test's side, so every row reaching a later clause is on the other, and
    a later test of that side is spent text and steps.  A clause left with
    no test is ``loop?`` alone, which is right: every row reaching it is in
    its cube.
    """
    implied: set[tuple[int, int]] = set()
    out = []
    for constraints in cover:
        kept = [test for test in constraints if test not in implied]
        out.append(kept)
        if len(kept) == 1:
            w, value = kept[0]
            implied.add((w, value ^ 1))
    return out


def _flips(cover: list[list[tuple[int, int]]], dims: list[int], n: int) -> int:
    """Return the index bits whose input is read negated.

    An input is flipped when more of its single-input tests ask for 0 than
    for 1, counted both plainly (each sheds ``== Nil``, eight characters,
    for one ``!`` on the read) and weighted by the rows that reach the
    test's line (each sheds four steps per row).  The cubes are disjoint
    and a row in one hangs on its line, so a line is reached by every row
    outside the cubes before it.  Registers set their own polarity, so only
    the bare tests count.
    """
    count = [0] * n
    weight = [0] * n
    reach = 1 << n
    for constraints, dim in zip(cover, dims, strict=True):
        for w, value in constraints:
            if w.bit_count() == 1:
                bit = w.bit_length() - 1
                count[bit] += 1 if value else -1
                weight[bit] += reach if value else -reach
        reach -= 1 << dim
    return sum(1 << bit for bit in range(n) if count[bit] < 0 and weight[bit] < 0)
