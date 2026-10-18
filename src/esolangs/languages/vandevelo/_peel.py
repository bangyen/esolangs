"""The affine-cube peel behind the Vandevelo cover.

:class:`_Peel` covers a 1-set with affine cubes grown by iterated popular
differences; :class:`_Node` holds one coset representative per level.

A cube is grown by iterated popular
differences: pick ``v`` maximising ``|B & (B ^ v)|``, intersect, repeat
while a pair remains; the chain finds cubes of dimension about
``log2(log2(T))`` that no local search sees.  Cohen--Shinkar (ECCC
TR14-099): at remainder density ``eps`` the chain from the most popular
direction reaches ``d(eps) = log2(n) - log2(log2(1/eps)) - 2``, so a peel
taking only cubes of at least that dimension ends in ``1 + 9 * 2**n / n``
clauses.

Against the sparse tail's lowest-point growth alone the peel saves 9.7% of
characters at n=8 (200 tables), 13.2% at n=10 and 20.8% at n=12.

An ignored input is a free direction of every cube, so the cover already
drops it: projecting first is 0.4% larger, pooled over 22 tables at n=8-9.  Guards
are cosets of the 1-set, so there is no subtree to share.

The peel does not restart per cube.  Every scored pair set ``S(v) = B & (B ^
v)`` is kept and updated as points leave: the root pools :data:`_CANDIDATES`
directions, each with a node of its own candidates and greedy sub-chain,
built on demand.  Harvesting is deep-first in phases: phase ``d`` takes
every coset at the deepest level of any chain at least ``d`` deep, and
drops only when the up-to-date chain from the most popular root direction
falls short, so it never drops below ``d(eps)``.  That chain and the first
pass :func:`_assure` at every level (direction holds at least half the
average popularity), so ``eps' >= eps**2 / 4`` and cubes exceed ``n / (2 *
(log2(1 / eps) + 2))`` points; summed over density bands that is at most
``16 * 2**n / n`` dense clauses plus ``2**n / n`` sparse, for every table.
The pool is rechosen from the remainder's nearest existing differences once
a fixed fraction has gone; below density ``1 / max(_CANDIDATES, n)`` each
cube is grown at its lowest point from that point's nearest differences,
filled from its successors in row order when probes fall short.

Nodes hold cosets, not points: a node ``l`` levels down stores one
representative per coset of its ``l``-dimensional span (:class:`_Node`), so
building, scoring, removal and refresh passes visit its coset
count ``q``, which at least halves a level.  Removal charges to cosets
built.  Refresh in both :meth:`_Peel.extend` and :meth:`_Peel.certify` waits
until removals reach a quarter of the current size: scanning ``q``
representatives then charges at most four visits per removed coset.
The exact :func:`_assure` fallback sorts representatives, so its cost
is ``O(q log q)`` per call, before charging repeated certification.
Through five inputs :func:`_ensure_popular` scores every direction first;
it is a size rule, not part of the bound.  The sparse tail costs a constant
per point.

Linear time is not proved, and cannot be before linear output.  Four build
terms escape the charge: a child rebuilt after it empties scans its
parent's ``q`` cosets (bounded by ``q**2`` a node, likewise the repeated
assurance and child replacement in :meth:`_Peel.certify`); cosets built cost
``O(T * n)`` a chain; halving
would need both halves of each child coset to leave together, and
rebuilding in :meth:`_Peel.extend` only after three quarters is lost
costs 2.5% over a 433-table corpus; :func:`_nearest`'s sparse fallback
lists points.  The dual-basis core queries pair sums in ``O(n * |core|)``
a clause; ``|core| <= 1 + sqrt(2 * 2**dim)`` and the cubes partition the
1-set, so Cauchy--Schwarz with ``C <= 17 * T / n`` bounds the sum by
``O(T * sqrt(n))``; its linear charge remains open.  Measured element
visits per entry are flat at n=10..14 -- three or eight zeros
2,700--3,800 (17,000--28,000 and rising when nodes held points), density
0.9 2,400--2,700, dense 500--900, quadratic forms 110--120.
"""

from __future__ import annotations

import heapq

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


def _points(mask: int) -> list[int]:
    """Set bit positions of ``mask``, ascending."""
    out = []
    while mask:
        low = mask & -mask
        out.append(low.bit_length() - 1)
        mask ^= low
    return out


def _nearest(
    node: _Node, pivot: int, seen: set[int], n: int, cap: int, *, scan: bool = True
) -> list[int]:
    """Return the ``cap`` nearest differences from canonical ``pivot`` inside ``node``.

    Smallest by ``(bit_count, value)``, skipping ``seen`` and the node's
    span: differences are walked in that order (each weight's values
    ascending, by Gosper's step), testing membership, so a dense set yields
    its head after about ``cap / density`` probes.  After ``4 * cap`` probes
    without filling the list the set is sparse and is listed whole, at its
    size; the answer is the same either way.  This is the one step on a node
    that costs points, not cosets: listing only the representatives'
    differences costs cosets but moves emitted size by up to 4% a table,
    either sign, at n=8..12.  With ``scan`` off the probes' finds are
    returned as they stand.
    """
    reps = node.reps
    reduce = node.reduce
    limit = 1 << n
    out: list[int] = []
    probes = 0
    for weight in range(1, n + 1):
        v = (1 << weight) - 1
        while v < limit:
            probes += 1
            if probes > 4 * cap:
                break
            cv = reduce(v)
            if cv and (pivot ^ cv) in reps and v not in seen:
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
        found = set(out)
        span = node.span()
        # Canonical pivot/r give reduce(pivot ^ r ^ s) == pivot ^ r.
        extra = heapq.nsmallest(
            cap - len(out),
            (
                (v.bit_count(), v)
                for v in (pivot ^ r ^ s for r in reps if r != pivot for s in span)
                if v not in seen and v not in found
            ),
        )
        out.extend(v for _, v in extra)
    return out


class _Node:
    """A working set along a chain, held as its cosets, with candidate scores.

    The set ``S`` is a union of cosets of the subspace spanned by the
    chain's directions down to here; ``reps`` holds one representative per
    coset, the one zero on every pivot of the reduced basis ``pivots``
    (``{leading bit: row}``), which is also the coset's least point.  Work
    on a node is its coset count, not its size, and the count at least
    halves a level.  ``cands[v]`` is ``|S & (S ^ v)|`` in points for each
    scored direction ``v`` and ``canon[v]`` its reduction; ``cv`` is the
    node's own direction reduced by its parent's basis and ``hi`` that
    reduction's leading bit; ``child`` is the greedy continuation, kept
    while it has points; ``removed`` counts points gone since the
    candidates were chosen.
    """

    __slots__ = (
        "cands",
        "canon",
        "child",
        "cv",
        "dim",
        "hi",
        "pivots",
        "removed",
        "reps",
        "v",
    )

    def __init__(
        self,
        v: int,
        cv: int,
        reps: set[int],
        pivots: dict[int, int],
    ) -> None:
        self.v = v
        self.cv = cv
        self.hi = cv.bit_length() - 1
        self.reps = reps
        self.pivots = pivots
        self.dim = len(pivots)
        self.cands: dict[int, int] = {}
        self.canon: dict[int, int] = {}
        self.child: _Node | None = None
        self.removed = 0

    @classmethod
    def root(cls, points: set[int]) -> _Node:
        """Return a chain's top, where every point is its own coset."""
        return cls(0, 0, points, {})

    @property
    def size(self) -> int:
        """``|S|`` in points."""
        return len(self.reps) << self.dim

    def span(self) -> list[int]:
        """Every element of the span, in ``2**dim`` work."""
        out = [0]
        for row in self.pivots.values():
            out += [s ^ row for s in out]
        return out

    def reduce(self, x: int) -> int:
        """Return the representative of ``x``'s coset: zero on every pivot."""
        for bit, row in self.pivots.items():
            if x >> bit & 1:
                x ^= row
        return x

    def below(self, v: int) -> _Node:
        """Return the node for ``S & (S ^ v)``, in work linear in ``reps``."""
        cv = self.reduce(v)
        hi = cv.bit_length() - 1
        pivots = {b: r ^ cv if r >> hi & 1 else r for b, r in self.pivots.items()}
        pivots[hi] = cv
        reps = self.reps
        pairs = {r ^ cv if r >> hi & 1 else r for r in reps if r ^ cv in reps}
        return _Node(v, cv, pairs, pivots)


def _score(node: _Node, dirs: list[int]) -> None:
    """Add the pair size of each direction in ``dirs`` to the node."""
    for v in dirs:
        if v in node.cands:
            continue
        cv = node.reduce(v)
        if cv:
            node.canon[v] = cv
            node.cands[v] = _pairs(node, cv)


def _pairs(node: _Node, cv: int) -> int:
    """Return ``|S & (S ^ v)|`` in points, for ``v`` reduced to ``cv``."""
    reps = node.reps
    return sum((r ^ cv) in reps for r in reps) << node.dim


def _best(node: _Node) -> tuple[int | None, int]:
    """Return the candidate with the largest pair set, if any has a pair."""
    best_v, best_c = None, 1
    for v, c in node.cands.items():
        if c > best_c or (c == best_c and best_v is not None and v < best_v):
            best_v, best_c = v, c
    return best_v, best_c


def _ensure_popular(node: _Node, n: int) -> None:
    """Score every direction when a small dense set's candidates fall short.

    Only for ``2**n <= 32``, on a dense set (``|S| >= 2**n / n``) whose best
    scored direction misses the pigeonhole average ``|S|**2 / 2**n``: the
    most popular of all ``2**n - 1`` directions, ties to the smallest, joins
    the candidates.  At most 31 directions a call, so a constant.  Without it
    12 of 256 three-input tables grow, by up to 46 characters (63%); with it
    no three-input table is larger than under the seeded 8-draw sampling it
    replaced, and four inputs total 0.05% less.  Hence the cap: dropping
    that sampling changed 0 of 200 random tables at each n=6..10.
    """
    total = 1 << n
    size = node.size
    if total > 32 or size * n < total:
        return
    _, best_c = _best(node)
    if best_c * total >= size * size:
        return
    best_v = None
    for v in range(1, total):
        cv = node.reduce(v)
        if cv and v not in node.cands:
            count = _pairs(node, cv)
            if count > best_c:
                best_v, best_c = v, count
    if best_v is not None:
        node.canon[best_v] = node.reduce(best_v)
        node.cands[best_v] = best_c


def _assure(node: _Node, n: int) -> None:
    """Make the node's best candidate reach half the pigeonhole average.

    The node's points are ``q`` cosets of its span, of dimension ``j``, so
    in the quotient, of dimension ``m = n - j``, half the average over the
    nonzero directions is ``theta = q * (q - 1) / (2 * (2**m - 1))`` ordered
    pairs.  When no candidate reaches it, one that does is found in
    ``O(q)`` work and joins the candidates.  The representatives are zero
    on the span's pivots; ``U`` is spanned by the lowest ``a`` free
    coordinates, with ``2**a >= 2**(m + 1) / q``.  Its cosets split the
    representatives into buckets, and by Cauchy--Schwarz the pairs inside
    buckets number at least ``q**2 / 2**(m - a) - q >= (2**a - 1) *
    theta``.  Counting bucket differences until that many are seen --
    about ``2 * q`` -- leaves some nonzero ``u`` in ``U`` with at least
    ``theta`` by pigeonhole.  Only the chains the clause bound speaks for
    call this, so it is a guarantee, not a search.
    """
    size = node.size
    j = node.dim
    q = len(node.reps)
    if q < 2:
        return
    _, best_c = _best(node)
    if best_c > 1 and 2 * best_c * ((1 << n) - (1 << j)) >= size * (size - (1 << j)):
        return
    pivots = node.pivots
    m = n - j
    a = min(m, (((1 << (m + 1)) - 1) // q).bit_length())
    inside = sum(1 << b for b in [b for b in range(n) if b not in pivots][:a])
    buckets: dict[int, list[int]] = {}
    for p in sorted(node.reps):
        buckets.setdefault(p & ~inside, []).append(p)
    # Stop at (2**a - 1) * theta ordered pairs, cleared of denominators.
    need = ((1 << a) - 1) * q * (q - 1)
    unit = 2 * ((1 << m) - 1)
    counts: dict[int, int] = {}
    seen = 0
    for reps in buckets.values():
        ordered = sorted(reps)
        for i, x in enumerate(ordered):
            for y in ordered[i + 1 :]:
                counts[x ^ y] = counts.get(x ^ y, 0) + 2
                seen += 2
            if seen * unit >= need:
                break
        if seen * unit >= need:
            break
    v = min(counts, key=lambda u: (-counts[u], u))
    node.canon[v] = v
    node.cands[v] = _pairs(node, v)


def _remove(node: _Node, c: int) -> None:
    """Take the coset represented by ``c`` out of the node and its chain below."""
    reps = node.reps
    if c not in reps:
        return
    reps.discard(c)
    node.removed += 1 << node.dim
    # ``cands[w]`` counts points ``q`` with ``q`` and ``q ^ w`` both in the
    # set; the leaving coset pairs with the one ``w`` away, so the count
    # drops by both cosets' points exactly when that one is still present.
    unit = 2 << node.dim
    cands = node.cands
    for w, cw in node.canon.items():
        if (c ^ cw) in reps:
            cands[w] -= unit
    child = node.child
    if child is not None:
        _remove(child, c ^ child.cv if c >> child.hi & 1 else c)


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
        self.root = _Node.root(ones)
        self.nodes: dict[int, _Node] = {}  # pooled direction -> its node
        self.tried: set[int] = set()  # directions scored this phase
        self.cubes: list[tuple[int, list[int]]] = []
        self.since = 0  # points removed since the pool was refreshed
        _score(self.root, _nearest(self.root, min(ones), set(), n, _CANDIDATES))
        _ensure_popular(self.root, n)

    def make_child(self, parent: _Node, v: int) -> _Node:
        """Build the node for direction ``v`` below ``parent``.

        Its set is the parent's pair set for ``v``, scored on the parent's
        best ``_INHERIT`` directions plus fresh nearest differences inside
        it.
        """
        child = parent.below(v)
        ranked = sorted(parent.cands.items(), key=lambda kv: (-kv[1], kv[0]))
        dirs = [w for w, _ in ranked if w != v][:_INHERIT]
        fresh = _nearest(
            child, min(child.reps), set(dirs), self.n, _CANDIDATES - len(dirs)
        )
        _score(child, dirs + fresh)
        _ensure_popular(child, self.n)
        return child

    def discard_pairless(self, node: _Node) -> None:
        """Drop dead candidates without scanning the node's representatives."""
        for v in [v for v, c in node.cands.items() if c < 2]:
            del node.cands[v], node.canon[v]
            if node is self.root:
                self.nodes.pop(v, None)
                self.tried.discard(v)

    def refresh(self, node: _Node) -> None:
        """Replace the node's pairless candidates with fresh nearest differences."""
        node.removed = 0
        self.discard_pairless(node)
        if len(node.cands) < _CANDIDATES:
            # With a full pool _nearest returns nothing, but min still
            # scanned 262,863 cosets over the 364-table audit corpus.
            fresh = _nearest(
                node,
                min(node.reps),
                set(node.cands),
                self.n,
                _CANDIDATES - len(node.cands),
            )
            _score(node, fresh)
        _ensure_popular(node, self.n)

    def extend(self, node: _Node, *, certain: bool = False) -> int:
        """Build the greedy chain below ``node`` as far as it goes; its depth.

        A ``certain`` chain has :func:`_assure` at every level, so it is
        one the clause bound speaks for.
        """
        depth = 0
        cur = node
        while True:
            if cur.child is not None and cur.child.reps:
                cur = cur.child
                depth += 1
                continue
            cur.child = None
            if cur is not node and cur.removed >= _REFRESH * cur.size:
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
            _remove(node, p ^ node.cv if p >> node.hi & 1 else p)
        self.since += 1

    def harvest(self, node: _Node) -> None:
        """Take every coset at the deepest level of the node's chain."""
        chain = [node]
        while chain[-1].child is not None and chain[-1].child.reps:
            chain.append(chain[-1].child)
        leaf = chain[-1]
        dirs = [x.v for x in chain]
        span = leaf.span()
        # A representative is its coset's least point.
        for r in sorted(leaf.reps):
            if r not in leaf.reps:
                continue
            self.cubes.append((r, list(dirs)))
            for s in span:
                self.take(r ^ s)

    def certify(self) -> _Node | None:
        """Bring the chain the proof speaks for up to date and return it.

        From the most popular root direction, at each level the most
        popular candidate of the current set, with :func:`_assure` at each.
        Levels whose direction is still the most popular are kept;
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
            # Scores are exact after _remove; pool refill is optional.
            # At this threshold q <= 4 * removed cosets, so its scan has
            # a removal charge even when certification is called often.
            if cur.removed >= _REFRESH * cur.size:
                self.refresh(cur)
            else:
                self.discard_pairless(cur)
            _assure(cur, self.n)
            best_w, _ = _best(cur)
            if best_w is None:
                cur.child = None
                return node
            child = cur.child
            if child is None or child.v != best_w or not child.reps:
                child = cur.child = self.make_child(cur, best_w)
            cur = child

    def _prune_empty_nodes(self) -> None:
        """Drop pooled nodes whose sets have emptied, unscoring them."""
        for v in [v for v, node in self.nodes.items() if not node.reps]:
            del self.nodes[v]
            self.tried.discard(v)

    def _deepest_chain(self, depth_target: int) -> _Node | None:
        """Return the pooled node whose chain is at least ``depth_target`` deep."""
        best: _Node | None = None
        best_key: tuple[int, int, int] | None = None
        for v, node in self.nodes.items():
            if node.removed >= _REFRESH * node.size:
                self.refresh(node)
            depth = self.extend(node) + 1
            if depth >= depth_target:
                key = (depth, node.size, -v)
                if best_key is None or key > best_key:
                    best, best_key = node, key
        return best

    def _pool_next(self, depth_target: int) -> int | None:
        """Score one more pooled direction this phase; the target it leaves."""
        root = self.root
        # The most popular one first, if a small pool has fallen below average.
        _ensure_popular(root, self.n)
        if depth_target > self.n:
            _assure(root, self.n)
        pick = None
        for v, c in sorted(root.cands.items(), key=lambda kv: (-kv[1], kv[0])):
            if c < 2:
                break
            if v not in self.nodes and v not in self.tried:
                pick = v
                break
        if pick is None:
            return None
        self.tried.add(pick)
        self.nodes[pick] = self.make_child(root, pick)
        if depth_target > self.n:
            return self.extend(self.nodes[pick], certain=True) + 1
        return depth_target

    def _certify_step(self, depth_target: int) -> tuple[bool, int]:
        """Harvest past the proven chain, or drop the phase target a level."""
        proven = self.certify()
        if proven is not None and self.extend(proven) + 1 >= depth_target:
            self.harvest(proven)
            return True, depth_target
        if depth_target > 1:
            self.tried.clear()
            return True, depth_target - 1
        return False, depth_target

    def _take_lowest(self) -> None:
        """Take the remainder's lowest point as a cube of dimension zero."""
        p = min(self.root.reps)
        self.cubes.append((p, []))
        self.take(p)

    def run(self) -> list[tuple[int, list[int]]]:
        """Peel the whole 1-set; returns ``(base, dirs)`` per cube."""
        root = self.root
        n = self.n
        sparse_at = (1 << n) // max(_CANDIDATES, n)
        depth_target = n + 1
        while root.reps:
            if len(root.reps) <= sparse_at:
                self.sparse()
                break
            if self.since >= _REFRESH * len(root.reps):
                self.since = 0
                self.refresh(root)
            self._prune_empty_nodes()
            # 1. the deepest chain at least depth_target deep
            best = self._deepest_chain(depth_target)
            if best is not None:
                self.harvest(best)
                continue
            # 2. score one more pooled direction this phase
            pooled = self._pool_next(depth_target)
            if pooled is not None:
                depth_target = pooled
                continue
            # 3. drop the phase, but only past a chain the proof speaks for
            stepped, depth_target = self._certify_step(depth_target)
            if stepped:
                continue
            self._take_lowest()
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
        alive = self.root.reps
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
                self.root, pivot, seen, self.n, _CANDIDATES - len(cands), scan=False
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
