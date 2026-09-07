# `%^2^-1` boolean generator: reach, bounds and negative results

How far each of the six constructions reaches, what bounds it, and what was
tried and removed.  The constructions themselves are in
`src/esolangs/tools/boolean/pct_squared_minus_one.py`, whose docstring is
authoritative and not restated here; this file keeps the arguments a future
change would otherwise have to re-derive.

Whatever a construction misses is *unreached*, never proved unreachable.  The
wall in [`docs/proofs.md`](proofs.md) covers the **reading** model only —
nothing here bounds embedded-input programs in general, and
[`docs/limitations.md`](limitations.md) records what bounds are actually
known.

## Coverage by construction

| construction | reaches |
|---|---|
| two-input derivation | every table at `n <= 2`, XOR and XNOR included |
| `_cascade` | every conjunction or disjunction of literals, any arity, in `2n + 4` characters |
| `_affine` | 86 tables at three inputs, in 0.8s for the arity |
| `_ladder` | majority-3 and the other linearly separable tables |
| `_deep_band` | **all 65536** four-input tables |
| `_fold` | five inputs and beyond; eleven inputs reached |

The two-input derivation does not generalise past two inputs — it reads one
slope per column of a two-input table — and the reason is structural: one
affine map per input composes into a *shared* value, which forces each
cofactor of the table to be constant or an affine image of one shared
function.  Only **88 of the 256** three-input tables satisfy that.

A one-input table is derived as the two-input table that ignores its second
input.

## What each construction pays for

`_ladder` is the only path that computes *with* the over-3003 reset instead
of keeping clear of it.  Every other path is affine in the accumulator, so
the rows keep their order and no two merge unless they already agree; the
reset is the one primitive that is not affine, mapping everything above 3003
onto zero and leaving everything below alone — a threshold.  A threshold on a
weighted sum is a majority, which is why this path builds majority-3, the
smallest OR of disjoint subcubes and one the composed-affine search cannot
reach.

One bound is known about it: a single reset is one threshold, and only **104
of the 256** three-input tables are linearly separable, so that shape cannot
be made total by widening its grid.  What lifts it is not more arithmetic but
a different *printing command* — `e` prints `chr(acc & 0xFF)`, so a row only
has to be **congruent** to 48 or 49 mod 256 rather than equal to 0 or 1.

## What bounds `_deep_band`: distinctness, not runs

The count is worth stating because the obvious guess is wrong.  A first
reading had each run boundary consuming a residue system, allowing about
`3003 // 256 == 11` of them — but random five-input tables refuse at five to
eight runs, well inside that.

The real budget is the span distinctness costs.  Two rows sharing a value are
merged by the first cut that reaches them and can never be separated again,
so a weighting serves a table only if every collision it forces joins rows of
one class.  Keeping *all* rows distinct needs weights growing like a binary
code, a span of `(2**n - 1) * 256`: **1792** at three inputs, which fits under
the limit, against **3840** at four and **7936** at five, which do not.  From
four inputs on, every weighting inside the limit collides some rows, and a
table builds only if its structure tolerates the collisions forced on it.

Four inputs are total because 3840 overshoots 3003 only slightly and enough
weightings survive.  At five, the searched family collides two rows of
opposite classes in all **537792** of its weightings for a random table, which
is why generic five-input tables are refused by the deep band — while
*symmetric* tables build at any arity, the popcount ladder spanning only
`n * 256` and colliding exactly the rows such a table already agrees on.
Parity-5, majority-5 and threshold-5 all build, and parity is executed on the
interpreter through six inputs.

**Removed: the positive-ladder variant.**  It shipped alongside `_deep_band`
for a while and was removed once measured — it served no table the deep band
does not (**0 of 256** at three inputs, the only arity it reached) and its
programs were about four times longer (median **11492** characters against
**3144**), so it was strictly dominated on both axes.

## What bounds `_fold`: the workspace, then the move algebra

Five inputs close on this path: every table tried plans and executes — all
**256** at three inputs, **120** random at four, **300** random at five plus
parity, every threshold, near-parity and the fully alternating **32-run**
worst case, and **40** at six inputs — against the 496 the weighted
constructions reach at five.  The fold is not *proved* total at any arity it
does not enumerate.

The bound is the ladder's footprint rather than an arity check.  Rows start at
`-step * r`, so the ladder spans `step * (2**n - 1)`, laid from a zero
accumulator, which means it has to fit inside `[-3003, 0]`.  At the shipped
spacing of 4 that is **4092** at ten inputs, over the workspace, and no plan
on such a ladder could ever be emitted.  Halving the spacing halves the
footprint to **2046** (`_FOLD_NARROW_STEP`).

But *uniform* spacing is itself the waste.  The plan needs only that the rows
sit at `2**n` **distinct** positions, and distinctness costs about `2**n`
rather than the `2 * (2**n - 1)` a step-2 ladder spends.  The packed ladder
`_FOLD_SUBSET_LADDER` meets the exact floor, `2**n + 1`, carrying **eleven
inputs** at **2049** where the uniform one wanted **4094**.

Twelve is where it ends, and there the wall is the move algebra rather than
the spelling.  The doubling `m` — the only way to reorder groups at all — is
offered only when the state's spread is at most 3002, and `2**12` distinct
positions span at least **4095** wherever they sit.  So no twelve-input ladder
ever doubles: the search from such a state **exhausts after fifteen states**,
an empty frontier rather than a budget.  Thirteen is impossible by counting
alone, `2**13` positions against the **6007** values a `p` can address.

## Cost, and why the fold sits last in the chain

A fold plan is **0.15ms** at three inputs, **0.36ms** at four, **1.0ms** at
five and **3.2ms** at six (medians; worst observed 3.3ms at five, 5.9ms at
six; a 997-group eleven-input plan is **2.3s**).  Two things make that hold
rather than degrade.

The plan is one named move per state rather than a search.  The search-based
configurations this replaced once left a 21-point table too wide to search and
too narrow for their descent's target, spending **fifty seconds** to refuse a
table they could build — a failure mode a case analysis does not have.

And `_deep_band` is screened above four inputs instead of enumerated, since a
refusal there cost about **eighteen seconds** and a generic five-input table
can never build (only tables agreeing on every popcount class survive the
collisions its weightings force).  Screening moved a generic five-input build
from **~18.3s to ~0.13s**, at the price of the shorter programs the deep band
would have found for the asymmetric tables it happened to serve.

## Two shape choices that decide the reach

Both are assumptions of the shape rather than of the language.

Building the ladder **positive** makes every row sum sit under the limit at
once, so distinct sums need weights behaving like a binary code — at least
`2**n - 1` units against the `3003 // 256 == 11` the limit allows, which stops
at three inputs because four needs 15.  Building it by **subtraction** instead
puts the whole order below zero, where the reset cannot fire and no budget
applies.

And distinct sums are more than the table needs: a cut *erases*, so every row
it wipes lands on zero together whatever the gaps between them were, and only
the boundaries *between* runs need a full residue system.  Rows may therefore
collide when they share a class, which prices a table's span by its number of
runs instead of by `2**n`, and admits the popcount ladder — every weight one —
on which parity spans `n` units rather than `2**n - 1`.

## Removed: the setter-assignment enumeration

An earlier version enumerated setter assignments, a product of size
`len(options) ** (2 * n)` guarded by a budget.  The two-input derivation
replaced it outright and needs no budget.

An enumeration over branch pairs likewise stood where `_affine` now solves,
reaching the same **86** tables at **6.4 seconds** for the arity against
**0.8** and emitting longer programs.  What is left of it is the equal-width
spelling by `_spellings_by_width`, which is what lets an odd width gap close.
