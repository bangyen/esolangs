# Complete ordered residual sharing in Line

Let a truth table have length $T=2^n$, with inputs indexed most significant
first. This proof concerns the canonical sharing requirement for default
generation. The emitted size is the raster rectangle in pixels; all figures
below use a 20-pixel instruction unit and scale one unless stated otherwise.
It does not assert that a layered drawing minimizes area among all possible
encodings.

## Complete folds and selection

The streaming construction reads in original input order. At depth $d$, a
state is the residual table after its first $d$ input bits, together with
that depth. Canonical child-pair identities intern equal residuals at each
depth. The traversal visits each state once, records every distinct incoming
edge, and assigns its first edge the destination stem. Every later incoming
edge joins that same stem. Equal halves have one outgoing edge and no test.
Terminal values have one shared output stem per value; the independent
`_walk_states` oracle checks those terminal identities as well as readers.

Induction on depth proves completeness. The root represents the whole table.
Splitting any visited residual reaches exactly its two halves, or their
common half once. Interning identifies every equal half at the next depth;
no other residual is identified with it. Thus every reachable residual has
one state, irrespective of how many prefixes reach it. A state at another
depth has a different remaining-read obligation. Mandatory reads on a
constant or test-free descent do not duplicate its eventual selector or
output stem: those are still interned at their own depth.

In the streaming construction, let $E$ be the
number of distinct edges and $S$ the number of reachable states. Every
non-root state has an incoming edge, so $E-(S-1)$ is precisely the sum of
incoming multiplicities beyond the first. The no-joins exit therefore means
there is no remaining merge to draw, not that a residual-count cap was hit.

Default generation compares the streaming fold with the existing tree
and projection fallback. It has no node-count or sharing cutoff. No
input-order search is performed. A joint ablation of the earlier
seven-geometry race (forward, destination, streaming, centered, median,
packed, projected) kept the streaming fold: on symmetric tables it alone
loses at most 2.5 percent against the race (n=5 to 10), and on random
tables at most 9.3 percent (n=6, 7; none at n=8). The projected variant
was removed in 2026-10: priced as a separate mechanism it reached only
8.00/8.96 percent on tiled tables at n=14, under the 10 percent bar.

Each geometry computes its exact bounding rectangle from stroke endpoints
before allocating pixels. Cardinal and 45-degree segments attain their
coordinate extrema at endpoints. The one-unit margins contain the entry
arrowhead, so the measured dimensions equal the rendered canvas dimensions.
A complete fold wins a fallback area tie; the first complete fold retains
subsequent ties. Before a complete fold is selected, the caller passes the
current area plus one to the strict private admission test. After selection,
later candidates receive the current area without that allowance. A fallback
winner is therefore strictly smaller than every eligible complete drawing.
This is a per-table instance of the average-larger canonical exemption in
[Contributing](../CONTRIBUTING.md#what-makes-a-generator-optimization-worth-shipping),
not a lower bound on other physical embeddings.

## Routing and extraction

All routes move forward in the vertical coordinate. Stem columns are
multiples of eight, and outgoing rails are congruent to two or six modulo
eight. Consequently foreign descending rails cannot coincide with stems or with the
opcode envelopes. Summing the signed sideways legs of `i` and `o` gives
excursions between minus one and plus one unit, despite their two-unit
internal connector or diagonal.

Horizontal spans are padded by one unit at both ends before interval
coloring. Spans sharing a row are separated by at least three units.
Ordinary horizontal/vertical intersections are crossings; a join ends with a
one-unit diagonal onto its destination's vertical stem. Arrival and join
rails occupy even-offset rows at two-unit pitch. A join lands on the
following odd-offset row, which contains no horizontal rail. Its own arrival
is at least four units above it, so it reaches the interior of the already
drawn destination stem rather than its entry corner.

The last join landing is at least three units above the next reader's ink;
previous-layer rails end before the next layer's outgoing rails begin.
Opcode excursions and the residue-separated rails retain at least one unit
of clearance. The extractor probes three quarters of the explicit
instruction unit, so this clearance exceeds the probe even at the supported
eight-pixel minimum. Scaling changes pixels, not this integer geometry.
Custom instruction units must also be supplied to native extraction.

The rejected one-unit rail-pitch prototype illustrates why the landing row
is part of the construction. At table `0xFAC748EF`, input `01010`, its graph
returns zero but its native PNG returns one. A typed-grid diagnostic finds
four landings touching foreign horizontal rails, versus none in the shipped
layout. The regression executes all 32 rows of the shipped streaming layout
at the eight-pixel unit, and at scale two with the explicit decoder unit.

## Modeling and emitted area

For residual width $k$, there are at most $2^{n-k}$ occurrences and at most
$2^{2^k}$ distinct tables. Hence the number $M$ of layered states satisfies

$$M\le\sum_{k=0}^{n}\min(2^{n-k},2^{2^k})=O(T/n).$$

For $n\ge16$, split at $a=\lfloor\log_2n\rfloor-1$. The low-width part is at
most $n2^{n/2}\le T/n$; the high-width part is at most $T/2^a\le4T/n$. The
finite smaller arities change only the constant. There are at most two edges
per state and a fixed number of stroke segments per edge. Column ranges in a
layer are bounded by its state count and its predecessor's. Thus left-edge
interval coloring, including its column sweep, takes $O(M)$ work summed over
the layers. Validation,
dependency detection, projection and the fixed reversal also take $O(T)$ RAM
work.

Rejected candidates retain only $O(M+n)$ nodes and segments. They never
expand a rectangle or a long segment into grid cells. A selected drawing is
no larger than the tree fallback. Alternating perpendicular subtree extents
bound each tree side by $O(2^{n/2})$: two decision levels double a side,
with an additive $O(n)$ bound for intervening pointer moves. Solving the
recurrence $s(n)\le2s(n-2)+O(n)$ gives that bound. The loader adds $O(n)$,
which does not change it. The fallback rectangle is therefore $O(T)$.
Selected segments overlap only at bounded-degree crossings and joins, so
painting, row conversion and PNG output cost their $O(T)$ emitted area. No
linear-area claim is made for an unselected complete bus.

## Execution and written workspace

A streaming state overwrites original cell zero with its next input. Its
fork tests that bit; an equal-half state continues without testing.
Constants drain all remaining inputs. The terminal moves once to initially
zero cell one, optionally adds one, and outputs. Induction on the residual
table therefore gives the intended answer after exactly $n$ reads. Both
cells lie within the original tape for $n\ge2$, and every stored value
remains a bit. There are at most $n$ tests and $n-1$ join transitions; three
terminal operations and the halt give at most $3n+4\le5n$ commands.

Let $K$ count actual conditional forks in a complete fold. At the last
selector level, only identity and complement are nonconstant, and the
earlier levels contain at most $2^d$ forks at depth $d$. Therefore
$K\le\sum_{d=0}^{n-2}2^d+2=2^{n-1}+1=T/2+1$. A drawn binary fork tree has at
most $2K+1$ real frames, and the complete DAG has at most $K-1$ additional
join resumes: including the two terminal values, $E-(S-1)=K-1$. Inline
constants can only remove joins. Thus the frame count is at most $3K\le2T$
for $n\ge3$. The frame index uses at most $n+1$ bits. The opcode position,
including the end-of-frame position, is at most $3n-2$. A streaming suffix
below its first fork has at most $n-1$ reads and three output operations,
within $3n-2$. The pointer and input
cursor need at most $\operatorname{bl}(n-1)$ and $\operatorname{bl}(2n-1)$
bits. At most the original $n$ bit-valued tape cells are written. Their
indexed representation gives the unchanged bound

$$n+1+\operatorname{bl}(3n-2)+\operatorname{bl}(n-1)
+\operatorname{bl}(2n-1)
+\sum_{c<n}(\max(1,\operatorname{bl}(c))+1).$$

The two-input initial band is checked exhaustively. These are bounds on
native extracted frames and written snapshots, not retained generator
metadata.

## Executed evidence

The fixed cohort contains 200 eight-input tables from `Random(19)`, using
successive `choice("01")` calls. For each table, both complete geometries
are compared and the smaller is taken; the 200 public PNGs are executed
natively on all 256 rows (51,200 rows, no mismatch). The complete
drawings total 7,929,032,800 pixels; the public fallbacks total
3,809,364,000. Every complete drawing is larger than its corresponding
fallback, and the aggregate excess is 108.145843 percent.

This is not a zero-result probe. Parity at eight inputs shares in 1,534,400
pixels versus the 15,404,800-pixel tree and executes all 256 rows. Majority
at eight inputs shares in 3,952,000 pixels, also with all 256 rows checked.
The independent substring oracle checks all sixteen two-input and all 256
three-input tables, plus eight seeded tables at each arity four through
eight, against the streaming fold. It verifies shared terminal identities
as well as nonterminal states and no-joins refusals. Existing native suites
separately execute every admitted three-input stream and seeded four- through
six-input controls.

Before and after the tie-policy change, all 256 public three-input PNGs
execute all eight rows: 4,096 native rows. Outputs, maximum commands and
aggregate area are unchanged at 55,985,652 pixels, with no table growing.

The deep growth diagnostic retains its 4.4 threshold and uses the registry's
default twelve-input ceiling. Its dense difference ratio is 4.015292 in
37.8 seconds. The former six-input ceiling mixed the small-tree layout
through five with the later tree layout and reported 11.393166 both before
and after the tie-policy change. The restored cohort has three final rungs
per arity parity above that transition; this finite statistic supports, but
does not replace, the construction bounds. The growth witnesses are also
executed from PNG with zero/one and spaced-row controls. The twelve-input
dense PNG occupies 311,827,200 pixels and passes 34 native rows in at most
60 commands; its native extraction and compilation take 21.3 seconds after
rendering. Pillow's default pixel guard rejects that locally generated
fixture, so the verification decoder uses an explicit allowance bounded by
its measured dimensions. The Line coverage and opcode checks are unchanged.

The historical 40.3 percent estimate counted duplicate nonconstant subtables
on 200 five-input tables and priced each with a raw parity-tree area slope.
It charged no routing cost. Reproduction checks 12,800 native rows across
raw and current public PNGs and yields 40.301185 percent from that formula.
It is an upper-bound cost model, not a measured attainable area reduction.
It does not invalidate the exact-area comparison of complete drawings.
