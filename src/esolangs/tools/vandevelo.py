"""Boolean-function generator for Vandevelo.

The program reads the inputs, then hangs -- ``loop -> loop?`` evaluated
lazily never terminates -- exactly when the table entry is 1.  Every bindable
value is affine in the inputs (``==``/``!=`` are XNOR/XOR over nil) and only
``::`` chains evaluate conditionally, so a guard line hangs on an affine
coset of inputs.  One guard line is emitted per coset of an affine cover of
the 1-set; single cosets and their complements (every affine table) bypass
the peel after geometric doubling checks.

A test for 0 is ``x? == Nil?``, eight characters and four steps over a bare
``x?``, so guards avoid it: a register's last toggle takes whichever
polarity the clause wants, an input mostly tested for 0 is read negated
(``~!>``) when the rows reaching those tests agree, and a test every
reaching row passes is dropped.  Ordering bare tests first saved 0.0% of
characters and 8.8% of steps at n=7, and was retired.  Over the three-input
tables: 26,438 characters to 23,425.

The cover is an affine-cube peel.  A cube is grown by iterated popular
differences: pick ``v`` maximising ``|B & (B ^ v)|``, intersect, repeat
while a pair remains; the chain finds cubes of dimension about
``log2(log2(T))`` that no local search sees.  Cohen--Shinkar (ECCC
TR14-099): at remainder density ``eps`` the chain from the most popular
direction reaches ``d(eps) = log2(n) - log2(log2(1/eps)) - 2``, so a peel
taking only cubes of at least that dimension ends in ``1 + 9 * 2**n / n``
clauses.

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
building, scoring, removal, refresh and :func:`_assure` cost its coset
count ``q``, which at least halves a level.  Removal charges to cosets
built.  So does refresh in :meth:`_Peel.extend` (after a quarter is lost),
but not :meth:`_Peel.certify`, which refreshes every level on every call.
The sampled fallback scores :data:`_SAMPLES` uniform pair differences; it
is a heuristic -- :func:`_assure` carries the bound and on measured tables
never computes.  The sparse tail costs a constant per point.

Linear time is not proved, and cannot be before linear output.  Four build
terms escape the charge: a child rebuilt after it empties scans its
parent's ``q`` cosets (bounded by ``q**2`` a node, likewise
:meth:`_Peel.certify`); cosets built cost ``O(T * n)`` a chain; halving
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

A cube's guard needs one part per dual-space constraint.
:func:`_constraints` builds them from short relations: all but at most
``1 + 2**((dim + 1) / 2)`` are parities of at most four inputs, the rest
come from reduced elimination at most ``dim + 1`` wide, so a clause weighs
at most ``4 * n + (dim + 1) * (1 + 2**((dim + 1) / 2))`` inputs.
Single-input constraints test the input directly; wider ones live in
strict register bindings (``A ~> a?``, ``A ~> A? != b?``) that later
clauses morph one toggle at a time; a morph costs strictly fewer lines than
a fresh register, so upkeep never exceeds the total weight.  Over the peel
that is ``4 * n + 36 * 2**n`` by the clause bound, the second term at most
``4 * 2**n`` over the disjoint cubes, so register upkeep is O(T) lines --
under ``40 * 2**n + 4 * n`` -- and measures under half the emitted text.
The bank holds at most ``n**2`` registers (:func:`_bank_cap`), so a name is at most two
input names long and a full bank respells its least recently used free register
at fresh cost; a clause scans the :data:`_SCAN` most recently used, a
constant per constraint.  The reduced-echelon basis alone would not bound
the weight: on a cube whose columns spread over ``2**dim`` values it
weighs ``n * dim / 2`` whatever the pivots, ``Theta(T log log T)`` at the
``log2(n)`` dimensions the peel produces.  Identifier lengths are ``O(log
n)``, so characters are ``O(T log n)``, not ``O(T)``; removing that factor
is open.
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
    node: _Node, pivot: int, seen: set[int], n: int, cap: int, *, scan: bool = True
) -> list[int]:
    """Return the ``cap`` nearest differences from ``pivot`` inside ``node``.

    Smallest by ``(bit_count, value)``, skipping ``seen`` and the node's
    span: the differences are walked in that order -- each weight's values
    ascending, by Gosper's next-permutation step -- testing membership, so
    a dense set yields its head after about ``cap / density`` probes.  When
    four times ``cap`` probes have not filled the list the set is sparse
    and the whole of it is listed instead, at its size; the answer is the
    same either way.  This is the one step on a node that costs points,
    not cosets: listing only the representatives' differences costs
    cosets but moves emitted size by up to 4% a table, either sign, at
    n=8..12.  With ``scan`` off the probes' finds are returned as they
    stand.
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
        extra = heapq.nsmallest(
            cap - len(out),
            (
                (v.bit_count(), v)
                for v in (pivot ^ r ^ s for r in reps for s in span)
                if v and reduce(v) and v not in seen and v not in found
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
        "parent",
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
        parent: _Node | None,
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
        self.parent = parent
        self.removed = 0

    @classmethod
    def root(cls, points: set[int]) -> _Node:
        """Return a chain's top, where every point is its own coset."""
        return cls(0, 0, points, {}, None)

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
        return _Node(v, cv, pairs, pivots, self)


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
    count = 0
    for r in reps:
        if (r ^ cv) in reps:
            count += 1
    return count << node.dim


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
    probability at least a half.  A uniform pair of points is a uniform
    pair of cosets plus a span element that changes no pair count, so the
    draw is between representatives.  :data:`_SAMPLES` draws cost what
    scoring that many candidates does; the first to clear joins the
    candidates.
    """
    size = node.size
    total = 1 << n
    if size * n < total:
        return
    _, best_c = _best(node)
    if best_c * total >= size * size:
        return
    reps = list(node.reps)
    # Seeded by the set, so the program is a function of the table.
    rng = random.Random(size)  # nosec B311
    best_v = None
    for _ in range(_SAMPLES):
        v = rng.choice(reps) ^ rng.choice(reps)
        if not v or v in node.cands:
            continue
        count = _pairs(node, v)
        if count > best_c:
            best_v, best_c = v, count
    if best_v is not None:
        node.canon[best_v] = best_v
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

    def refresh(self, node: _Node) -> None:
        """Replace the node's pairless candidates with fresh nearest differences."""
        node.removed = 0
        for v in [v for v, c in node.cands.items() if c < 2]:
            del node.cands[v], node.canon[v]
            if node is self.root:
                self.nodes.pop(v, None)
                self.tried.discard(v)
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
            if child is None or child.v != best_w or not child.reps:
                child = cur.child = self.make_child(cur, best_w)
            cur = child

    def run(self) -> list[tuple[int, list[int]]]:
        """Peel the whole 1-set; returns ``(base, dirs)`` per cube."""
        root = self.root
        n = self.n
        sparse_at = (1 << n) // max(_CANDIDATES, n)
        depth_target = n + 1
        tried = self.tried
        while root.reps:
            if len(root.reps) <= sparse_at:
                self.sparse()
                break
            if self.since >= _REFRESH * len(root.reps):
                self.since = 0
                self.refresh(root)
            for v in [v for v, node in self.nodes.items() if not node.reps]:
                del self.nodes[v]
                tried.discard(v)
            # 1. the deepest chain at least depth_target deep
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
            p = min(root.reps)
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
    # Keep pair sums rather than materializing every triple. Querying a
    # triple against each core column preserves the old first witness.
    witnesses: dict[int, int] = {}
    pairs: dict[int, int] = {}
    core: list[int] = []
    duals: list[int] = []

    def rank(inputs: int) -> tuple[int, int, list[int]]:
        # The old cache inserted witnesses by last input, then width,
        # then the earlier inputs in ascending order.
        return inputs.bit_length(), inputs.bit_count(), _points(inputs)

    for j, col in enumerate(cols):
        if col == 0:
            duals.append(1 << j)
            continue
        witness = witnesses.get(col)
        if witness is None:
            witness = pairs.get(col)
            for c in core:
                pair = pairs.get(col ^ cols[c])
                if pair is not None and not pair & (1 << c):
                    triple = pair | (1 << c)
                    if witness is None or rank(triple) < rank(witness):
                        witness = triple
        if witness is not None:
            # A later core input cannot precede this witness's last input,
            # so repeats keep the first witness without another core scan.
            witnesses[col] = witness
            duals.append(witness | (1 << j))
        else:
            for c in core:
                pairs[col ^ cols[c]] = (1 << j) | (1 << c)
            witnesses[col] = 1 << j
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
        cubes = [coset] if coset is not None else (_Peel(ones, n).run() if ones else [])
        cover = _pruned([_constraints(base, dirs, n) for base, dirs in cubes])
        dims = [len(dirs) for _, dirs in cubes]
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
        lines.append(
            "::".join([*parts, loop]) if compact else " :: ".join([*parts, loop])
        )
    return "\n".join(lines)


def _pruned(cover: list[list[tuple[int, int]]]) -> list[list[tuple[int, int]]]:
    """Drop the tests every row reaching their clause passes.

    Random tables: 0.0% of characters.  Unions of cubes and axis half-spaces,
    which the peel covers with one-test clauses: 10.7% at n=8, 12.1% at n=10.

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
    the bare tests count.  Saves 1.5% of characters on random tables at n=8
    (200 tables), 14.8-17.6% on single-minterm tables at n=8-12 and 24-32%
    when the minterms have few 1 bits: judged on that sparse class.
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
