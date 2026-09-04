# Minifuck boolean generator: negative results

Why the generator is **total** — no arity and no table it declines — and
what that cost to establish.  The construction itself is in
`src/esolangs/tools/boolean/minifuck.py`, whose docstring is authoritative
and not restated here; this file keeps the arguments a future change would
otherwise have to re-derive.

An enumeration cap is evidence about the enumeration, not about the
language — the reusable lesson behind this file.  The blocker index is
[`docs/limitations.md`](limitations.md); other languages' negative results
are in [`docs/walls.md`](walls.md).

**The staged route is total at `n <= 3`.**  It derives the
`(separator, settle count, suffix, accumulator)` choice rather than searching
for it, and builds every table at one, two and three inputs.  The selection
rule is why it reaches tables the searches cannot: the searches hunt for a
cell *holding* the answer and then lose it to the prefix-XOR on the walk out,
while the staging selects on the column **as the read sees it**.  Sampled
tables that fail after ~130 seconds of searching build in under 0.08s from a
staging.  `src/esolangs/tools/boolean/minifuck.py` carries the mechanism and
the pool-code derivation; what follows is only what is *not* reachable and
what was disproved along the way.

## The termination convention is not available

Point Break's generator sidesteps having no output by halting for a 0 and
looping for a 1, and that convention would suit Minifuck's obstruction
exactly, consuming the answer where it stands with none of the transit that
washes a column out.  Minifuck cannot use it.  The instruction pointer is
only ever incremented — once in `[`'s skip branch, once at the end of `step`
— with no decrement, assignment or jump anywhere in the interpreter, so every
program halts within `len(code)` steps.  "Loops forever" is not a reachable
state.  Confirmed over 4000 random programs: none failed to halt, and the
step count never exceeded the program length.  This is also why the language
needs no hang detector.

## Is `_mux` total?  Every refusal site closes by argument

Nothing in the construction reads `n` except `_mux_weights`, `_mux_pad` and
`_mux_start`, all closed forms defined for every `n`.  XOR builds at every
arity tried through seven — 243, 429, 622, 2511, 9565 and 39915 characters
at `n` of 2 to 7.  **448 of 448 rows correct** on the shipped interpreter,
sampled across `n` of 5, 6 and 7 (XOR and random tables).

`_mux` never raises, so *total* means exactly "no `None`-site fires".  There
are six such sites, and the failure surface is therefore finite.  A table also
needs only **one** `(acc, cell7, direct)` combination to succeed, so a witness
argument suffices.

The whole chain rests on one atom.  From a skip-free state `'[x'` advances the
pointer, flips the cell, conditionally flips the neighbour, and **never leaves
a skip pending** — exhaustive over all four `(cell, neighbour)` states.  From
it: no round begins with a pending skip (walks and pads are `[x` runs, setter
fills are `[<`/`xx`, `_mux_weight` ends in `<`, rounds end in `x`); a round's
`'<'*R + '[x'*R + 'x'` moves `−R` then exactly `+R`, so **every pointer is
restored**; and a row at `q` writes only within `[q−R+1, q+1]`, whose low end
is at least 9 because the guard gives `R <= min(ptrs) − 8`.  **Cells 0..8 —
the pool `tape[:8]` and cell 7 — are therefore frozen after the initial
walk.**  Instrumented over 670 rounds: no pending skips, no pointer movement,
and the lowest cell ever written is exactly 9.

**Separation (site 2) is injective, uniformly in `n`.**  The final pointer is
`c0 − sum_i 2**(n−1−i) * x_i`, verified in the real emission context for `n`
of 2 to 8: all `2**n` rows distinct, no row dead.  **The mechanism the source
states for this is wrong**, and finding out why is what turned the arity
residue into a proof; see the subsection below.

**The weight gadget gates a walk; it does not re-read the bit.**  The
docstring says `[x<[<` "moves the pointer by the bit's value and puts the cell
back, so the bit can be read again", and that `k` such reads displace by `k`
times the bit.  The contract is right and the mechanism is not.  Exhaustively
over every local configuration, one read followed by the rewinding `<` moves
**−1 if the cell at `ptr+1` reads 1 and 0 otherwise**, restoring that cell and
leaving no skip.  So the setter's bit only *gates entry*: a `bit = 1` row
starts walking left and each further read consumes **one cell of the walk's
wake**, while a `bit = 0` row never starts.  Probed on a blank tape the gadget
therefore stalls after a single read — displacement −1 whatever `k` is — which
is not staleness but simply that there is no wake to consume.

This matters because it converts the gadget's linearity from a measurement
into an inequality.  The gadget is linear exactly while the wake lasts, so it
saturates at `k > start + 1`: at four inputs, where `start = 31`, the spread
climbs with `k` to 32 and is pinned at 32 for every larger `k`.  The 32 is not
a constant of the language — it is that arity's own starting cell.

**So the first gadget never saturates, for any `n`.**  It needs
`k = 2**(n-1)` and has `start + 1` cells of wake, and
`_mux_start(n) = 32 + max(0, 2**(n-1) - 9)` gives

* `n <= 4`: `start + 1 = 33` against `k <= 8`;
* `n >= 5`: `start + 1 = 24 + 2**(n-1)` against `k = 2**(n-1)`.

The margin is **exactly 24 cells at every arity from five up** — independent of
`n`, which is what `_mux_start`'s `- 9` term is buying.

**And no later gadget can saturate either**, because each one's territory lies
strictly right of its predecessor's.  Writing `E_i` for the pointer entering
gadget `i` and `L_i = E_i - k_i` for its leftmost reach: a `bit = 1` row loses
`k_i` and the following pad walk restores `k_i + pad`, so `E_{i+1} >= E_i +
pad`, while `k_{i+1} = k_i / 2`.  Hence

    L_{i+1} - L_i  >=  pad + k_i / 2  >  0

for every `i` and every `n` — **the halving weights are what guarantee it**.
Each gadget therefore consumes wake laid down by a pad walk over cells that
row has never touched, and a `[x` run over pristine zeros leaves solid ones.
(A `[x` run over *junk* does not: it leaves ones only from a zero tape, which
is why the non-overlap is load-bearing rather than decorative.)  Verified per
row and per gadget: no path cell reads anything but 1, at every arity from two
to ten, and the separation stays affine and injective at eleven and twelve
inputs — 2048 of 2048 and 4096 of 4096 distinct pointers, no dead row.

**The reusable lesson.**  A contract can be measured true for years while the
mechanism named beside it is false, and the two only come apart when someone
needs the mechanism.  "Measured linear for `k` of 1 to 8" was true, and every
shipped arity was inside the region where it holds; the explanation attached
to it would have predicted linearity on a blank tape, where the gadget in fact
stalls at one cell.  What made the difference was asking *why* the number was
what it was, rather than extending the range it had been checked over.

**The rewind guard (site 4) can never fire.**  The accumulator loop starts at
`hi − lo + 9`, and there the worst rewind is

    hi − (hi − lo + 9) + 1  =  lo − 8

which *is* the guard `min(ptrs) − 8`; larger accumulators only shrink the
rewind, and pointers never move, so `min(ptrs)` stays `lo`.  An algebraic
identity, independent of `n` and of the weights, checked at `n` of 2 to 9
(25/25, 27/27, 35/35, 62/62, 126/126, 270/270, 590/590, 1294/1294).  The
"margin reaches 0" comment in the source is this identity seen from the
inside: it is tight by construction rather than by luck.

**The round cap (site 5) suffices.**  The probe clamps every row to `ptr = 0`
and walks to a converged pointer, so a "column" is one fixed cell index read
across the rows — measured, exactly one index (cell 24) over a whole build —
and not each row's own `q+1`.  Given that, monotonicity is geometric.  A round
uses `R = f − acc + 1`, so a row at `q` has window low end `q − f + acc`; for
`q > f` that exceeds `acc`, and cascades write `cell+1`, so **both write
mechanisms miss the read cell**.  Since `acc < lo <= q`, the window contains
`acc` **iff `q <= f`**: rows above the frontier cannot change (0 violations
over 4128 row-round pairs).  And the frontier's own read cell always flips,
because the walk lands on `q − R + 1` first while every cascade writes
`cell+1` and the walk never *lands* on `q − R` — so nothing reaches that cell
twice.  Exhaustive for `R` of 1 to 8 over every window configuration, and 0
failures over random and hostile all-ones tapes to `R = 128`.  Each round
therefore fixes its frontier permanently and the frontier strictly decreases,
so at most `2**n` rounds are needed under a cap of `2**n + 4` (measured: 0
non-monotone events, 232 of 232 frontier flips, at most 40 rounds used against
a cap of 68 at six inputs).

The tempting shortcut here is *false* and is worth recording as such: cell
`acc−1` is 1 in 104 of 207 rounds, so its cascade does fire.  It simply lands
after the walk has already flipped `acc`, and cannot undo it.

**Pool coverage (site 3) closes too, and uniformly in `n`.**  `_pool_reaches`
reads cells 0..7 after walking out, plus the pointer, skip and dead gates.
Three facts collapse it to a single execution:

* *The probe state is canonical.*  Cells 0..8 are frozen, `_mux_probe` emits
  `x` (absorbing any pending skip) and then clamps, and `<` never writes — so
  every probe state is `ptr = 0`, `skip` clear, `dead` clear, with the same
  frozen prefix.  That prefix is `(0,1,1,1,1,1,1,1,1)`: **one value, identical
  across every row and every arity from two to nine inputs**, because it is
  the wake of the initial `[x` walk over a blank tape and `_mux_start(n)` is
  at least 32 for all `n`.
* *The code never looks past the frozen region.*  The shipped winner
  `[<[<[<<[[[<[[<<<` walks the trajectory
  `1 1 2 1 2 2 1 2 3 4 4 5 6 6 5 4` — **maximum cell 6**, comfortably inside
  cells 0..8.  It therefore cannot see a round's debris at all, and the rows
  cannot diverge, so `len({m.ptr}) != 1` cannot fire either.
* *Neither remaining gate can fire.*  No pool code contains `.`, and `.` is
  the only instruction that sets `dead`; every code ends in a `<` run, and `<`
  never sets `skip`.

So the verdict is a function of the frozen prefix and `cell7` alone, which
makes one execution per orientation an **exhaustive** check rather than a
sample: `True` at `cell7 == 0`, verified identically at four, five, six and
seven inputs.  Measured the long way round first, and agreeing: over every
reachable probe state (93 at four inputs, 168 at five) the verdict never
varied, and over 1426 probe calls at four, five and six inputs there were no
`None` returns, with exactly one of the five codes ever selected.

The witness is that one orientation.  A code answers `cell7 == 0` or
`cell7 == 1` and never both, so the `cell7 == 1` arm of the sweep contributes
nothing to existence — the claim is precisely that **at `cell7 == 0` a code
always reaches**, which is all a totality witness needs.  The `_walk_to`
sub-case cannot raise: `_pool_reaches` accepts a code only after checking its
pointer is converged, and that check precedes the emit.

One step is needed to carry this to the real emission, which walks to the
caller's accumulator rather than to nine: `_endgame` asks `_find_pool` for
`acc − 1`, while the probe above settles the verdict at `_PROBE_WALK_OUT`.
The source records the two agreeing as a measurement over walk-outs 9 to 41.
It is a **corollary of the `[x` atom**: the pair's pointer step is
value-independent and its cascade writes `cell + 1`, strictly rightward, so
once a walk has crossed cell 8 no later step of it can reach back into cells
0..7 — and those are the only cells the verdict reads.  The verdict is
therefore identical for every walk-out of nine or more, whatever debris the
walk crosses.  Site 6 closes given
site 3, because the sculpt's exit test and `_try_print` go through the same
pool-walk-read path, so column agreement implies a correct print.

**So all six sites close, and `_mux` is total at every arity.**  The `[x`
atom, skip cleanliness, pointer restoration and write confinement are finite
case analyses; the rewind identity is algebra; the round cap is window
geometry plus the single-flip lemma; site 3 is the canonicity argument; and
the separation is affine injectivity resting on the two saturation bounds
derived above.  None of them carries a residual `n`.

**The three quantities that were per-arity measurements now have `n`-uniform
arguments**, which is what closes the arity question rather than deferring it:

* *The separation leaves `2**n` distinct pointers.*  Affine injectivity gives
  this once every gadget is linear, and both saturation cases are ruled out
  above — the first gadget by the constant 24-cell margin, the rest by the
  strict non-overlap `L_{i+1} - L_i >= pad + k_i / 2`.
* *The frozen prefix is `(0,1,1,1,1,1,1,1,1)`.*  It is the wake of `_walk_to`
  over a blank tape, which lays a one at each cell it crosses and never
  returns, so cells 0..8 reach that value after **eight** `[x` pairs and never
  change again.  Every arity's walk is at least 31 pairs — `_mux_start(n) - 1`
  is 31 at its smallest and grows — so every arity gets the same prefix.
* *The pool code's trajectory peaks at cell 6.*  Its execution reads only cells
  0..8, which the previous point fixes to a single value, so the trajectory is
  the same computation at every arity, not a coincidence repeated per arity.

None of the three depends on the truth table, so one argument settles all
`2**(2**n)` tables at every arity at once.  `_mux_separate` still runs the
distinctness check at emission time, which now serves as a guard rather than
as the thing the claim rests on: were a future change to break linearity, the
construction refuses instead of emitting a wrong program.

Everything measured agrees: all 16 tables at two inputs and all 256 at three,
92 of 92 random tables at four, five and six, no refusal anywhere, and 448 of
448 rows correct on the shipped interpreter at five, six and seven.  The
binding constraint is cost, not expressiveness: template length grows about
fourfold per arity (a rewind costs `3K+1` characters with `K` on the order of
the `2**n` span, across up to `2**n` rounds) — about 0.14s a table at five
inputs, 40s at six, 820s at seven, where the template reaches 13685
characters.

**The generator is total.**  `_MUX_ARITIES` was a verification boundary and
nothing more; widening it needed no new construction and no new check,
because the three arguments above hold at every `n`.  What it still owed was
*execution*, since this repository's standing rule is that a claim about a
generated program is worth what its run on the shipped interpreter is
worth — now paid, at 448/448.  The tuple is replaced by the floor
`_MUX_MIN_ARITY = 2`, which exists only because `_solve` routes constants
and one-input projections to `_degenerate` before the route is reached.

A six-input table with a *narrow essential core* projects down to a smaller
arity, which is why "does `n = 6` build?" has to be asked with a
fully-essential table to mean anything.  There is no arity, and no table at
any arity, that the Minifuck boolean generator declines.

Coverage before this route closed the arity: complementing inputs as they
land took four inputs to **60942 of 64594 (94.35%)**, and that residue is
what the sculpting was built to attack.

## `n == 5` ships partially; full coverage is out of reach of any flat family

A flat pool of columns cannot cover a real *fraction* of five inputs, but it
carries a measured sliver, derived rather than searched for.

**Measured, not estimated.**  `_derived_plans` cannot run at this arity: it
pre-builds a `wanted` dict over all `2 ** (2 ** n)` tables, which is `2**32`
entries.  Inverting the loop — collect the columns the family actually
produces, then count them — gives:

| suffix family, all 5 separators × 2 settles, shipped caps | distinct 32-bit columns | fully essential |
|---|---|---|
| pure runs `'[' * k` | 2508 | 1874 |
| one `<` inside the run (**shipped**) | **28096** | **24582** |

The column set is **fully complement-closed** (28096 of 28096 have their
complement present), which is what lets coverage be quoted in pairs.  Only
**2** of the 24582 essential columns are affine, so this is not a family of
parities with a few extras — it is overwhelmingly nonlinear.

Against 4294642034 fully-essential five-input tables that is **0.00057%**.
The counting argument stands exactly as written: no constant factor on the
suffix axis closes a gap of that order, and `n == 4` really was the last
arity where a flat family covers a real share.

**What ships anyway.**  A miss falls through to the searches, so admitting
the arity cannot cost coverage.  The only obstacle was mechanical: the
whole-arity spelling will not build a `2**32`-entry dict.  So five inputs
derives **table-major** — the same loops in the same order, with `wanted`
narrowed to the one table and its complement (`_STAGED_ARITIES`).

The flagship is five-input XOR: this file records XOR as the table the
searches fail on, and at five inputs a fully-essential table has *no* search
that reaches it.  It **builds in 3.8 seconds and prints all 32 rows on the
shipped interpreter**, search-free, from a 259-character template.

The cost is the trade this makes.  At `n <= 4` the enumeration is paid once
per process and every later table is free; here it is paid *per table* —
143 seconds for a table the family misses, and far less for one it reaches,
since a hit stops the enumeration where it lands.  Measured through
`_derive_staging`: 143.0s for a random fully-essential miss, against 3.7s for
five-input XOR and 0.6s for five-input AND, both of which sit early in the
enumeration.  So the quoted arity cost is the *miss*, not what a reachable
table pays.

The shipped caps are carried over from four inputs and are **unmeasured at
five**; they are constant-factor headroom and do not change the story above.

## Composition through the pointer: refuted, with the mechanism

A construction composing sub-results through the pointer position fails
because the combine step **creates no information**.  Superseded as a route
to closing an arity, but kept because it rules out the whole
*position-decode* shape rather than one attempt at it.

**"No decode from an accumulated position" — the exact content.**  A mux
needs a selector read then a cofactor read.  With the cofactors planted as
their pre-images (`p0 = NOT f0`, `p1 = NOT(f1 XOR p0)`, inverting the walk's
prefix-XOR) the second read is **correct in all eight rows** — it sees
exactly `f_v`.  The chain works.  What fails is the readout:

```
ptr after the chain = entry + v + answer
```

`v` and the answer are *summed*, so position cannot separate `(v=0, ans=1)`
from `(v=1, ans=0)`.  That is the whole of the recorded claim, and stating it
this way also names the escape — a later read of a cell holding `NOT v` makes
the displacement `answer + 1`.

**Two negatives that are forced and prove nothing**, recorded so they are not
re-run as evidence:

- A **static band** cannot cancel the displacement (all 256 patterns, every
  tail walk, one and two reads: zero).  This is a theorem: two rows converged
  on one position, with an identical static band ahead and a rightward-only
  tail, execute identically forever — `[` touches only `ptr + 1` and nothing
  looks behind.
- A **uniform live `NOT v` band** also fails, for a narrower reason: the value
  a read sees is `NOT(planted XOR running-prefix)`, and the prefix depends on
  the debris each row crossed, so the pre-image needed is **per-row**.

**The verified two-stage chain, and why it still fails.**  Carried to 42
configurations in which the stage-2 selector arrives as `v` and the stage-2
read sees `f_v`, asserted in all eight rows rather than assumed.  Both
products stand — `v AND f1` and `NOT v AND f0` — and columns depending on all
three variables appear.  The mux appeared to stand as well, and **it does
not**: in all 7 such configurations the per-row solver had planted a
`v`-dependent value at the very cell being read back (`11001010` at cell 29 —
the mux complement, re-complemented by the crossing).  The chain was *handed*
the answer.  Forced to a uniform function of `(f0, f1)` — something an embed
could produce — the mux vanishes under every plant rule tried.

So a selecting walk yields **one product**, never both and never the mux,
because the read consumes the selector into the pointer.

**A chain is not a suffix the enumeration can emit**, so "a chain is just a
suffix string over the same alphabet, hence governed by the same flat-pool
count" is wrong.  `_stagings` emits one uninterrupted run from `_BASE - 1`;
a chain walks to a *chosen* cell, reads, walks a chosen gap, and reads
again.  Its coordinates are `(separator, settle, k, cell, read1, gap, read2,
accumulator, orientation)` — a strictly larger pool that no `'[' * k` and no
single-insert suffix spells.

**The question that matters is the printable set, not the standing set.**
"Which chain leaves the answer sitting in a cell?" has answers, and every
one dies on the walk out.  "Which chain leaves a tape the ordinary endgame
prints correctly?" is different and does not require decoding position at
all — it reshapes the tape so the existing print route lands.  A sweep of
125440 chains against 400 unreached four-input tables printed 78 (19.5%,
78/78 interpreter-verified), extrapolating to roughly 39% coverage — not a
measurement of the whole space.

**What survives.**  The mux analysis above is still correct about what it
examined — `ptr = entry + v + ans` does sum the selector with the answer —
as a statement about position-decoding, and false as a statement about
chains in general.  The counting argument still governs the *staging
family*: nothing here raises what `_stagings` reaches, and four inputs was
not total from this alone — it needed the sculpted route.  The chain pool
is itself finite and fixed-size, so it does not obviously close another
arity.  Not shipped; the sweep and verification scripts are gitignored
working files (`notes/minifuck_chain_sweep.py`, `notes/minifuck_chain_verify.py`).
