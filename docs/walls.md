
# Generator and transpiler negative results

The full arguments behind the blocker tables in
[`docs/limitations.md`](limitations.md): what a generator provably cannot
do, and what merely looked that way.  Completed constructions — the working
generators and how they work — live in the source and the commit history,
not here.

Two kinds of entry, and both bind future work:

- **Standing walls.**  A negative result plus the structural reason it
  cannot be lifted.  6-5's label budget, ROTfuck, 3x, Dotlang, 2dFish.
- **Refuted approaches.**  A mechanism that provably does not work, or a
  search whose negative was an artifact of how it was asked.  These stop a
  future attempt spending the same round twice.

A cap that fell is kept only where the *shape* of the failure still guides
a search — the recurring lesson being that an enumeration cap is evidence
about the enumeration, not about the language.  Where a cap simply no
longer exists, `docs/limitations.md` records the current status and the
history is in git.

## 6-5 (35 branch labels bound the tree)

**The 35 comes from the language, not from the generator's encoder.**  The
[wiki spec](https://esolangs.org/wiki/6-5) defines operand notation as:

> Numbers beyond 9 denoted using letters. (A=10, B=11 etc.)

Letters are `A..Z`, so the operand alphabet is `0..9` then `A..Z` and the
largest value an operand can name is **35**.  A `8n` jump names the n-th `4`
marker, so 35 is the highest marker index any jump can reach: markers past
that exist in the program text but are unaddressable.

**Labels cannot be reused, so the budget is a total-nodes count and not a
live-set one.**  This is the piece a resource argument needs and it holds on
the interpreter's own semantics: `8n` resolves its target by scanning the
token list *from the start* and counting `4` tokens until it reaches the
n-th.  A label is therefore a global ordinal fixed by position in the
emitted string — not a name bound in a scope, not a nearest-match, and not
something a subtree can consume and free.  Two distinct jump targets need
two distinct ordinals for the whole life of the program, so the tree cannot
recycle a label once its subtree is finished.  The bound is `2**n - 1`
standing nodes against 35, not tree depth against 35.

Given both, the generator is a decision tree that folds its constant
subtrees, one label per internal node the fold leaves standing.  That makes
the limit a property of the *table*, not of `n`: the fold's worst case is an
alternating table, which folds nothing and spends `2**n - 1`, so the tree is
total through `n == 5` (31) and begins refusing at `n == 6` (63).  Tables
that fold hard still render at any width — AND-`n` needs only `n` labels.

An arithmetic-kernel alternative (embedding the table as a single integer,
at O(`2**(2**n)`) characters behind a ~2 MB setup guard) never covered a
table the tree could not: a buildable `T` confines the ones to low indices,
which leaves the rest of the table constant, which folds well inside the
label budget.  Not worth building for that reason.

### The attack that does not work: operands past `Z`

This wall was once overturned and the lift was **reverted**.  Recording the
attack so it is not retried: this repo's interpreter decodes an operand as

```python
def num(char: str) -> int:
    if char.isdigit():
        return int(char)
    return ord(char.upper()) - 55
```

which is unguarded arithmetic over *any* character, so `[` reads as 36, `{`
as 68, and DEL as 72.  Padding with inert `4`s (a no-op the marker scan
still counts) bridges the values no character names, and on that basis every
table renders at every `n` — parity at `n == 6/7/8` builds and executes
correctly on all `2**n` inputs.

**That is undefined behaviour, not a language property.**  The spec says
*letters*, and `[`, `{` and DEL are not letters.  Three tells:

1. `num`'s own docstring states a *narrower* contract than even `A..Z`:
   "Decode a 6-5 operand digit: 0-9 literal, A-F hexadecimal."
2. The decode is not injective outside the letters — `num("a") == num("A")
   == 10` via `.upper()`.  The "unnameable" values 42–67 that padding had to
   bridge are exactly that case-folding: a formula running outside its
   intended domain, not a designed gap.
3. Operands are unvalidated and not bounded below: `num("\n") == -45`,
   `num(" ") == -23`.  Nothing rejects them.  Depending on values above 35
   is depending on the *absence of validation*.

The shipped examples (`examples/hello-world/6-5.txt`,
`examples/boolean/6-5.txt`) reach a maximum operand of 8 and are entirely
alphanumeric, so no ground-truth example exercises the region — and this
repo's convention is that examples are ground truth and prose governs where
examples are silent.  Both point the same way.

The methodological lesson is worth more than the result: **executing a
generated program proves nothing when the interpreter it runs on is the
thing in question.**  The lift's verification passed on all `2**n` inputs at
`n == 6/7/8` precisely because it ran against the permissive interpreter
that admits the undefined region.  Execution is only evidence against a
*conforming* interpreter.  See `docs/limitations.md` for the interpreter
conformance gap this exposed.

## 3x (constant-bit guard skip is unsafe)

A guard that separates differing rows from default rows sharing the same bit
prefix cannot have a "redundant" bit test dropped, because the default rows
share the prefix too — dropping the test would misclassify them.  The sibling
idea (pre-negating stored input bits to halve `not_bit`) remains open but is
marginal.

## Minifuck (both caps fell; the generator is total)

Two caps this file used to record have both fallen, and the shape of each
failure is the reusable part.

**The runtime-read cap is false.**  It said a *reading* generator reaches
only the four one-input functions plus the eight 0-preserving two-input
tables.  A reading construction builds and verifies all four one-input and
**all sixteen** two-input tables on the shipped interpreter, with clean
`"0"`/`"1"` output and exactly `n` reads per run.  The original searches
missed it because they were **length-bounded** (no complemented read-prefix
to length 11, full-program search to 14, re-verification to 34) over *bare
programs*, while the construction is 88-148 characters — a read/re-zero
prologue composed with the tree and endgame, outside every one of those
bounds.  An enumeration cap is evidence about the cap, not about the
language.  The mechanism the cap rested on is real but escapable: each read
leaves ASCII residue in the pool, and a re-zero gadget after each read clears
it while the bit survives as a pointer offset.  Two gadgets are needed — one
searched from blank tape re-zeroes only the *first* read, since after a bit
is banked the tape is populated and later reads need a gadget searched from
that frontier.  `examples/boolean/minifuck.txt` is the only committed record
of this model; the shipped generator is parameterized instead.

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

### The termination convention is not available

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

#### Is `_mux` total?  Every refusal site closes by argument, and the gate is gone

The arity tuple was a **verification gate, not a structural cap**, and it has
been removed on the strength of what follows.  Nothing in the construction
reads `n` except `_mux_weights`, `_mux_pad` and `_mux_start`, all closed
forms defined for every `n`.  XOR builds at every arity tried through seven
— 243, 429, 622, 2511, 9565 and 39915 characters at `n` of 2 to 7.  **448 of
448 rows correct** on the shipped interpreter, sampled across `n` of 5, 6
and 7 (XOR and random tables).

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
binding constraint is cost rather than expressiveness, template length growing
about fourfold per arity (a rewind costs `3K+1` characters with `K` on the
order of the `2**n` span, across up to `2**n` rounds).

**The arity gate is gone, and the generator is total.**  `_MUX_ARITIES` was a
verification boundary and nothing more; widening it needed no new construction
and no new check, because the three arguments above hold at every `n`.  What
it still owed was *execution* — the arguments say the construction cannot
refuse, and this repository's standing rule is that a claim about a generated
program is worth what its run on the shipped interpreter is worth.  That has
now been paid, so the tuple has been replaced by the floor `_MUX_MIN_ARITY =
2`, which exists only because `_solve` routes constants and one-input
projections to `_degenerate` before the route is reached.

A six-input table with a *narrow essential core* builds fine even under the
old gate — it projects down to an arity inside the tuple — which is why
"does `n = 6` build?" has to be asked with a fully-essential table to mean
anything.  There is now no arity, and no table at any arity, that the
Minifuck boolean generator declines.  The *cost* curve is what now bounds a
caller — about 0.14s a table at five inputs, 40s at six, and 820s at seven,
where the template reaches 13685 characters.  The `2**n` growth is in the
sculpting: a rewind costs `3K+1` characters with `K` on the order of the
`2**n` span, across up to `2**n` rounds.

**The two measurements the module cites.**  Execution: **448 of 448 rows
correct** on the shipped interpreter at five, six and seven inputs, which
is the run behind the totality claim — the argument says the construction
cannot refuse, and this repository's standing rule is that such a claim is
worth what its run is worth.  Coverage before the sculpted route closed
the arity: complementing inputs as they land took four inputs to **60942
of 64594 (94.35%)**, and that residue is what the sculpting was built to
attack.

### `n == 5` ships partially; full coverage is out of reach of any flat family

A flat pool of columns cannot cover a real *fraction* of five inputs — that
counting argument is sound — but it does carry a measured sliver, now
derived rather than searched for.

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

**What ships anyway.**  Partial coverage is worth gating on for the same
reason it was at four inputs — a miss falls through to the searches, so
admitting the arity cannot cost coverage.  The only obstacle was mechanical:
the whole-arity spelling will not build a `2**32`-entry dict.  So five inputs
derives **table-major** — the same loops in the same order, with `wanted`
narrowed to the one table and its complement (`_STAGED_ARITIES`).

The flagship is five-input XOR, and it is the pointed case for the same
reason four-input XOR was: this file records XOR as the table the searches
fail on, and at five inputs a fully-essential table has *no* search that
reaches it.  It now **builds in 3.8 seconds and prints all 32 rows on the
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

### Composition through the pointer: refuted, with the mechanism

A construction composing sub-results through the pointer position fails
because the combine step **creates no information** — this is superseded as
a route to closing an arity (see "Four inputs is closed" above), but the
mechanism is worth keeping since it rules out the whole *position-decode*
shape rather than one attempt at it.

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

## 123 (parameterized; wider arities gated on cost, not expressiveness)

**Resolved.  All four one-input and all sixteen two-input tables build, and
the generator ships** (`esolangs.tools.boolean.one_two_three`).  The bound
that looked like a language ceiling belonged to a setter choice instead.

**The setter is a free parameter, and that is the reusable lesson.**  The
displacement-neutral `12`/`21` pair keeps every instantiation in position
lockstep, so a set bit can only add a pass and never remove one, the looping
set is upward-closed, and the computed table is monotone by construction —
a survey of 1428 templates under that pair found only monotone tables, which
is exactly what it predicts.  The **±1 fill** (`1` for a one, `2` for a zero,
one character each, so nothing leaks through `len()`) displaces the pointer
*oppositely*, breaks position lockstep, and voids the monotonicity
hypothesis.  All sixteen tables follow, XOR, XNOR, NAND and NOR included.
The ±1 setter had been considered and rejected for the **printing** route —
"instantiations drift apart by bit count and never print together", true
there and irrelevant to the termination route, where nothing has to print.

**The mechanism is a counter modulo four.**  Displacement after the embeds is
`(#zeros - #ones)`, the `-4 -> 0` wrap reduces it mod 4, and a tail of `1`s
decodes it: `{X0}{X1}` followed by `k` ones computes a function of the input
*popcount* alone — rows `01` and `10` always agree — sweeping XNOR at
`k == 2` and XOR at `k == 4`.  The asymmetric tables use `3`, whose
TRUE-backward jump re-runs the preceding segment and makes the pass count
input-dependent: the one non-affine operator in the language.

Two constraints shape the shipped plans.  Every looping row is a **proven
state revisit**, never unbounded growth — `run_until_halt_or_cycle` does not
return on a program whose pointer marches right forever, so such a row would
hang the harness rather than report a 1.  And every plan emits its slots in
name order with each `{Xi}` once.

### Language facts worth keeping

- `3` on a TRUE/FALSE bit jumps to the *nearest* preceding/following `3`, not
  a bracket-matched one, so the only constructible pattern is "repeat the
  region before the `3` while TRUE" — never a jump to an independent branch
  target.
- `3` is a control-flow no-op at `pos < 0`, though it still shifts
  instruction positions, which is what desynchronizes naive splices.
- A program ending with `pos >= 0` restarts from ip 0 with the tape intact
  and the input cursor advanced, so one `2` at -3 can read a different byte
  on each pass.
- A TRUE `3` re-runs only back to the *previous* `3`, so a read placed before
  that `3` is never re-executed; the desync applies within a segment.
- Under `1` the positions `0, -1, -2, -3` form a **4-cycle**, so a row that
  drops below zero circles rather than settling.  The only rightward escapes
  are `2` at `-3` (reads stdin, fatal for a parameterized program), `2` at
  `-2` (prints), and `2` at `-1` (the sole free exit).

## NoComment's arity cap (the 255 bounded one jump, not a composition)

The blocker table used to record `n <= 8` as a "genuine wall: the `s` skip is
byte-indexed, capping every jump at 255."  That does not survive: **255
bounds a single skip, and skips compose.**  The cap was a property of the
generator's decode, not of the language.  It is now `n <= 11`, and what binds
there is the tape.

### What actually broke at nine inputs

The old construction computed the input's numeric index into one cell, then
spent a single `s` skipping by that index into a staircase of `2**n` `l`
moves, landing on a pre-loaded cell holding `48 + table[index]`.  Two
separate things break past `n == 8`: the index itself exceeds a byte and
wraps mod 256 (`2**9 - 1 == 511`), and each bit's guarded contribution adds
`2**w` in unary, so from `w == 8` the guarded *block* is longer than the 255
its own skip can cover.  Neither is a statement about NoComment; both are
statements about using exactly one skip for a job.

### The two compositions

The properties this rests on are in the **wiki's own words**, which matters
because a lift that only works where an implementation is more permissive
than its spec is undefined behaviour, not a capability.  The wiki gives `s`
as "If the value of the pointer is non-zero, **peek (do not pop)** a value
from the stack ... and jump x spaces forward", and describes memory as "A
static, flat memory space **divided into bytes**".  So the peek is specified,
the pointer is never said to move during a jump, and the byte-sized cell is
exactly where the 255 comes from.  The spec states no limit on jump distance
or program length.

**Chained guards — a guarded region may be any length.**  After a skip fires,
the guard cell is still under the pointer and still nonzero, so it can be
tested again immediately.  A guarded region of length `L` is emitted as
`ceil(L / 255)` chunks, each preceded by glue that rebuilds that chunk's
length in a scratch cell, pushes it, returns to the guard, and skips.  The
glue runs on *both* paths, so it can only be emitted from one position —
which is why every chunk must end with the pointer back on the guard.  A
700-command guarded region was run through the interpreter on both the taken
and untaken paths and behaved as one guarded block.

**Additive staircases — a displacement may be any size.**  Entering a
staircase of `L` copies of `l` by skipping `c` executes `L - c` of them, so
pre-walking `L` right and then skipping `c` is a net move of `+c`.
Displacements *add* across consecutive staircases, so an index far past 255
is reached by `q` stages whose skip amounts sum to it.  Crucially the index
splits into **summands, not digits**: each summand is a plain sum of per-bit
contributions, so no rescaling by 256 is ever needed — which is what kills
the obvious "high digit needs a `hi * 256` skip" dead end.

Between stages the stack top must advance, and `f` is the only pop — it
writes the popped value into the cell under the pointer.  That clobber is
survivable because it lands mid-corridor, but only with a **constant**
trailing summand of `1`, so the final landing is strictly right of every
clobbered cell.  Without it the all-zero input lands exactly on a clobbered
cell and prints the popped summand instead of the answer.  That input is the
canonical failure of this construction, worth keeping in mind for any
re-derivation.

### What binds now, and why it is not a wall either

The layout needs `2**n` output cells, plus an apron of nonzero cells past the
table for the stages' guards to land on, plus the walk's own reach.  The
tape defaults to 4096 cells, so `n == 12` needs cell 4650 and is refused.
The wiki *does* require the memory space to be static — pointer overflow is
defined as moving to the opposite end, which a tape with no ends could not do
— but it never gives a size, so 4096 is this interpreter's choice.  That
makes this a configuration bound in the same sense as the Factor row's
`sys.get_int_max_str_digits()`.  Both `nocomment(table, tape=...)` and
`run(code, io, tape=...)` take the size; `n == 12` builds and runs correctly
at `tape=16384`.  The default stays put because the size is *observable* —
cell 0 steps left to `tape - 1` — so moving it would change what existing
wrapping programs do.

### Evidence

`n <= 8` still takes the original single-skip path and renders
**byte-identical** programs.  The wide path was checked by running every
generated program through the interpreter: at each of `n == 9`, `10` and
`11`, five tables (alternating, parity, a random dense table, constant zero,
AND-`n`) were evaluated on **all** `2**n` input combinations, and every
output matched.  The tests derive the cap by asking the generator where it
stops rather than pinning a literal, so the bound tracks the tape.

The construction was also audited against the spec's *domain*, since a green
execution gate proves nothing when the construction is built out of the
interpreter's own non-conformance.  Instrumenting every executed step over
every input at `n == 9`, `10` and `11` shows the largest skip amount ever
peeked is **255** and the largest value ever written is **255** — the
construction lives strictly inside the byte, composing many legal skips
rather than needing one illegal one.  No generated program contains a
non-command character, pops an empty stack, jumps outside the program, or
wraps the pointer past either tape end.

This is the same shape of error as two others on record: `%^2^-1`'s NOT needs
36 commands so a length-8 sweep missed it, and ZTOALC's positional-index wall
fell to `s += s` because the sweep only searched trees.  In all three the
claim bounded one primitive and was read as bounding what could be built out
of it.  The discipline that separates these from a false lift is the one
applied above: name the spec text the construction depends on, and check that
nothing executed leaves the region that text sanctions.

## NoComment, BF-PDA (a `{Ci}` embed was not actually needed)

Both generators previously embedded a second placeholder (`{Ci}`) alongside
each bit (`{Xi}`), reasoned as "the if/else branch needs a gate that is
nonzero exactly when the input bit is zero, and neither language can
compute that complement at runtime."  That reasoning does not survive
closer reading of either instruction set:

- **NoComment**: `s` skips the next fixed-length block *iff the tested cell
  is nonzero* — which makes the *skipped* block a "run iff zero" gate, i.e.
  a NOT gate, for free.  A short prologue tests each raw bit cell with `s`
  and increments a fresh complement cell inside the skipped block, so
  `comp_i = 1 - bit_i` is computed once per input at runtime from the
  embedded `{Xi}` alone.  Both the skip path and the fall-through path end
  with the pointer back on the bit cell (the guarded block's last move),
  so the next bit's prologue starts from a known position — the same
  convention the rest of the generator already uses for its guarded
  increments.
- **BF-PDA**: the `{Ci}` push was never actually read *as a value*.  Tracing
  the generated control flow shows the one-arm (`[ > sub1 < ] >`) is
  entered and exits via a fresh `0` push that also pops the guard; the
  zero-arm is reached only because, when the one-arm is skipped, the
  *un-consumed bit itself* gets popped by the trailing `>`, exposing
  whatever was pushed just before it as the new top.  That value only
  needs to be truthy there — it never depends on the bit — so a constant
  `1` marker (`<@`, embedded directly in the template, not through
  `{Ci}`/`instantiate`) is correct.  Verified against the interpreter: a
  constant-`1` marker reproduces every table through `n == 3` exhaustively
  and `n == 4` spot checks; a constant-`0` marker (the discriminating
  negative control) fails on every combination with a zero bit, pinning
  that the marker must be truthy but confirming its *value* was never
  input-dependent.

Both generators now embed each input exactly once, with no `{Ci}`, matching
Eval and every other parameterized generator: the exactly-once rule holds
without exception.

## Dotlang (removed: its boolean construction could not embed each input once)

A plain decision tree fails on Dotlang: `W~` warps to the *first* `W<name>`s`
marker, so deeper levels re-enter the same markers and lose branch history;
the type conditionals (`!?:`) cannot help — input digits become `int` 0/1,
so both bits share a type — and there is no value comparison or arithmetic.
Worse, Dotlang has no storage at all (no register, tape, or accumulator to
hold a bit and re-read it), so *no* once-embedding boolean generator exists:
a bit has to be re-embedded at every junction that tests it.

The generator resolved the wall by forking: ``(`` spawns a dot at the
matching ``)`` while the caller continues, so a junction forks the dot into
two and the embedded gate (``{Xi}`` or its ``{Ci}`` complement, filled with
a pass-through ``a`` or an empty cell) kills one of them, leaving exactly
the branch the bit selects.  The survivor turns down and right into its
subtree, and each leaf is a ``#0#``/``#1#`` literal that prints the table
entry before the dot dies.  The tree re-embedded each input at `2**i`
junctions — the only parameterized generator that did not embed each input
exactly once.

The language was removed: that re-embedding (and the ``{Ci}`` placeholder it
needed) is the workaround for having no state, and the text generator is a
plain literal-embed, so Dotlang was too thin to justify being the sole
exception to the exactly-once rule.  The construction is recorded here as a
negative result so the assessment is not redone.

## Polynomial (numeric root-finding ruled out; caps at 138 instructions)

The generator emits exact integer polynomials whose coefficients far exceed
float64's exact-integer range (2**53) once a few instructions accumulate —
`'Hello, World!'` has coefficients up to 10**95 — so every floating-point
solver (high-precision `mp.polyroots`, companion-matrix QR, change-of-scale)
silently solves the wrong polynomial, and a residual-based gate cannot work
(the ill-conditioning ~1e16 makes wildly wrong roots look right).  The
interpreter factors the monic integer polynomial over Z with sympy instead.

That exact factorization defines the boolean generator's practical bound,
but the bound is on **instructions, not inputs** — each instruction consumes
a fresh prime, so the degree (and the factoring cost) tracks the instruction
count, which is what `_POLYNOMIAL_MAX_INSTRS = 138` caps.  An earlier `n <= 4`
gate measured the wrong thing: it refused parity from `n == 5` even though
parity needs only 13 instructions per input.  The generator now builds both a
decision tree and a residual-merge state machine (an ordered BDD, merging any
two prefixes with the same residual subfunction rather than only constant
ones) and emits the shorter, which makes the real bound visible — parity
renders through `n == 8` at 106 instructions, while random dense tables,
whose residuals do not merge, start refusing at `n == 6`.  So a table that
collapses to few states renders at any width; what is capped is the ones that
do not collapse.

## ROTfuck (rotation defeats a decision tree)

The rotation defeats a brainfuck decision tree outright: a `[ body ]` whose
body is a rotation-encoded loop cannot work, because when the `]` fires its
`[` has rotated away (the skip-path seek needs `q ≡ p+1` while
re-convergence needs `q ≡ p`).  The shipped boolean generator sidesteps the
wall by never looping (a phantom-`]` block whose straight-line body is
position-encoded), which keeps the generator total but makes the programs
long (O(`n·2**n`) blocks, ~1.4s/execution at `n == 4`).

## Assessed boolean candidates that fell through

- **%^2^-1** (wall at `n >= 2` for the *reading* model, machine-checked —
  **resolved by parameterizing**).  Its only control flow is `t`, which
  rewinds to the program start when the accumulator is nonzero, preserving
  the accumulator across the rewind.  There is no forward jump and no way to
  branch over code, so a program cannot route two inputs to different tails.

  **The wall and its scope.**  The full argument is in
  [`docs/proofs.md`](proofs.md); it proves
  `computes_ignores` — every program meeting the boolean contract (halt
  cleanly, consume both bits, print one character) computes a function that
  ignores one of its two inputs — so `no_xor` and `no_and` follow.  Two
  structural facts drive it: `n` *overwrites* the accumulator, so the state
  at the last read is a function of the last bit alone; and `t` jumps only to
  position 0, so a run that halts must have input enough for every read ahead
  of the cursor (`count_le_of_halts`), which forbids the two runs from
  diverging at a `t`.  Output therefore factors as `A(b1) ++ B(b2)`, and a
  one-character output forces one factor empty.  This is an induction over
  unbounded length, not a bounded search: the axiom audit reported only
  `propext`, `Classical.choice` and `Quot.sound` — no `sorryAx`, no
  `native_decide`.

  **Parameterizing voids the proof's hypothesis.**  No `n` ever runs, so
  nothing overwrites the accumulator and the "state at the last read depends
  on the last bit alone" step has no object to apply to.  The construction
  needs *no branch at all*, which is what lets it fit a language whose only
  jump target is position 0.  Three interpreter-checked properties carry it:
  `l` prints the accumulator in **decimal**, so an accumulator holding 0 or 1
  prints `"0"`/`"1"` and the answer never has to be routed to a print site;
  command strings compose as affine maps (`p` negates, `'` zeroes, `m`
  doubles, `s`/`i` translate), so chaining one per input makes the
  accumulator a *product-weighted* function of the bits; and the over-3003
  reset fires before every command, including the `l` that prints — so a
  value above the limit prints as `0`.  (Nothing shipped relies on that: see
  the tail note below, where the reset is measured *not* to separate.)

  **The nonlinearity is load-bearing.**  A purely *additive* weighting gives
  each row a distinct consecutive value, and every affine-plus-clamp tail is
  then monotone in the row index, so `{00, 11}` can never be split from
  `{01, 10}` — a 3M-vector BFS over that family reaches only the two constant
  tables.  A later `p` negating what earlier bits contributed is what breaks
  the monotonicity and reaches XOR.

  **All four one-input functions are expressible**, which an earlier length-8
  search missed: NOT is `nss` + `i` * 31 + `pe` (36 commands), computing
  `x -> -x + 97` so that 48 -> 49 and 49 -> 48.  Building the additive
  constant out of `s`/`i` needs ~20+ commands, well outside a length-8 sweep.

  **The three-input cap was the padding, not the language.**  Coverage at
  `n == 3` went 48/256 -> 86/256 (and 154 -> 496 at `n == 4`) — later to
  106/256 with the ladder, and finally to 256/256 with the band construction,
  both below — by adding a third construction that composes one affine
  setter per input and *searches*
  the composition, rather than reading one slope per column as the two-input
  derivation does.  XOR3 builds, which is no subcube.  What had actually been
  refusing it was a width rule: both branches of a setter must be equal width
  or the program leaks its inputs through `len()`, and `_pad_pair` pads with
  `pp`, which closes only *even* gaps.  Parity-3's witness wants branches of
  width 6 and 5, so it died on an odd shortfall — with a printable tail
  (`pssssspl`) already in hand.  Spelling both branches at a width they share
  closes it; 99 of the 100 maps in the grid have spellings of both parities.
  Two search-design notes, both of which cost a wrong answer first: the state
  space must be deduplicated by the **partition** a vector induces on the
  input combinations, not by its values (a value-keyed sweep did not finish,
  and a value-*capped* one reported 14/256 — below what the cascade already
  builds, the signature of a forced result); and the composition indexes
  inputs least-significant-first while a truth table is most-significant-first,
  a bit reversal that presented as inverted outputs on setters that did not
  even differ, and accounted for all 68 initial verification failures.

  **The reset is not a separator, and the tail bound now has a reason.**  An
  earlier note here described the over-3003 reset as "an implicit comparator
  the endgame uses to fold a parked zero-class onto 0"; the shipped
  `_tail_for` in fact never reaches it, and its own docstring records that the
  amplify-then-clamp shape "never once fired".  The reset cannot separate:
  every command acts uniformly on the accumulator, so `s`/`i` translate all
  rows alike and `m`/`p` scale them alike, and the reset merges a class onto 0
  without ever splitting rows that agree.  A BFS over *value-vectors* rather
  than program strings found no tail separating three or more values to depth
  14, and the reset was instrumented as firing 1148–7020 times across ~43–55k
  explored states — so that zero is a real negative and not a search of dead
  code.  The affine path's own reach is likewise measured rather than assumed:
  84/256 alone, unchanged by widening the multipliers to `±4`, the offsets to
  `±16`, the spelling depth to 9, or the witness count to 16.  The 88 that the
  shared-cofactor law admits is **not** a ceiling on this path: that law is a
  necessary condition on the *last* input alone, and the search reaches 32
  tables it does not admit while missing 36 that it does, so the two sets
  cross rather than nest.  The bound on the affine path is therefore measured
  and not derived, which is why 84 is reported as where every widening tried
  stops rather than as a proved maximum.

  **Majority-3 is reached, and this entry's argument for its being out of
  reach was wrong.**  The entry closed by saying that what is needed is "a
  running total that survives a gadget that erases, and there is one
  register" — correctly labelling itself evidence about a layout rather than a
  wall.  The register is enough, because the running total does not need to
  survive a gadget: it can *be* the accumulator, and the over-3003 reset can
  read it.  A fourth construction, the **threshold ladder**, gives each input
  a weight, subtracts it into a negative accumulator, and lets the reset fold
  every row above the limit onto 0.  That is a threshold on a weighted sum,
  which is exactly a majority; coverage at `n == 3` went 86/256 -> **106/256**
  (and later to 256/256, see below),
  majority-3 among the twenty added, at 598 characters and executed on all
  eight rows.

  This does not contradict "the reset cannot separate" above: the reset
  still cannot separate rows that agree — it merges, and the ladder
  supplies an order for it to merge along.  The separation is done by the
  weights before the reset ever fires.

  Two things the construction turns on, both of which cost a wrong answer
  first.  Stage one must stay **nonpositive**, since the reset never fires on
  a negative accumulator and that is what makes the stage exactly affine; a
  positive intermediate crossing 3003 clamps at the *next* command, which
  silently produced a program computing the wrong function.  And the
  stage-one vector must be obtained by **running the emitted characters**
  rather than by solving the arithmetic separately: a `pp` hold negates, so a
  magnitude past the limit clamps to 0, and a model that assumed
  `-(base + Σ w·b)` disagreed with the interpreter on exactly the rows where
  it mattered.  Modelling and emitting were reconciled by making the search
  call `_apply` on the code that is actually emitted.

  What bounds the *ladder* is stated rather than guessed: one reset is one
  threshold, and only **104 of the 256** three-input tables are linearly
  separable, so no widening of the ladder grid can make that shape total.
  That bound is about the ladder, not the language.

  **Three inputs are now total — 256/256 — and the lever was the printing
  command.**  Everything above prints with `l`, which spells the
  accumulator in decimal and so needs it to *be* 0 or 1.  `e` prints
  `chr(acc & 0xFF)`, so a row only has to be **congruent** to 48 or 49 mod
  256, and with residues as the target the reset can be used repeatedly.
  The **band construction** weights each input by a multiple of 256 (so all
  rows start congruent), sorts the rows by the weighted sum — turning the
  table into runs — and clears one run per stage from the top, since the
  reset only wipes the largest values.  Survivors are parked back *under*
  the limit between stages; parking them negative stops drift but also
  stops the next clamp, which is the bug that cost a rewrite.

  Nothing is searched.  A wiped band thereafter receives the same
  translations as the survivors, so the parking amount cancels out of their
  residue gap and each stage's translation is fixed by one congruence,
  `U ≡ (live − band) − v (mod 256)`.  Each cut's window is one full residue
  system wide, so exactly one translation in it qualifies — which is why an
  earlier sweep of a window found precisely one working candidate in about
  two thousand.  Stage counts follow the run structure exactly:
  2/14/42/70/70/42/14/2 tables at 0–7 stages.  Programs run 8257–14959
  characters against the ladder's hundreds, so the path is tried last, and
  all 256 are interpreter-verified on every row at equal fill length.

- **Is the `%^2^-1` fold total?**  **No, and where it stops is the ladder's
  footprint rather than the plan search.**  The
  generator refuses generic tables from ten inputs on, and the refusal reads
  like the search giving up: the descent dead-ends 354 moves in with 420 of
  514 points still unmerged, nowhere near its 4128-step budget.  It is not
  the search.  Rows start at `-step * r`, so the ladder spans
  `step * (2**n - 1)`, and the emitter lays it from a **zero accumulator** —
  so the ladder has to fit inside `[-3003, 0]`.  `_fold_at` was gating on
  `2 * _LIMIT`, which is the span a *relative* plan state may occupy
  (`_fold_moves` allows 6006 because a state may sit anywhere in the
  workspace), and that let the planner spend thousands of moves on geometry
  the emitter refuses on its first op.  The alternating eleven-input table
  planned 2833 ops and then asserted, which is how the mismatch surfaced.

  Gated correctly, the boundary is exact and arithmetic.  At the shipped
  spacing of 4 the footprint is 4092 at ten inputs, over the workspace, so no
  such table could ever be emitted however long the planner ran.  Halving it
  (`_FOLD_NARROW_STEP`, tried only when the wide ladder finds no plan, so
  every template that already builds stays byte-identical — verified over a
  312-table corpus) gives 2046, which fits: **ten inputs build and print every
  row on the interpreter**, three random tables at 1024 rows each plus
  nine-input samples, one instantiation width per template.

  `2a + 3b` spells every amount except 1, so a *uniform* step of 1 is
  unspellable and two is the finest uniform ladder.  A related spelling fact
  fell out of the same work and is worth recording, since `_pad_pair`'s
  odd-gap refusal keeps reappearing in this module: **the identity has no
  odd-width spelling at all**, searched exhaustively over `s`/`i`/`p`/`m`
  through width 6.  An odd number of the only sign-flipping command cannot
  compose to `+0`, so a one-character `"s"` branch can never be padded to
  match a hold; the narrow ladder's last setter is respelled wider instead
  (`iipssp` against `pppppp`).

  **Ten is not a structural end; the false assumption was the word
  *uniform*.**  Rows must be *evenly* spaced is false — they need only be
  **distinct** — two rows sharing a value are merged by the first cut
  reaching them and can never be separated — and distinctness is far cheaper
  than uniformity.  The floor is exact: the `2**n` subset sums are distinct
  non-negative integers, so the largest is at least `2**n - 1`; the minimum
  weight is 2, so nothing sums to 1, and by symmetry nothing sums to `S - 1`;
  two values inside `[0, S]` are unattainable, giving **`S >= 2**n + 1`**.
  The ladder `(2, 3, 4, 8, 16, …, 2**(n-2))` meets it exactly — 2 and 3 cover
  the small residues a doubling ladder cannot reach without a weight of 1,
  and the powers above behave like a binary code.  Eleven inputs cost 2049
  where the uniform ladder wanted 4094, and **eleven inputs build and print
  every row on the interpreter**.  One assumption travelled with it: on a
  uniform ladder row order *is* position order, so runs are contiguous in
  `range(2**n)`; with these weights row 1 sits below row 8, and `_fold_at`
  groups runs over rows sorted by position instead.

  **Twelve is walled for the whole ladder family, and the argument is the
  move algebra rather than the spelling.**  The doubling `m` — which this
  entry already records as the *only* way to reorder groups, since wipes
  alone cap the live spread at 3003 and leave the cyclic order invariant — is
  offered only when `spread * 2 <= 2 * _LIMIT - 2`, i.e. a spread of at most
  3002.  Any ladder laying `2**12` distinct positions spans at least 4095
  wherever it sits, so **no twelve-input ladder ever gets a doubling**.
  Measured against the standing rule that a cap is not a convergence
  argument: the search from a twelve-input start **exhausts** — an empty
  heap, not a budget — after 15 states on a random table and after 121, 24
  and 1 on the low-run witnesses, while the same instrumentation finds a plan
  at four inputs (120 states) and hits its cap at eight (17394), so the zeros
  are real negatives and not a broken probe.  Thirteen needs no algebra at
  all: `2**13` distinct positions exceed the 6007 values a `p` can address.

  Low-run tables are worth checking separately at every other arity, but on a
  packed ladder they stop being low-run: **position order is not row order**,
  so a table with three runs in row order has **2049 points** in the geometry
  the plan actually sees (r=4 gives 2304, r=5 gives 2401).  That is also why
  `_fold_construct`'s `r <= 5` skeletons essentially never fire on a packed
  ladder, where on a uniform one they are the common path.

  A **two-sided ladder** was built to test whether the workspace, rather than
  the span, was binding, and removed once measured — the same fate as the
  positive-ladder band.  Making one weight negative (an adding setter,
  `p sub(k) p`, whose inner subtraction must come out even so the `p`-repeated
  hold is an identity and not a negation) doubles the *positions* available
  to `[-3003, 3003]`, and at twelve inputs it lays 4096 distinct rows peaking
  at 2050.  It serves nothing, because positions are not the binding
  resource — the span is, and 4096 distinct integers span 4095 wherever they
  sit.  0 of 18 tables across five arities were served by it and not by the
  packed ladder.

  So the answer to "total or not" is: **total at no arity it does not
  enumerate, reaching eleven**, with `n <= 4` exhaustive and five through
  eleven executed samples.  The residual `None` is still a real one — the plan
  search could in principle give up inside the workspace, though no table at
  eleven or below makes it — so this is reach, not a totality proof.  What is
  *walled* is the ladder family at twelve, and only that family: a
  construction that does not lay all `2**n` rows before planning would not
  inherit the span bound.

  **Interleaving the laying is the open door, and it is genuinely open.**
  All `{Xi}` embeds currently precede the body, so the fold must hold all
  `2**n` rows apart at once — which is exactly the span the twelve-input wall
  is about.  Laying some inputs, folding, then laying the rest would never
  need that.  A first guess recorded here was that this cannot help, because
  merging two rows before the remaining inputs are laid merges them for
  *every* completion, so a prefix-merge needs the two rows' cofactors on the
  unlaid inputs to be **identical** — and generic tables were assumed to have
  no equal cofactors.  **Measured, that is false**: with one input unlaid a
  cofactor is a two-bit string, so there are only four of them and the 2048
  prefix blocks of a random twelve-input table collapse into four buckets —
  2044 mergeable pairs (1008 of 1024 with two inputs unlaid, 292 of 512 with
  three).  Equal cofactors are abundant, not rare.

  **Every component works, and the open question is narrow.**  The
  invariants permit it: `docs/limitations.md` states the
  rule as embedding each input **exactly once** — a count, not a placement —
  the enforced slot test only requires ascending names, and Minifuck's
  sculpted route is the precedent for machinery between embeds.  A hand-built
  interleaved template (`{X0}` `ss` `{X1}` `ss` `{X2}`) fills and runs
  correctly on all eight rows at one instantiation width, so the mechanics
  are interpreter-verified rather than assumed.

  Four components were measured, each independently:

  * **Schedule arithmetic admits `n <= 13`.**  After laying `k` inputs there
    are at most `min(2**k, 2**(2**(n-k)))` live points — prefixes rising,
    cofactor strings collapsing — so the peak is far below `2**n`: 510 at
    twelve inputs, 1022 at thirteen, 2040 at fourteen.  The binding number is
    the **span** (a wipe needs `<= 3002`, as does the doubling), and at the
    gap-2 floor those are 1018, 2042 and 4078 — so fourteen is out.
  * **Merges work.**  An early probe read an "eight-merge ceiling" off end
    spans; that was the search's route.  Long sequences merge (256 points
    over 16 classes descend to 16), and single interior merges plan in six
    ops at every size, by exhaustive search.  The per-stage `None`s that
    looked like obstructions were **beam give-ups**.
  * **Program size is fine**: ~745 merges at twelve inputs × ~3 ops at the
    shipped 72 chars/op is ~0.1-0.3 MB, beside the shipped eleven-input
    build's 187 KB.
  * **Re-tightening is solved.**  This was the real difficulty: a compaction
    leaves survivors spread over ~2200, and the next lay needs a weight
    exceeding that, so an untightened chain dies in one stage.  Gaps are
    rigid — a wipe preserves 14 of 15 gaps, choosing only its own victim's —
    and a greedy span-minimiser therefore *grows* the span on its first move
    at every size.  The trick is the opposite: **widen to exactly 3003, then
    contract at `cmin`**, a rule read straight off the working small plans.
    Derived that way it converges geometrically at ratio `(k-2)/(k-1)` and
    reaches a tight lattice in `O(k)` ops — verified at `k` = 16, 32, 64 and
    128 (251, 498, 916, 1182 ops).  An earlier controller aimed at a fixed
    absolute width, stalled from `k = 6`, and was written up as "bounded at
    five points"; that was the controller, not the algebra.

  **Chained end to end, it completes at eight inputs.**  Running the whole
  thing with the shipped move set — lay, compact, re-tighten, repeat — on
  real positions and real cofactors, asserting at each stage that every row
  still sits where its bits put it and with no idealised repacking anywhere,
  an eight-input table finishes all eight stages in about a second.  It does
  real work on the way (32 points compact to 29, 58 to 16, 32 to 4) and ends
  at **two points spanning 1**, which is exactly the state the existing
  residue endgame closes.  **Nine inputs complete too**; ten reaches stage 6
  of 10, eleven stalls at stage 6 of 11, and twelve at stage 7 of 12.

  **What separates them is one number: the point count at the arity's first
  merge-requiring stage** — 32 at eight and nine inputs, then 64, 128 and 256
  at ten, eleven and twelve.  A wipe takes the bottom or top `k` points, so
  it reaches a duplicate sitting at an *end* trivially and an **interior**
  one only by a long detour.  Isolated and exhausted, an interior duplicate
  among `k` otherwise-distinct points does merge — depth 2 at `k = 4`, depth
  6 at 6, depth 9 at 7 through 9 — but the search cost explodes: 990 states
  at `k = 6`, 86591 at 7, 113034 at 9, and a 2M-state cap at 10.  So the
  merges the schedule needs are reachable in principle and unaffordable in
  practice from about ten surrounding points, which is exactly where the
  chain starts failing.

  Two cautions for anyone retrying.  The compaction is delicately tuned:
  offering the full `k` range *and* ranking by span as a tie-break took the
  eight-input chain from complete back to a stage-4 stall, so the shipped
  `kcap=3`, count-first ranking is the baseline to beat.  But `kcap=3` is
  also **structurally unable to do interior merges at all** — it only ever
  wipes the outermost three points — so lifting it is necessary, just not
  sufficient, and it must be lifted without disturbing the ranking.

  So the position is: interleaving is legal, its arithmetic admits thirteen
  inputs, and it **builds today at eight** — short of the packed ladder's
  eleven, so it ships nothing yet, and the gap to thirteen is planner
  engineering rather than a discovered obstruction.  Nothing here is walled:
  no search in this investigation emptied its heap.

  Note what the bound is *not*: it is the **fold's**, not the generator's.
  Arity alone refuses nothing, because the cascade builds every conjunction
  or disjunction of literals at any width — the alternating and
  single-minterm tables build at any arity, in 138 characters, and only a
  *generic* table past eleven inputs reaches the raise.  A refusal test that picks
  a structured table at a high arity therefore does not exercise the path it
  means to.  As everywhere in
  this file, eleven and up are **unreached by this construction**, not walled:
  the Lean theorem covers the reading model only, and nothing here bounds
  embedded-input programs in general.  A construction that does not lay a
  rigid ladder would not inherit the bound.

- **The Temporary Stack** — **this entry's argument is refuted; the removal
  rested on a bad negative.**  The entry claimed the auto-drain's `front - 1`
  output cannot be `'0'`/`'1'` and that there is no input-dependent branch.
  Both are false, checked against the interpreter restored from `06687a2^`.

  *There is an input-dependent branch: the drain condition itself.*
  `sum(stk[1:]) / 2 > stk[0]` is evaluated against stack *values*, so an
  input byte in the tail decides whether the drain fires at all.
  `o v49 @ v50` prints `'0'` for input `'1'` and stays silent for `'0'`.  It
  is a real comparator, not a coincidence of two constants: sweeping the
  trailing constant over 48-52 matches the prediction from
  `(input + tail) / 2 > front` on all ten cases.

  *And the answer needs no 49/50 constant.*  In numeric mode the drain prints
  the number `front - 1` as text, so a front of 1 or 2 prints `'0'` or `'1'`
  directly.  The premise that the answer must arrive as byte 48/49 through
  `chr()` is what made a value-to-length conversion look necessary.

  *But the generator would be partial.*  Two inputs reach 9 of the 16 tables
  by length 5.  Three of the missing seven need b1 negated, i.e. b1 at the
  front of the comparison, which it cannot reach without b0 popping first —
  and that pop emits.  NAND, NOR, XOR and XNOR need an input-gated *silent*
  death, and none exists: a death occurs when a popped value leaves byte
  mode's range, and it is silent only at depth 1 (any deeper pop prints the
  values above the killer on the way down), while a depth-1 kill needs
  `front <= 0`, making its condition `sum(tail) / 2 > 0` — true on every row
  once input has landed.  So every death is either input-independent or
  noisy.  The language supports a *partial* generator of roughly ArrowQueue's
  threshold class.  Whether that clears the bar is a separate judgement, and
  the removal's other ground — the literal-embed text generator, see
  `docs/limitations.md` — is untouched.

- **WII2D**: the accumulator never affects control flow (`^v<>` set the
  direction, `@` jumps unconditionally to the closest `@`), so there is no
  value-testable branch to route a decision tree on.  **Resolved by the
  n-embedding chain** (`esolangs.tools.boolean.wii2d`): the branches are
  routing, not value tests, and the *accumulator arithmetic* decodes the
  input.  Each input is embedded exactly once as a junction whose two
  branches are op strings that transform the accumulator before re-merging
  ahead of the next junction; the final accumulator is the table entry.

  The op strings are **constructed, not searched**, and since 2026-08-31 that
  is literally true of every step: nothing keeps an alternative, widens a
  beam, or retries.  Because no cell's behaviour can depend on the
  accumulator, a junction's two op strings are shared by every prefix that
  reaches it, which leaves exactly one shape — a chain that folds the bits
  into a single number, then a decode that turns that number into the entry.

  *The chain* walks the table's decision diagram one input at a time, taking
  the first legal pair from a fixed catalogue (`_WII2D_JUNCTIONS`).  A pair
  is legal unless it lands two *different* residual functions on one
  accumulator value, which nothing downstream could separate.  Horner's
  `('*', '*+')` ends the catalogue and is legal unconditionally — its
  children `2v` and `2w + 1` differ in parity, and `2v == 2w` forces
  `v == w` — so **the walk is total and cannot dead-end**.  The earlier
  entries are the ones that *merge*: two prefixes leaving the same residual
  function share a value, which narrows the domain handed to the decode.
  Several catalogue entries are the shapes the hand-written special cases
  use — parity's `('', '-s')` and the popcount prefix's `('', '+')` are both
  in it — but the special cases still short-circuit ahead of the chain,
  because they are shorter than what the general walk produces.

  *The decode* is built out of folds: `s` is the only op that is not
  order-preserving, and `'-' * c + 's'` merges exactly the pairs equidistant
  from `c`, so folding drives the live values together until two remain —
  which a threshold `'-' * t + '/' * k + '+'` reads out.  At each step it
  takes the **single** best fold under a fixed ranking (magnitude, then live
  count, then length); there is no beam and no width ladder.  A fold merges
  at least one pair, so the live count strictly drops and the loop is bounded
  by the domain size.

  **The single-candidate rule is exhaustively verified, not sampled.**  All
  256 patterns at `D == 8` and all **65536 at `D == 16`** — the widest domain
  the general path asks for — decode under it, each checked by applying the
  emitted op string back over the domain.  The maximally-alternating
  patterns, which need the most folds since a fold at best halves the block
  count, are among the successes.  Four different rankings were swept
  exhaustively at `D == 16` and **all four are total**, so the result is a
  property of the fold algebra rather than of a lucky tie-break.

  **The pool-counting bound this entry used to cite is withdrawn.**  It
  measured how many decodes could be *drawn from a fixed pool of short
  op-strings* — coverage falling from 94% at `n == 3` to 0.04% at `n == 5` —
  which bounds *picking* a decode, not **building** one.  The fold composes a
  decode of whatever length the pattern needs, so the pool never has to
  contain the answer: every one of the 65536 patterns on the 16-point
  `n == 5` domain folds, the case the old note put at 0.04%.

  **`n == 7` stops on a cost guard, not a capability limit.**  The refusal is
  `_WII2D_MAX_INDEX_DOMAIN = 32` compared against `2 ** (n - 1)`, firing
  *before* the chain is walked, so it has never established that anything
  fails.

  **The doubling trap and its retry are gone, by construction.**  The old
  note recorded a "sizeable minority" of tables sending the fold somewhere it
  took minutes to return from: `s` squares, so a fold roughly doubles every
  live value's bit length, and `_wii2d_compress` can only halve when no two
  values needing different bits collide.  Instrumented on a 64-point pattern
  that never returned, `max|v|` went from 3 to over 4300 *digits* while the
  live count crawled 60 → 19.  That was a property of ranking by live count —
  merging as hard as possible at each step, through ever-larger numbers.
  Ranking by **magnitude first** removes the cause rather than detecting it,
  so the `_WII2D_MAX_STATE_BITS` threshold and the second ranked pass it
  guarded no longer exist.

  The `n == 6` worst case is where the trap lived: the old beam-plus-retry
  ranking's worst emitted program was 13411 characters at 393ms; the single-
  candidate ranking's worst is 1242 characters at 12ms.

  **Most of the remaining build time was speculative compression, not the
  fold.**  A candidate is cheap to enumerate and expensive to *compress* -- a
  halving loop over the whole domain, rebuilding the live map each step --
  and the decode consumes only the head, so compressing every candidate threw
  the rest away.  Profiled, that discard rose with the domain: 7 compressions
  per fold actually used at `D == 16`, 15 at `D == 32`, 50 at `D == 64`.
  That, and not the emitted string, is why build time climbed faster than the
  domain did.  `_WII2D_SHORTLIST` compresses four candidates and drops the
  rest, which makes the count flat in the domain and is *both* smaller and
  faster than compressing everything.

  The screen is an admitted approximation, not a bound: compression is a
  contraction (a measured 529 collapsing to 17), so the uncompressed
  magnitude cannot predict the compressed one, and over 80 sampled states
  there was always a candidate whose uncompressed magnitude exceeded the
  eventual winner's compressed magnitude.  An early exit justified as a bound
  was tried first and changed the emitted programs, which is how that was
  found.  Programs are **not** byte-for-byte what they were
  wherever the general path runs: the ranking changed.  (The committed
  example is `n == 2`, which the untouched closed form still answers, so that
  file is unchanged.)

  *Accumulator magnitude.*  The fold squares, so intermediates grow, and
  magnitude-first ranking is what now holds them down.  The wiki specifies no
  accumulator bound and this interpreter uses arbitrary-precision integers,
  so nothing here contradicts the spec.

  There is no universal fallback (a tree would need each input re-embedded at
  every node, which WII2D has no way to store).  The *chain* half is now
  proved total — Horner is always legal, so the walk cannot dead-end — and
  the *decode* half is exhaustively verified through `D == 16`, the widest
  domain the general path asks for.  What remains genuinely open is
  completeness **beyond** that: the fold could dead-end in principle at
  `D == 32` or wider, where verification is sampled rather than exhaustive.
  No sampled pattern has failed, and an unproven completeness claim is not a
  wall.

## 2dFish (the WII2D-style merging chain is affine-only; a decision tree is the universal construction)

**The language was removed.**  This boolean-generator wall is one half of
the removal reason; the other half is that 2dFish's `(...)*` captures a
literal string from the source row and prints it whole, which makes the
language's true text-generator floor a literal-embed rather than the
shipped delta-encoder — see `docs/limitations.md`'s "Assessed and rejected"
list.

2dFish can host a WII2D-style parameterized generator: its direction cells
(`/` east, `v` south, `^` north) steer a pointer carrying a single
accumulator, and there is no runtime conditional nor a way to combine two
`%` reads (each overwrites the accumulator).  The WII2D merging-chain
technique transfers almost verbatim — junction cells filled `/` (bit 0,
continue east) or `v` (bit 1, detour onto a lower row and remerge ahead),
branch op strings from the fish alphabet `i d s` (increment, decrement,
square) transforming the accumulator, and the fold decode
(:func:`esolangs.tools.boolean.wii2d`'s `_wii2d_decode`) is written against
an op alphabet rather than a specific one — but the chain is
**strictly weaker** than WII2D's.

The chain must finish with the accumulator **exactly** 0 or 1 (`o` prints
the decimal value, so a leftover 2, 16, or 81 would print as garbage, and
2dFish has no value-testable branch to fix it up).  With only `i`/`d`
(injective shifts) and `s` (collapses exactly the pair `{x, -x}`), a
decoding op string can only merge values that meet by a sign at the moment
of a square, so the reachable tables are exactly the **affine functions over
GF(2)** — the XOR of any subset of the inputs (the empty subset giving the
constant 0) and the complement of each, `2**(n+1)` tables in all.  Verified
exhaustively against the interpreter: all four one-input tables round-trip,
but of the sixteen two-input tables only the eight affine ones do — AND, OR,
NAND, NOR, and the two single-input-and-not gates are unreachable at any
op-string length (exact 0/1 brute force to length 5, search to length 8) —
and the search's reachable count at `n == 3` and `n == 4` is exactly
`2**(n+1)` (16 and 32).  So a chain-only generator would raise on the most
common tables.

The universal construction is therefore the **decision tree**: re-embed
each input at every node (2**n - 1 junction cells), with uniform-width
leaves holding `i o @` (entry 1) or `o @` (entry 0).  That is total and was
verified against the interpreter for every table through `n == 4` (all
combinations, all 65536 four-input tables).

Four 2dFish mechanics differ from WII2D and must be handled by the layout:

- **No `>`/`<`.**  2dFish's direction cells are `/ \ v ^` only; east is `/`.
  Every `>` becomes `/`, and there is no `!` start marker — the top-left
  cell must be `/` to set the initial heading (the interpreter reads it
  before any command).
- **Ragged grid.**  WII2D's interpreter pads every row to the grid width, so
  its rstrip'd rows are safe; 2dFish's interpreter does not pad, so a
  northward ascent or a `v` descent can fall off a short row and halt with
  `HaltError`.  Every row must be emitted at the full grid width.
- **No digit-set op.**  WII2D's layout sets the chain's starting accumulator
  with a single digit cell; in 2dFish digits are no-ops (the accumulator
  starts at 0), so the start value is a preamble of `i` repeated (`i*start`)
  before the first junction.
- **Fixed-width placeholders.**  The chain template must use single-character
  junction cells filled in place, not WII2D's
  `{Xi}`-to-4-char replacement, which shifts the row one cell per junction —
  WII2D absorbs the shift with its wrapping and row padding, 2dFish does not.

## Termination-based convention (Point Break and ArrowQueue are full generators; the rest partial)

A "halt vs. loop forever" convention — the program halts iff the embedded
input bits satisfy the function — was explored for the languages with a
built-in infinite-loop branch.  It expresses one-input functions, and some
languages reach multi-input threshold functions:

- **ArrowQueue**: the ring-template analysis below hit a
  threshold/AND/OR-class ceiling, and the shipped generator
  (:func:`esolangs.tools.boolean.parameterized.arrowqueue`) **resolves it**
  by leaving the ring template entirely.  A queue-sustaining ring
  (``[" ~*", "+~*", "*~+"]``) hangs iff its center `~` is present, so the
  ring is a one-input identity gadget under the convention; with bit cells
  spread across the ring it becomes an *n*-ary AND (hang iff all bits
  present), and the OR and NOR tables are expressible in other layouts
  (verified by search).  But the hang structure sustains iff its single
  sustainer cell is `~` — each bit can only add a "must be present"
  literal, so a single ring is one AND of literals (one minterm), and
  multiple rings cannot be OR'd on the IP's single path.  XOR/XNOR (two
  disjunct minterms) would need to OR two rings, which the IP's single path
  cannot host, and a 200,000-grid search never produced them — strong
  evidence for a threshold/AND/OR-class ceiling, though not a proof.

  The generator breaks the ceiling by using the queue itself as the
  decision state instead of the ring's center cell.  The header embeds each
  input bit once as a direction (right is 0, down is 1), the next rows
  queue the right/down/left/up loop components, and a **full decision tree**
  pops one bit per level at a ``+`` branch, routing the pointer right for a
  0 and down for a 1 (a ``+`` pop replaces the heading entirely, so the
  route works from any approach).  A ``0`` leaf is an empty 3x3 block (the
  pointer runs off the grid, which halts) and a ``1`` leaf is a
  self-sustaining ring that pushes on every edge and pops on every corner.
  The tree is deliberately full — constant slices are not collapsed —
  because the ring's corner pops must consume exactly the four loop
  components, so every path pops all ``n`` bits first.  Every table is
  supported: all ``n <= 3`` tables exhaustively, with ``n == 4``-``5``
  sampled; program size doubles per input level.

- **Point Break** is the first language where the convention is a *general*
  boolean generator
  (`esolangs.tools.boolean.point_break`): the language has no output, but
  its Turing-complete arithmetic makes every ``n``-ary table a sum of
  minterms (a product of bits and complements computed with single-
  operation ``LET``s), and a fixed template — ``LET g:=one-f`` then
  ``POINT loop`` / ``IF g BREAK loop`` / ``END loop`` — halts iff ``f`` is
  0 and loops forever iff ``f`` is 1, exactly the wiki's own truth-machine
  semantics.  No other language in the repo needed the new harness
  contract (termination as the answer); Point Break is the first where
  the convention unlocks an arbitrary table rather than hitting a
  structural ceiling.  The looping side is decided deterministically by
  state-cycle detection: Point Break is step-capable and a repeated
  complete-state snapshot proves the loop (see the roadmap's
  hang-detection section), so the boolean tests need no wall-clock bound
  at all — which also sidesteps the coverage-tracer deadlock that a
  timeout backstop would invite.

### Four no-output rejections the convention reopens

The convention needs no output at all, so "no output" is not by itself a
sufficient rejection — a point four ledger entries got wrong, each rejected
partly on an I/O ground the convention does not care about.  Re-checked
against their specs:

- **Vandevelo** is the strongest.  `Inp` is real input (nothing to
  substitute), `::` is JavaScript `&&`, and `-!>`/`~!>` negate, so AND with
  NOT is functionally complete — no affine ceiling of the kind that walled
  2dFish, and every table is expressible in principle.  Its wiki
  truth-machine already answers by termination via the self-referential
  `2 -> 2?`.  The open question is *detecting* the hang: lazy
  self-reference is not a revisited machine state, so state-cycle detection
  may not apply and the wall-clock backstop would have to carry it.
- **Crement** matches Point Break's profile exactly: Turing complete
  on-page (two-counter Minsky reduction), `JUMP` branching on a data
  field's sign, halting by running past the last address, looping by
  jumping backward, and step-capable so cycle detection would decide the
  looping side.  But the wiki defines no truth machine, so adopting the
  convention here *extends* the Point Break exception rather than following
  it — the exception is worded around a wiki-defined truth machine.
- **ALT-4** has the wiki artifacts (an infinite loop `00110`, a truth
  machine `01010` with the input prepended) but a thin machine: one file's
  stack holds only zeroes, i.e. a unary counter with an emptiness test, so
  an arbitrary table needs a decision tree built over that and the general
  construction is unproven.  Its `2` multithreads by *filename* — the
  file/OS-based I/O the criteria exclude — which a generator can avoid but
  an interpreter cannot.
- **Conveyor** has the halt/loop distinction (`HALT`, a jumper that
  otherwise loops back, `IFEZ`/`IFGT`), so its stderr-only output is not
  the real blocker; it stays rejected on spec stability instead (an
  unwritten ROT13 example, and unexplained `(Supervisor+)` privilege
  tiers).

None of the four has a construction built, so none is claimed as a
generator: what these entries revise is the *rejection rationale*, which
cited missing I/O where the convention makes I/O irrelevant.  Whether the
ceiling in each case is real (as with ArrowQueue's single-ring minterm
limit) is exactly what building one would settle.

## A Painter Ant boolean generator (general; any n)

A Painter Ant has no I/O, so its boolean generator (in
:mod:`esolangs.tools.boolean.a_painter_ant`) uses the parameterized
convention, read by a semantic grid model (the interpreter's own output is
the visited-cell bounding box, which carries no coordinates).  The answer
is the **colour of the cell the ant lands on** at the end of a cycle (white
is one, black is zero).

The construction paints one decision-tree leaf per input combination and
routes the ant to the leaf for its inputs.  Each leaf is painted ``P``
(white) for a one table entry and **left unpainted** (a space, ignored by
the interpreter) for a zero.  The head walks each leaf out and back
piecewise — one weighted move per input bit, in the same order and
direction the routing uses, so the outbound path never crosses a
previously painted leaf — with ``WS``/``NE`` uppercase anchors (for
``n >= 2``, plus a leading anchor for odd ``n``) that launch the cycle-2
ant off the leaf onto the painted ring.  The body paints a two-layer
**star** around the output leaf and its y-mirror, and the final input's
``WWwWWEEe``/``NENEESWw`` dance closes the walk onto the leaf.  Only ``P``
is ever used — the generator never paints a cell black — so the white cells
are monotone increasing: cycle 1 establishes them and every later cycle
only re-confirms a subset, which is what makes every instantiated program
a cycle-stable fixed point (the box is identical for any whole number of
cycles).  The full construction is recorded in
``docs/a_painter_ant_generator.md``.

Supported for **every arity** and verified cycle-stable and exact: all
``n <= 3`` tables exhaustively (including n == 1 and n == 2), with
``n == 4``-``7`` sampled plus structured and constant edge tables.  The
general method — encode each combination as a distinct leaf position
reached by the weighted bit-moves, and anchor the cycle-2 run back onto
that leaf — is recorded in ``docs/a_painter_ant_generator.md``.

## Multiply capability (Jaune realizes it)

A *multiply* program reads two decimal operands (most-significant first, one
digit per input line) and prints their product as a decimal number (no
leading zeros).  It tests a distinct capability from the boolean criterion
(digit input + arithmetic + decimal output, vs. bit input + branching) and
from the text criterion (arbitrary byte output).

Unlike the boolean criterion, this is **not a generator family**: a boolean
truth table's length ``2**n`` *is* the input count (so the boolean
generators infer ``n`` from the table and take only the table), but
multiplication is a single function ``a * b`` whose operand lengths are a
property of the input, not of the function.  So there is no
``multiply(language, n)`` class to build across the registry — a language
either reads until a delimiter (``*`` between the operands, ``#`` at the
end) and needs one sentinel construction for any digit count, or it cannot.
Jaune is the first language found with the capability; the rest of
the registry's languages are not known to have it (their generators are
text-only or absent), so this records the criterion and the one realized
construction rather than a family of generators.

A brainfuck prototype is built and verified: read+normalize each digit
(ASCII minus 48), multiply via a nested loop, and print the product with a
published 8-bit decimal-print routine.  **n = 1 works exhaustively (all 100
single-digit pairs 0-9 × 0-9).**

For n > 1 the right construction is grade-school long multiplication:
allocate 2n cells for the 2n operand digits (each 0-9, fitting a byte) and
carry over between result cells, so no single cell ever holds the full
product.  This avoids the single-cell overflow that blocks accumulating the
product in one cell.  But the per-digit *carry* needs a "while >= 10"
operation, and with the interpreter's documented 8-bit wrapping cells (mod
256) the standard divmod/carry algorithms assume non-wrapping cells and do
not transfer directly — that decimal printer embeds a working divmod, but it
is tied to the printer's cell layout, not reusable as a standalone carry.
So n = 1 is proven; n > 1 needs a wrapping-safe carry, which is a genuine
brainfuck-algorithms construction rather than a quick extension.

**Jaune realizes the capability:** its cells do not wrap (the language's
reference implementation stores each cell as a JavaScript number with plain
``+=``/``-=``, no modulo or bitmask, and this interpreter uses Python
``int``) and ``^`` prints the current cell as a decimal number, so each
operand fits in a single cell and the product accumulates without a
digit-per-cell carry.  The
program (:func:`esolangs.tools.boolean.jaune_multiply`) runs each read on a
dedicated always-one cell (the ``?``/``!`` jumps are conditional, so a cell
permanently set to 1 gives the loop-back jump an unconditional trigger),
folds each digit with ``v+`` plus a run of nine ``&`` after a ``#``
(multiply by 10), detects a sentinel by adding its offset from a digit
(``*`` is 42, ``6+`` zeroes it; ``#`` is 35, ``13+`` zeroes it) and jumping
on zero, then loops the repeated addition of the first operand over the
second.  Verified exhaustively for single-digit operands (all 100 pairs)
and spot-checked through ten-digit operands.

## Cross-check removals (why seven were dropped)

Seven `extra/` cross-checks (Rust and RISC-V ports run against the Python
interpreters by `scripts/verify_differential.py`) were removed for not
meeting the independent-and-broad bar: Kak, Trash, Number Seventy-Four
(Rust) and Brainpocalypse, Stun Step, 2 Bits 1 Byte (RISC-V) had no
generator at all, so their differentials were a hand-written 4-6 program
corpus each, and the references were ports of (or ported to) the Python,
so agreement was not independent evidence.  123 had a generator but its
RISC-V cross-check was corpus-only (4 generated texts + 2 hand-written
jumps, no fuzz) and verified programs the round-trip test already covers.
All seven added little over the Python unit tests at real toolchain cost
(cargo + RISC-V cross-compiler + unicorn in CI).  The *languages* all
stayed except the six later removed outright (2 Bits 1 Byte, Trash, Number
Seventy-Four, Kak, Brainpocalypse, Stun Step — see the assessed-and-rejected
ledger in `docs/limitations.md`); only the redundant cross-checks went for
the rest.  Live candidates for new cross-checks are in `docs/roadmap.md`.

## State-cycle detection coverage (hang detection without a wall-clock timeout)

`esolangs.vm.run_until_halt_or_cycle` proves a hang immediately for
deterministic, step-capable machines that revisit an exact internal state,
instead of waiting out a wall-clock timeout.  It requires a **complete**
snapshot (the machine's internal fields, including the input-cursor position
— the VM's language-shaped `ip`/`memory`/`stack` view is not enough);
determinism (LaserFuck's random heading, WII2D's `?` and Painfuck's `y` are
excluded); and a `step()`/`halted` state object, since a whole-program
`run()` exposes no internal state to hash.

Detection uses Brent's two-pointer algorithm rather than a hash set of every
visited state: one stored "tortoise" snapshot is compared against the live
machine on every step, doubling the gap between checkpoints each time the gap
is closed.  That holds O(1) snapshots instead of O(cycle length), at the cost
of stepping up to ~2x past the cycle's start before returning — callers get
the verdict, not the machine's state at detection.

**It catches cycles, not every hang.**  An unbounded-growth loop never
revisits a state, so it is invisible to this mechanism however complete the
snapshot: a brainfuck `+[>+]` grows the tape forever, and a call that never
returns pushes one frame per `step()` and pops none, so the frame tuple grows
by one element every step and two whole-machine snapshots can never compare
equal.  The wall-clock timeout stays as the backstop for that class, and for
the fuzzers, which do not control program shape the way hand-written tests
do.

`tests/fuzz/test_interpreters_robustness.py` decides the empty-program
invariant by state-cycle detection for forty-nine string-based step-capable
machines and keeps the SIGALRM backstop for the non-deterministic rest.
Every registry language is step-capable — `_VM_ADAPTERS` covers the whole
registry — so `make_vm`'s `KeyError` -> `UnknownLanguageError` fallback is
exercised by temporarily removing an adapter rather than by a real example.

**Partially-resumable machines.**  MyScript's frame stack unrolls only a
*top-level* `while` into resumable steps; a `while` nested inside a function
call runs to completion within one `step()` via the original recursive
evaluator, since that nesting is bounded by call depth in a working program.
Forbin's frame resumes `main`'s own statements and top-level `for`-loop rows
the same way.  Forbin's *expression-position* calls (`x = f(y)`) are the one
remaining gap: `_Machine` tracks one cursor for the single resumable frame,
and a nested call from inside an expression runs to completion inside one
`step()`, its frames never part of `snapshot()`.  That path is deliberately
native-recursive — `return` exits a call immediately, so there is no
return-value-threading idiom to convert — and it remains bounded by Python's
own recursion limit rather than a documented cap.

**Suptiftam's call machinery, Forbin's statement-position calls and all of
Lamfunc's calls run on an explicit frame stack** (`_Machine.frames`), so a
terminating recursion of any depth completes — confirmed by a 300-level
chained-function test for Suptiftam and Forbin and a 2000-level one for
Lamfunc, past Python's default 1000-frame limit.  Lamfunc needed the fuller
design: it has no statement/expression split whose statement side discards
its value, and a realistic recursive call sits in *argument* position
relative to the lazy `i` builtin, the language's only conditional.  So every
call at any depth pushes a `_Frame` rather than only the outermost.

**`run_until_halt_or_ancestor` catches the recursion the cycle detector
cannot.**  It compares a newly-pushed frame's own local state against the
frames already on the stack, rather than whole-machine snapshots across time,
so it catches a call whose local state repeats identically relative to an
ancestor — frame N+1 is provably about to replay what frame N did.  It is
keyed on a frame's function, bindings **and input position**; that last
component is what makes it sound rather than merely eager, since a recursion
whose base case depends on an unread byte enters with identical bindings on
every lap and a bindings-only key would call it a hang one read from
returning.  It does not catch every infinite recursion — `f(x) { f(x - 1) }`
recurses forever without any local state repeating — though how much slips
through is language-dependent: Forbin's only datatype is bits, so even a
changing argument comes back around.  It is O(depth) per push rather than the
cycle detector's O(1), so it is separate machinery, not a tweak.  A machine
opts in by exposing `frames` and a `frame_entry_key`; Forbin does, and gained
its first hang test as a result, every one of its hangs being in this class.

**Fargo is the case where the cycle detector cannot be primary at all.**  It
has no jumps and each line runs once, so *recursion is its only loop* — the
wiki's own truth machine hangs by calling `one` from inside `one`.  Its hang
detection is therefore `run_until_halt_or_ancestor`, and the frame key is
sound without the output number because Fargo's output is write-only: `%` and
`$` both return 0 and no builtin reads the output number back.  The cycle
detector still covers the terminating side, which is why Fargo appears in
both lists.

**The wall-clock backstop is broken under `pytest --cov`.**  Raising from the
SIGALRM handler while the coverage C tracer is active can deadlock the
tracer: the exception unwinds through the tracer's C code while it holds its
internal lock, so the *next* traced run spins forever.  An interpreter
evaluating a `next(genexpr)` in its hot loop makes it near-deterministic —
the signal lands inside the suspended generator frame and leaves the lock
held — while a genexpr-free loop reduces it to a rare race.  This is why
state-cycle detection matters beyond speed: it removes the deadlock hazard
entirely for the machines it covers.  The one alarm that stays by design is
`test_api.py`'s `+[]` case, a feature test of `esolangs.run`'s `timeout`
parameter rather than a hang-detection strategy.
