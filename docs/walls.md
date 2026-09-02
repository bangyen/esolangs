
# Generator and transpiler walls

The full wall arguments behind the blocker tables in
[`docs/limitations.md`](limitations.md) — the negative result and the
structural reason it cannot be lifted.  Completed constructions (the
working generators, and how they work) live in the commit history, not
here.

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

An arithmetic kernel used to catch the `n > 5` region by embedding the table
as a single integer (6-5's pointer cannot net-advance, so there is no
computed array indexing), at O(`2**(2**n)`) characters for dense tables
behind a ~2 MB setup guard.  It was **retired**: a buildable `T` confines
the ones to low indices, which leaves the rest of the table constant, which
folds well inside the label budget — so it never covered a table the tree
could not.  A search over contiguous families at n=6,7,8 and ~18000 random
tables found no counterexample.

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

## ZTOALC L (dense non-symmetric n > 3 wall) — **FALLEN**

This wall held that dense non-symmetric tables past `n == 3` could not be
rendered, on the claim that **"ZTOALC L's expression grammar has no multiply,
so computing a positional index from `n` bits would need a weighted
accumulation (`bit_i * 2**(n-1-i)`) that `+`/`-`/`=` cannot express in one
step."**

That is the false step, and it is false for a reason worth keeping:
**doubling does not need multiplication.**  `s += s` is a legal command — the
interpreter evaluates a command's target and its operand independently — so
the positional index is built by double-and-add, `s += s` then `s += x{i}`,
one pair per input.  No multiply, no weighted literals, `2n - 1` commands.
With a positional index in hand the table is a plain `2**n`-entry array,
`t[s]` selects the answer, and every table — dense, non-symmetric, any `n` —
becomes the same branch-free program.

The second half fell with it.  The section priced a positional lookup at
`2**33` lines at `n == 4`, past the `2**22` gate, assuming the program had to
sit on the pure power-of-two descent where `L` commands cost `2**L` lines.
It does not: placing command `j` on the `j`-th value of *any* Collatz
trajectory is collision-free, for the same reason the convergent tail is
fatal to trees — a trajectory visits distinct values until it reaches 1,
since a repeat would be a cycle it never escapes.  Peaks grow far slower than
`2**L`: XOR4, quoted here at 524,288 lines, is now **484**.

**The re-verification that "confirmed" the wall was soundly run and searched
the wrong space.**  Sweeping `b1` to ~500,000 values per table really does
find no collision-free placement — but every candidate it tested was a
*decision tree*, and the tree is what the convergent tail defeats; the
branch-free lookup was never in the pool.  A completed search over a
parameterized family bounds that family, not the language.

**Status:** the generator constructs one program per table, with no search,
reorder or cache.  The only remaining limits are size: a table needing more
commands than the longest committed anchor covers (`ztoalc_starts.py`,
reaching 1132 steps), or whose trajectory peaks past the `2**22` line gate.
Verified against the interpreter for every table at `n <= 3` exhaustively,
and for random and structured tables at `n == 4` through `n == 7`.

## 3x (constant-bit guard skip is unsafe)

A guard that separates differing rows from default rows sharing the same bit
prefix cannot have a "redundant" bit test dropped, because the default rows
share the prefix too — dropping the test would misclassify them.  The sibling
idea (pre-negating stored input bits to halve `not_bit`) remains open but is
marginal.

## Minifuck (the read-model cap is FALSE; the staged route is total at n <= 3)

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

### The sculpted route's program length is set by the accumulator

`_mux` used to return the first `(C, orientation, read)` combination that
printed.  That is a poor choice for *length*, and the reason is structural: a
sculpting round emits `'<' * K + '[x' * K + 'x'`, so it costs **`3K + 1`
characters** for a rewind of `K = frontier - C + 1`.  The accumulator `C`
therefore sets the price of every round the table needs, and the first
accumulator tried is not the cheapest.

Measured over sampled four-input tables:

| accumulator order | mean template |
|---|---|
| first ascending (what shipped) | 1046 |
| first descending | 700 |
| **minimum over all** | **594** |

A 43% reduction, and at five inputs the same change takes five-input XOR from
2511 characters to 1174 (53%).  Across the whole 336-table baseline the 61
mux-route templates shrink 42.1% in total.

**There is no cheap rule to substitute for measuring.**  The length curve is
not monotone in the accumulator — sampled tables put their minimum at the
top, the bottom and the middle — and although the winner clusters high (15 of
20 in the top six accumulators), pruning to those loses the optimum on a
quarter of tables.  So the route sculpts every combination and keeps the
shortest; a build costs about 220ms where it cost 7ms.

Two savings pay part of that back, both verified to leave the emitted
template byte for byte identical: the pool code is carried between rounds as
a hint (it never changes within one sculpt — measured, zero switches), and
the code scan probes at the fixed `_PROBE_WALK_OUT` rather than at the
caller's accumulator.  The second rests on the walk-out invariance this file
already records, re-measured on the states a sculpt actually reaches: 50
`(state, code, cell7)` triples over walk-outs 9 to 41, no triple changing
answer.

**Four other length levers were tried and do not pay.**  The accumulator is
the only one that does:

| lever | result |
|---|---|
| shorten the separation prefix | already minimal — 210 characters, and its floor pad is already zero |
| start the embed further left (smaller row positions ⇒ smaller rewinds) | start 32 is the floor: 30 and below scribble the guarded region, which strands every pool probe |
| reorder the separation weights so cheap rows sit where the sculpt hits | any order but descending fails to separate at all — the heaviest gadget needs the most headroom |
| drop the round's trailing `x` | works and is verified 20/20 on the interpreter, but saves 1 character per round (594 → 589, 0.8%) and spends the `_FLIP` guard that keeps a cascade from eating the next instruction; not taken |

The round order is also fixed by the termination argument — fixing the
highest disagreeing row is what makes a round provably unable to disturb the
rows above it — and the cost is not concentrated in the first round anyway
(measured: the first rewind is 29% of total round cost), so there is no
cheap reordering to find.

### The staging enumeration is invertible, but there is no closed form

The staged route used to run its enumeration **per table**, testing
`(separator, settle, suffix, accumulator)` candidates until one printed.  It
now walks the enumeration once per arity, tabulating *column -> first
staging*, and a table is a dict lookup.  Two findings made that possible and
one is a negative worth keeping.

**The pool code does not depend on the accumulator.**  `_find_pool` is asked
for a `walk_out`, so it *could* answer differently per accumulator — measured
over every `(separator, settle, suffix, orientation)` at two, three and four
inputs, it never does (160/160 constant at each arity).  So one walk answers
the whole accumulator range instead of one walk per accumulator, which is
what made the enumeration cheap enough to invert: a four-input table the span
screen admits but no staging places went from **27.7s to 4.8s**.

**The reachable column set is small**, which is why a table beats a formula:

| n | tabulation pass | distinct reachable columns |
|---|---|---|
| 2 | 0.1s | 16 |
| 3 | 0.2s | 252 |
| 4 | 5.0s | 15994 |
| 5 | 8.5s | 28096 |

Five inputs used to ship a 30000-staging budget, justified by "the
enumeration cannot stop early on a miss" — a miss paid the whole 54.7s
sweep.  The tabulation consumed that rationale: a miss is now a dict lookup.
The budget was costing **21756 columns** to save six seconds once per
process, so it is gone.  Lifting it cannot change a template that already
existed — a budget truncates the enumeration without reordering it, and
every column both passes reach gets the same staging (measured, 0
disagreements) — but it *does* change coverage, taking tables that sat late
in the enumeration from a raise to a build.  Twenty sampled from the newly
reached all build and print their 32 rows on the shipped interpreter.

**The negative: the printed column has no closed form in `(suffix, acc)`.**
Three translation hypotheses were tested against the measured grid and all
fail — `acc - ceil(k/2)` leaves 38 of 40 shift classes ambiguous, and the
diagonals `grid[k-1][a-1]` and `grid[k-2][a-1]` are violated 306 and 274
times out of 700.  The grid *does* saturate the way the bracket-run law
predicts (past `k` of about `2 * (acc - 16) + 1` the column stops moving),
but the pool code depends on the state the staging leaves behind, so the
column is not pure tape algebra.  Inverting by tabulation is not a fallback
from an algebraic form that exists — it is the mechanism.

**The order is the contract, and a correctness check cannot see it.**  A
table takes the *first* staging that prints it, so the index must walk
`_stagings` order exactly: both passes, every pure bracket run across every
slice before any insert suffix, same budget accounting.  A draft interleaved
the two passes per slice.  Every column it produced was reachable and valid,
every program it emitted printed its table, and it still assigned five-input
XOR `None` where the enumeration assigns `(2, 0, 0, 33)`.  Only a diff of the
staging *tuples* against the per-table enumeration caught it, which is why
that enumeration is kept as an oracle and pinned by a test rather than
deleted as dead code.

### The read polarity is the free variable

The printed digit is `NOT(v XOR cell7)` for accumulator value `v`, and every
pool the walk-and-clamp fix can reach conserves `v XOR cell7` — so the free
variable is the read polarity, not the pool.  Alongside `[<`, which leaves
the pointer at `(acc-1) + v`, `[x<[<` leaves it at `(acc-1) + NOT v` while
restoring the cell, and swapping the two flips the printed digit.  That is
what makes a table printable whenever its complement is, and why a table and
its complement share a staging.

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

### The n = 4 wall was a wall around the *suffix*, and it has partly fallen

This section used to say the staging method does not scale to `n == 4`, on a
counting argument: a staging offers only ~52 slots, and sweeping every
separator and settle reached 1200 distinct 16-bit columns, 1012 fully
essential — **1.6%** of the arity even if every one were usable.  It closed
by saying that closing `n == 4` needs "a mechanism producing columns in
bulk, which is a different design, not more sweeping."

That was right about the sweeping and wrong about the design being distant.
**The count was over pure bracket runs**, because `'[' * k` is the only
suffix `_stagings` spelled.  Admitting a single `<` *inside* the run — one
string per length becomes `k + 1` — multiplies the yield by nine:

| suffix family, all 5 separators × 2 settles, shipped caps | essential 16-bit columns | share of 64594 |
|---|---|---|
| pure runs `'[' * k` (what the old count measured) | 1650 | 2.6% |
| one `<` inside the run (**shipped**) | **15404** | **23.9%** |

The pure-run row reads 1650 where the old text said 1012; re-measuring at the
shipped caps is the difference, the earlier sweep having been narrower.  The
figures above were checked by replaying sampled columns through `_replay`
before any of them were counted, so they are what the generator reaches and
not what a harness reported.

This is measured through the shipped caps, and 12 sampled tables from it —
four-input XOR among them — build through `minifuck()` and print all 16 rows
correctly on the real interpreter.  XOR is the pointed one: this file
records it as the four-input table the searches fail on, and it is now
search-free.

The generalisation was not a guess.  The one three-input suffix that was
stored at the time interleaves `<` into its bracket run, so a family no wider
than "the same run with a `<` in it" was already known to reach columns no
`'[' * k` reaches; what the measurement settled is *how many*.  That stored
suffix is now derived rather than stored — see `_rescue`, which is the same
family one `<` deeper.

**Why 23.9% and not 100%.**  The remaining 76% is not shown unreachable —
only unreached by this family.  Two axes were measured and are real headroom,
neither shipped because each multiplies the derivation's cost by more than it
returns:

| axis | essential columns | note |
|---|---|---|
| one `<` (shipped) | 15404 | |
| per-gap separators (a separator per gap, 5³ combinations) | 12726 | **not** contained in the shipped set: adds 7882 of its own, union **23286 = 36.1%** |
| two `<` inside the run, at `k <= 12` | 3464 vs 1720 for one `<` at the same `k` | strictly contains the one-`<` set; the axis has not saturated |

So the next raise is available and its price is known: per-gap costs 250
embeds against 10, and two-`<` about ten times the suffixes.  What is *not*
available is more of the same sweeping — settle counts of 2 and above
produce **zero** columns at both `n == 3` and `n == 4`, and instrumentation
says why: all 352 probes raise from `_find_pool`, so the extra clamp and
re-walk land the state outside every pool code rather than merely offering
worse columns.

**The cost this buys, stated plainly.**  At `n <= 3` the derivation stops
early because every table is placed.  At four it cannot — 76% is unreachable
— so the enumeration always runs to its caps, about 76 seconds, paid once
per process by the first fully-essential four-input table whether it hits or
misses.  The caps are not slack: coverage climbs to both of them (12256
tables at `k <= 24` against 15404 at 28), so trimming to buy time trims
coverage.

### Complementing an input on the way in is a free coordinate (shipped)

The enumeration varies the separator, the settle, the suffix and the
accumulator.  It never varied **whether a bit lands inverted**, and that is
worth 15404 → 60942 of 64594 fully-essential four-input tables, **23.9% →
94.35%**.  (That figure read 60546/93.7% for a while; re-measuring gives
60942, and the surplus was checked rather than counted — 40 sampled
flip-placed tables were replayed and every one printed all 16 rows on the
shipped interpreter.)

The gadget is `<[x`.  `<` steps back over the cell the setter used and `[`
flips it, which cascades into the setter's own cell — so the bit standing
there is inverted with the pointer left where the setter left it.

**This is not the input negation this file refuses elsewhere.**  "Why input
negation is not a shortcut" rejects having the *harness* fill `{Xi}` with the
complement of its bit, because then the emitted program computes a table the
caller pre-transformed for it.  Here the harness fill is untouched — the same
`[<`/`xx` every other generator gets — and the template complements the bit
itself, at runtime, from its own `{Xi}`.  That is the alternative that
section endorses, the one `nocomment` takes with its `s`-as-NOT gate.

**The third character is not padding.**  `[` on a zero cell sets the
interpreter's skip flag, so the two-character `<[` ends mid-cascade and eats
the *next* template instruction, shifting every later embedding by a cell.  It
passes a probe that compares tape and pointer, and tables built on it printed
**0 of 12** on the real interpreter.  `skip` is part of the state; a probe
that omits it reports a gadget that is not one.  `<[[` and `<[<` are the
other two spellings that clear it, and they leave different debris, so they
are untried coordinates rather than synonyms.

**Post-hoc template surgery does not work**, which is why this is a
derivation coordinate passed to `_embed` rather than a rewrite: the gadget
writes the live tape, so a template patched after the fact is not the program
the derivation simulated.

### The four-input obstruction is pool cardinality, not nonlinearity

Worth stating because it rules out a whole class of explanation for the
residue.  Taking the columns standing after a pure bracket run, over every
separator and settle, and computing each one's algebraic degree by Möbius
transform:

| arity | distinct standing columns | degrees |
|---|---|---|
| 2 | 16 | {0: 2, 1: 6, 2: 8} |
| 3 | 204 | {0: 2, 1: 13, 2: 88, 3: 101} |
| 4 | 694 | {0: 2, 1: 14, 2: 61, 3: 291, 4: 326} |

**Full degree is reached at every arity**, and the top degree is the *most*
populated class at four inputs.  The `[` cascade generates top-degree
functions freely, so nothing about the residue is explained by the family
being algebraically weak.  What is scarce is *count*: 694 standing columns per
geometry against 64594 tables.  Any route that closes the arity has to
multiply the pool, not make it more nonlinear.

### Slot permutation is *not* blocked by the name-order invariant

**This section used to read "the last 4048 fall to slot permutation, which is
refused".  Both halves were wrong** -- the count and the reason -- and each
error is worth recording, because the section was the standing argument for
not trying the axis at all.

**The count was stale.**  Re-measured, `_derived_plans` places 15404
fully-essential four-input tables and `_flipped_plans` 45538 more:
**60942 of 64594 (94.35%)**, leaving **3652**, not 60546/4048.  Checked rather
than counted -- 40 sampled flip-placed tables were replayed through
`_flipped_staging` and every one printed all 16 rows correctly on the shipped
interpreter.

**The refusal rested on a coupling that is not in the language.**  It was
right that a permuted embed *as `_embed` spells it* emits the `{Xi}` out of
ascending order, and right to refuse a carve-out.  What it missed is that
**emission order and tape geometry are separable.**  The invariant constrains
the order the placeholders appear in the template *text*; it says nothing
about which cell a bit lands in.  `<` never writes and clamps at 0, so the
pointer can be rewound between setters for free -- and then `{X0}` can be
emitted *first* and still be placed *anywhere*: rewind, walk right to the
chosen cell, emit the setter, repeat.

`_embed` couples the two only because it marches rightward and never rewinds.
That is a property of one spelling, not of Minifuck.  **So the axis is open,
and a name-order template can permute slots.**

**Prototyped and verified, not shipped.**  A `_embed_permuted` doing exactly
the above was built, integrated, and measured: n=4 coverage
**94.35% -> 94.98%** (residue 3652 -> 3240), with sampled templates rebuilt,
checked ascending, and run on the shipped interpreter -- correct rows and one
width per table.  At n=3 the family alone reaches 218/218, which is a
mechanism check rather than coverage, that arity already being total.

It was reverted because the yield does not justify the machinery, and the
*shape* of the yield is the useful part:

| geometry | n=4 residue reached | feasible geometries |
|---|---|---|
| sites inherited from the separators, flips=0 | 12 | 10 of 120 |
| + all 16 flip masks | 62 | 160 of 1920 |
| gaps swept 2..5 directly | **412** | 1792 of 24576 |
| descending sites, gaps 2..11 | 126 | 3200 of 16000 |

Descending sites were the *structural* bet -- they guarantee each setter lands
on blank tape, so feasibility stops binding and the `n!` factor collapses --
and they returned about a tenth the yield per second of plain permutation.
Each further coordinate buys less against a residue that barely moves.
Closing 3240 this way would need roughly 28x the yield of the best axis tried.
**On that evidence n=4 is not reachable by widening this family**; the residue
is the hard core, and closing it took a different construction, not another
coordinate on this one -- see "Four inputs is closed" below.

**Two facts decide the geometry**, both measured, and both would have to be
rediscovered by any reimplementation:

- **The rewind must stop above the pool.**  Clamping to the origin walks back
  through cells 0..7 and the *return* walk's `[x` rewrites them, leaving a
  pool no pool code repairs: `_find_pool` answers 0 accumulators against the
  ordinary embed's 26, and the route scores 0 of 218 at three inputs where
  stopping at cell 8 scores 58.
- **The setter is pointer-neutral only on a blank cell.**  `[<` on an occupied
  one cascades, the skip eats the `<`, and that row ends a cell right -- so the
  pointer *spreads*, and `<` above 0 preserves a spread.  A setter landing on
  an occupied cell therefore refuses the geometry, which is an ordinary miss.

**Nothing is open at four inputs any more** -- the residue these families
leave is closed by the sculpted route in the next section.  What this
section still establishes is narrower and stands: the *staging* families do
not reach it, and no impossibility argument was ever available for the
residue as tables (`_span_admits`, the one algebraic screen that could have
supported one, is vacuous at this arity).

**And none of this bears on totality for all `n`.**  Permutations, flips and
spacings add a per-arity constant of order `n! * 2 ** n` -- factorial, not
`2 ** (2 ** n)` -- so the counting argument below stands exactly as written.

### Four inputs is closed: separate the rows, then edit them one at a time

**64594 of 64594.**  The 3652 tables every axis above left standing all
build through the sculpted route (`_mux` in the module), and the whole
residue was verified rather than sampled: each of the 3652 built through the
public entry and printed all 16 rows correctly on the shipped interpreter,
at one program width per table and with the slots in name order.  Build cost
is ~10ms a table after a per-arity separation derivation (~15s, once per
process); the staged families run first, so every table they reach keeps its
template byte for byte.

The route is not another coordinate on the staging family, and it does not
spend the exactly-once rule -- each input is still embedded once.  Two
observations carry it, each the negation of an assumption every earlier
argument quietly made:

- **The flat-pool count assumed one read of the tape.**  A staging offers
  the columns *standing* at the read, so demand squares against a fixed
  pool.  But the embed's walk transform is affine and invertible -- after
  the embed no two rows share a state -- and a table-independent suffix of
  reads can convert that state difference into a **pointer** difference:
  all `2**n` rows at distinct positions.  Four searches derived that per
  arity (shortest-split BFS, greedy aimed reads, a short beam, a two-machine
  BFS on one stuck pair at a time); all four are now gone, replaced by
  weighting each input as it lands — see the constructed-separation section
  below.  The construction must still leave everything left of the embed
  untouched -- junk in the pool codes' working range strands every probe
  (measured: 0 usable probes against 14) -- which is why the route embeds
  sixteen cells right of `_BASE`, and why eight
  scratch cells just left of the embed stay deliberately writable: sealing
  them turns the derivation into a failure.

- **The position-decode refutation assumed rows shared positions.**  Its
  mechanism -- `ptr = entry + v + answer` sums the selector into the answer,
  and the per-row plant a live band needs is "not producible" -- is true of
  co-located rows and dissolves for separated ones.  A round of
  `'<' * K + '[x' * K` with `K = b - C + 1` flips a low target cell `C` for
  a *position-selected* set of rows: the row at `b` rewinds to `C - 1` and
  its first landing is `C` (an unconditional flip, clean whatever its tape
  holds); rows above `b` never touch cells at or left of `C`; rows below get
  scrambled.  So fixing the **highest** disagreeing row per round strictly
  lowers the frontier, and the printed column is sculpted to any target in
  at most `2**n` rounds -- a termination *argument*, not a search.

One negative here has since been **falsified**, and it is worth stating that
plainly because it was measured, recorded, and wrong.  "Reading a bit as it
lands loses everything but the Hamming weight — the setter-read unit is
shift-invariant over the uniform wake, `n + 1` distinct states out of `2**n`
at every arity and spacer tried" is true only of a bit a walk has already
crossed.  Read while **fresh**, and spaced so gadgets do not overlap, the
same unit carries arbitrary integer weight and separates every arity in
closed form.  See the section below; the shipped separation is built on
exactly the move this paragraph said could not work.

The other negative stands as an observation about the *searches*: what
resisted them longest was always the first input, whose distinguishing cells
are furthest left under everything later walks smear over them.  The
construction does not care, because it never has to find those cells.

**Five inputs is no longer gated.**  This paragraph used to say the searches
run ~191s and fail, stalling on pairs that differ in the first input, and
that lifting `n == 5` was "exactly one successful separation away".  The
constructed separation below does it in 0.004s, and `_MUX_ARITIES` now
carries five.  Pre-splitting the first input at embed time — walking over
`X0`'s landing cell so the setter itself splits — remains a recorded dead
end: it stalls at the same 20 of 32, which is why the fix had to be a
different construction rather than a better search.

### Separation is constructed, not searched — the saturation was a sandbox bug

This section used to read "separation has an algorithmic primitive, and it
saturates at three inputs", recording a weighting scheme that reached 13 of
16 at four inputs and no further.  **The saturation was an artefact of how
the weights were spaced, not a property of the primitive**, and the
construction that fixes it removed every search from `_mux_separate` and
lifted `n == 5` at the same time.  The superseded reasoning is kept below,
because the shape of the error is the reusable part.

**What was right.**  A restoring read `'[x<[<'` displaces the pointer by the
bit and puts the cell back, and rewinding one cell between such reads
compounds them exactly:

    ('[x<[<' + '<') * (k-1) + '[x<[<'   →   displacement −k

measured linear for `k` of 1 to 8 with no row dying.  So arbitrary integer
weight is constructible, and positional weighting is expressible.

**What was wrong.**  The old sweep swept *gaps 1 to 3*, and a weight-`k`
gadget writes up to `k − 3` cells left of its setter — so at `k >= 4` every
gadget in that sweep reached back into the previous one's cells **by
construction**.  That is exactly the reported symptom: "realised weights
permuted and rescaled by earlier gadgets' debris, `(−3, −1, −2)` where
`(1, 2, 4)` was intended".  The debris was not a fact about the language; it
was the sweep measuring gadgets that overlapped.  The corner of the design
space where `gap_i >= reach(k_i)` was never tested, and it is the corner
that works.

**The construction.**  Weight each input as it lands, then pad past the
damage:

    for i in range(n):
        setter(i)
        weight(2**(n-1-i))            # bit is FRESH — no walk in between
        pad "[x" * (2**(n-1-i) + extra)

    extra = max(2**(n-2) − 1, 1)
    start = _MUX_BASE + max(0, 2**(n-1) − 9)

The pointer lands at `c0 − Σ 2**(n-1-i)·x_i`: affine in the inputs, injective
by binary expansion, so all `2**n` rows separate **by construction**.
Verified affine with exactly the intended coefficients at every arity 2..6.

Two conditions are load-bearing and both were found by measuring:

* **The bit must be fresh.**  A single `[x` between the setter and the gadget
  folds the bit into the running prefix-XOR and every weight collapses to 1.
  This is what the old text's "reading a bit as it lands does not help and
  cannot — only the Hamming weight survives" was actually measuring: a
  *stale* bit.  Once banked into the pointer, the displacement survives
  arbitrary rightward padding (measured 0 to 10), so later gadgets cannot
  undo earlier weights.
* **`extra >= 2**(n-2) − 1` is sharp.**  At `n == 4` pads 1 and 2 give 14 of
  16 and pad 3 gives 16 of 16; at `n == 5` pads 1..6 give 21..30 of 32 and
  pad 7 closes it; at `n == 6` pad 15 is the first that separates.  Below the
  threshold the coefficients are still exactly right — the misses are rows
  whose leading bits clamp at the tape's floor, not a weighting error.

**Cost and reach.**

| n | searched | constructed | rows separated |
|---|---|---|---|
| 3 | 2.8s | 0.0002s | 8/8 |
| 4 | 15.0s | 0.0007s | 16/16 |
| 5 | fails after ~191s | 0.004s | **32/32** |
| 6 | — | 0.008s | 64/64 |

Four searches were deleted with it: a pointer-census BFS, a greedy pass over
aimed reads, a beam over aimed-read sequences, and a two-machine BFS on one
colliding pair.

**`n == 5` is no longer gated.**  The heading above this one said lifting it
was "exactly one successful separation away"; this is that separation.
Sampled end to end, 200 of 200 fully-essential five-input tables build
through `_mux` and print all 32 rows correctly on the shipped interpreter —
five-input XOR among them, the table this file records as one no search here
builds at all — at about 0.14s each.  The arity is **not closed**: 200 is a
sample of 4294642034, and what is claimed is that no sampled table failed,
not that none can.

**The reusable lesson.**  A sweep whose parameter range makes its units
overlap measures the overlap, not the units.  Both the "shift-invariance"
finding and the "13 of 16 saturation" were real measurements of a
misconfigured probe, and each read as a property of the language.  When a
primitive is documented as saturating, check whether the sweep that found
the saturation could have expressed the non-overlapping case at all.

### The generator no longer searches at all

With the separation constructed, the remaining searches were each one table
away from being unnecessary, and all of them are now gone.  There is no
breadth-first search anywhere in `minifuck.py`.

| search | what replaced it |
|---|---|
| four separation searches (BFS, greedy aimed reads, beam, pair BFS) | weight each input as it lands; pointer = the row's binary expansion |
| `_find_reset` (reconverging reset, BFS to depth 13) | `_RESET_HEAD + "<" * (ignored + 1)`, closed form |
| `_find_column` (degenerate route's column search) | the six tables it served build through `_mux` in milliseconds |
| `_find_parked` | already dead — reachable from nothing |
| `_search` (the shared BFS engine) | no callers left |

**The reset was the cleanest.**  Its search found length 12 at two ignored
inputs, the same string plus one `<` at three, and **nothing at four** — its
depth cap bit before the answer.  The pattern is just a fixed nine-character
head followed by `ignored + 1` clamping steps, and it converges at every
arity tried, 1 through 8.  A search that fails at four inputs and a
construction that works at eight were separated by noticing that two hits
differed by one character.

**The column search served six tables** — `X2` and its complement at three
inputs, `X2`/`X3` and theirs at four, the projections whose cell the
degenerate route does not read off directly.  All six build through `_mux`
in milliseconds and print every row on the shipped interpreter, and `_solve`
runs that route directly after the degenerate one, so deleting the search
strictly improved the fallback: a construction instead of a sweep.

What is left when a table cannot be built is a **raise**, which is a bounded
failure a caller can handle.  That was already the design for `n >= 5` — the
searches there turned a fast failure into an indefinite one — and it is now
the design everywhere.

### `n == 5` ships partially; full coverage is out of reach of any flat family

**The heading here used to read "`n >= 5` is out of reach of *any* staging
family".  That was wrong in scope and is corrected below.**  The counting
argument it rested on is sound and is kept — a flat pool of columns cannot
cover a real *fraction* of five inputs — but "cannot cover a fraction" was
silently read as "cannot cover anything", and the shipped family in fact
carries a measured sliver that is now derived rather than searched for.

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
narrowed to the one table and its complement (`_TABLE_MAJOR_ARITIES`).

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

`docs/walls.md` used to say a higher arity needs a construction that
*composes*, and named two failures in one line each. That line has now been
worked out in full, and the answer is that the combine step **creates no
information**.

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

**"Why no chain can escape the counting argument" — REFUTED BY
CONSTRUCTION** (2026-08-31).  This section used to argue that a chain is
"just a suffix string over the same alphabet", hence a *subset* of the
enumerated suffix space, hence governed by the same flat-pool count.  That
step is wrong, and 78 interpreter-verified programs say so.

A chain is **not** a suffix the enumeration can emit.  `_stagings` emits one
uninterrupted run from `_BASE - 1`; a chain walks to a *chosen* cell, reads,
walks a chosen gap, and reads again.  Its coordinates are
`(separator, settle, k, cell, read1, gap, read2, accumulator, orientation)` —
a strictly larger pool that no `'[' * k` and no single-insert suffix spells.
Being "over the same alphabet" was never the same as being in the same
enumeration.

**What was actually measured.**  Sweeping 125440 chains and scoring them
against what they would *print*:

| sample of unreached four-input tables | chains print | verified |
|---|---|---|
| 400 (strided over the unreached 49542) | **78 (19.5%)** | **78/78 on the interpreter** |

All 78 are fully essential, 296-329 characters, four slots.  Projected over
the whole unreached set that is roughly 9660 tables, taking four-input
coverage from 24.4% to about **39%** — an extrapolation from a strided
sample, not a measurement of the space.

**Why it was missed before, and it is not subtle.**  The earlier attempt
searched the *standing* set: "which chain leaves the answer sitting in a
cell?"  That question has answers (23 of 200 sampled) and every one of them
dies on the walk out — which is what "produced easily, destroyed almost every
time" below records, correctly.  The right question is the **printable** set:
which chain leaves a tape the ordinary endgame prints correctly.  The chain
never has to decode position at all; it reshapes the tape so the existing
print route lands.  Standing and printable are different sets, and the whole
negative came from searching the wrong one.

That question only became exhaustively askable once `_printed_column` gave a
closed form for what an endgame prints (see the module docstring): scoring a
chain costs a walk and a lookup instead of an emitted endgame, which is what
makes 125440 chains a ten-minute sweep instead of an overnight one.

**What survives.**  The mux analysis below is still correct about what it
actually examined — `ptr = entry + v + ans` does sum the selector with the
answer, and the standing answer really is destroyed by the walk's per-row
prefix-XOR.  It is a true statement about position-decoding, and a false
statement about chains in general.  The counting argument also still governs
the *staging family*: nothing here raises what `_stagings` reaches.

**What this does not establish.**  Four inputs is not total — this is a large
slice of the unreached space, not closure.  And the chain pool is itself
finite and fixed-size, so it faces the same demand-squares-per-arity problem
at five inputs; nothing here suggests it closes another arity.

**Reproducing it.**  The prototype is not shipped and nothing in `src/` calls
it.  `notes/minifuck_chain_sweep.py` runs the sweep (about ten minutes, and it
carries a positive control so a zero cannot be a forced artifact);
`notes/minifuck_chain_verify.py` re-derives the hits and runs every one of
them through the real interpreter, which is the 78/78 above.  `notes/` is
gitignored, so these are working files rather than a shipped harness.

### A sound decline exists after all, and it is linear algebra

The section below concludes that no invariant yields a *rule* — only rates —
and that stands for every invariant of the **truth table**.  What it missed
is that the predictor need not be a function of the table alone: it can be a
function of the **staging's state**, and there one exists.

**Post-suffix span containment.**  Take the columns standing after
`suffix + "<"` and the clamp, and their GF(2) span.  Everything `_endgame`
emits from there is affine in those columns, so **every column a staging
prints lies in that span**.  A table in no staging's span therefore cannot be
printed by any of them, and saying so is a linear-algebra test rather than a
sweep.

Measured, not argued:

| check | result |
|---|---|
| (staging, printed column) incidences contained, `n == 5` | **241280 / 241280** |
| false negatives over every reachable table | **0 / 24582** |
| unreachable tables declined | 53.4% |
| cost | **3.6 ms** against the enumeration's measured **143 s** |

The check that matters most is against the *generator* rather than against
the harvest the rule was built from: sampled declined tables were handed to
the real `_derive_staging`, which agreed on all of them after about 143
seconds of finding nothing.  Two independent implementations, written from
the description rather than from each other's code, agree on every figure.

**Why five inputs and not four.**  The identical condition is *vacuous* at
`n == 4` — ambient dimension 16 against bases whose rank reaches 16, so it
admits every table at exactly the 23.85% base rate.  At `n == 5` the ambient
dimension is 32 against a median rank of 16, so acceptance is about 2^-16.
It bites exactly where the cost is.

**What it does not claim.**  The mechanism is measured rather than proved:
the `[` cascade's skip is value-dependent, which is what breaks containment
*before* the suffix, and the claim is that nothing after it reintroduces the
nonlinearity.  The *pre*-suffix span is not a necessary condition and was
checked — the union of the ten slices' standing columns has rank 15 of 16 and
holds only 9236 of 15404 printed essential columns, because the bracket
cascade creates algebraic content the embed never left standing.  That is the
module's "select on the column at the read, not the cell holding it" trap in
algebraic form.

Validity is scoped to the shipped caps, separators and setter; the spans are
a property of those.  `test_span_screen_declines_no_reachable_table` replays
the whole enumeration against the spans and is what fails if that ever stops
being true — deliberately not a sampled test, since a screen that declines
one reachable table is a silent coverage regression.

One honest note on what shipping it buys: it removes the 143-second staged
sweep from a *failure*, and a declined table still falls through to the
column and parked searches.  It makes the staging fast to give up on, not the
whole call.

### The layout is a free parameter, and the tape state predicts yield

Everything above asks whether the *fixed* button layout can be predicted.
This asks whether the layout is the limiting choice, and whether the state a
button leaves says anything about what follows.  **Every result here is a
multiplier on the 23.9% at `n == 4`; none of it moves the counting argument,
and a tenfold layout win would still leave `n == 5` near 0.006%.**

**Separator length was never re-swept, and it is live.**  The shipped five
came from enumerating *short* strings to close an `n == 3` gap.  Sampling 178
strings of length 5–7 (of 3159) and screening them the same way gives **8100
novel essential columns beyond the shipped 15404 — 1.53x**.  That figure is a
**floor** twice over: candidates were screened pure-runs-only but diffed
against the shipped family's full pure+insert relation, and only 5.6% of the
space was sampled.  Best singles were `[x[[[` (302 novel), `[xxx[` and
`xxx[x[` (284).  Priced like the per-gap axis: each admitted separator is
about one more slice, so roughly +10% derivation cost.  Only 8 of 178 were
true forced zeros (every probe failing in `_find_pool`); the uniform
3016/6032 pool-failure rate elsewhere is the normal one-in-two.

**The setter had never been swept at all, and it is the widest axis of the
three.**  `_set_bit` returns `("[<", "xx")` — one hardcoded pair.  This
matters because this file already records, for the 123 language, that a
ceiling which looked like a language limit belonged to the *setter choice*.

Sweeping all 78 equal-width pairs of widths 1–2 (the shipped pair among
them), screened pure-runs-only:

| setter (zero, one) | essential columns | novel |
|---|---|---|
| `("x<", "[[")` | 2588 | **1858** |
| `("[[", "x<")` | 2588 | 1606 |
| `("x<", "[x")` | 2002 | 1482 |
| shipped `("xx", "[<")` | 1856 | — |

The best novel pair reaches 39% more essential columns than the shipped one,
and the **union over the top ten is 9842 novel columns — 1.64x** the shipped
family.  Admission would be **additive rather than a replacement**: each of
the top pairs misses about 93% of the shipped pair's own 1650 columns, so
nothing here dominates the current choice.

The winning pairs are **not displacement-neutral** — `x<` moves the pointer
where `xx` does not — which is exactly the 123 precedent, and the reason
neutrality was deliberately not required.  Equal width is the one real
constraint, since unequal fills leak the inputs through `len(program)`.

Of the 78 pairs, 8 yield nothing, and **none of those is an instrumentation
artifact**: zero of the eight failed in `_find_pool`, so they genuinely
produce no columns rather than breaking the endgame.  (Width 3 is a further
702 pairs at about 50 minutes and was not swept; the widths above are where
the 123 precedent points.)

### The state a button leaves predicts its yield, but barely guides a search

The pre-walk state's count of **standing nonaffine columns** predicts what a
prefix prints at **r = 0.925** (essential-column count 0.924, distinct 0.849;
pointer position and row spread predict nothing, r = 0.000).  The guard that
keeps this honest is that predictors are read from the *pre-walk state* and
ground truth from *printed* columns — the module's documented trap is using
standing columns as the yield, since the walk rewrites them.

It survives the check that matters: the feature was **selected** on `n == 4`
data, so its edge could have been feature selection.  Measured out-of-sample
at `n == 5` it holds — first-server position improves **+13.5% over random**.

**Yield is not novelty, and novelty is what an enumeration gains.**
Correlation with novelty is only r = 0.345, because a prefix delivering a lot
is mostly re-delivering what earlier prefixes already delivered.

**Where ordering can pay is `n == 5` alone.**  At `n <= 4` the derivation
runs to its caps regardless, and reordering forfeits the incremental
`[`-extension that makes it affordable, so coverage-at-k-prefixes never
becomes time saved.  At `n == 5`, which is table-major and stops at first
hit, the median first server moves from prefix 2888 to 1594 — 1.54x against
the shipped order, but only **1.13x against random**, and the shipped order
is *cost*-ordered by design rather than novelty-ordered, so it is the weaker
comparison that is the honest one.

**A raw score ranking is worse than useless, and the failure is the
lesson.**  Directing the unshipped two-`<` widening by score alone found
**zero** novel columns against blind enumeration's 118 — not anti-correlation
but **degenerate concentration**: all 200 top-scored candidates came from one
slice, `(sep 3, settle 0)`, tied at score 11.  A ranking with no diversity
term spends its whole budget on near-identical states.  Ranked within slice
and taken round-robin, the score gives **1.24x–1.74x** over diversified
random (five seeds; the scored arm is deterministic at 136 novel columns, the
random arms range 78–114).  So the score is worth a modest constant on a
directed widening, and nothing at all if applied naively.

### The staging → table map is a hash, not an index

The natural question after "the enumeration is brute force" is whether it
*has* to be — whether each button could be characterised, so a table could be
routed to the staging that serves it instead of sweeping.  Measured, no.

**Read this section with its scope in mind**: everything below is about
predictors that are functions of the **truth table**, and for those the
answer really is no.  A predictor of the *staging's state* is a different
object and a sound one exists — see the span screen above.  The failure
recorded here is of table-side invariants, not of prediction as such, and
missing that distinction is what kept the span rule unfound for as long as it
was.

**First, a methodological trap that produced a wrong answer before the right
one.**  The obvious object to analyse is the *assignment* — which staging
each table was given.  That object is contaminated by the first-hit rule:
separator 0 is enumerated first and claims everything it reaches, so the
later coordinates hold only leftovers.  Statements read off it ("separator 2
serves 72 tables, degrees 2 and 3") describe greedy residue, not separator
2's reach, and any predictiveness test inherits the contamination.

The honest object is the full many-to-many **relation** — every
`(separator, settle, suffix, accumulator, read, orientation)` against every
column it prints, with no dedup.  Built at each arity (2s / 76s / 143s) it is
what the numbers below are measured on.

**No invariant tested yields a rule.**  At `n == 4`, where both sides are
exhaustive — every essential table, and the family's complete reach at the
shipped caps — reachability was measured *by class*, against a base rate of
15404/64594 = **23.85%**:

| class | result |
|---|---|
| ANF degree | flat (1.01x at degree 4); no discrimination |
| ANF monomial support = consecutive intervals | 3.3% of reachable vs 2.8% of random — **noise** |
| ANF sparsity | identical distributions (median 8, max 16 both sides) |
| Hamming weight | **strong, symmetric**: 78.4% at weight 2 and 14, falling monotonically to 18.8% at weight 8 |
| nonlinearity | 1.79x at the near-affine end, 0.92x in the middle |

The consecutive-interval hypothesis is the one that was *derived from the
mechanism* — the `[` cascade is a skip-carry over adjacent cells in a
rightward-only language, so interval-shaped monomials looked likely — and it
is flatly refuted.  Worth recording as a mechanism-plausible guess that the
measurement killed.

**The weight and nonlinearity signals are real and still buy nothing
sound.**  Both are exhaustively measured, and the weight curve's symmetry
about 8 is exactly what complement-closure demands, so this is structure
rather than noise.  It is also coherent with the mechanism: a family built
from prefix-XORs plus one cascade term should over-represent near-affine and
unbalanced tables.  But **no weight class is empty** — reachable tables span
weights 1..15 of 1..15 — so no weight licenses declining without running the
sweep.  A rate sets expectations ("weight-8 tables are the slow ones"); it is
never a decline.

**The weight skew is a property of the family, not of one arity.**  Rates
cannot be measured at `n == 5` — the complement is 4.29e9 tables — but the
reachable set's weight *distribution* can be compared against the binomial a
uniform table would give, and it carries the same shape far more sharply:

| weight (of 32) | skew vs uniform |
|---|---|
| 5 / 27 | **41.6x** |
| 8 / 24 | 4.1x |
| 12 / 20 | 1.1x |
| 16 (balanced) | 0.8x |

Perfectly symmetric about 16, decaying monotonically to balance — 4.5% of
reachable tables have weight ≤8 or ≥24 against 0.70% of uniform ones.  So the
family really does favour unbalanced tables, and increasingly so with arity.
It still licenses no decline, for the same reason: the classes are thin, not
empty.

**Redundancy collapses as arity rises**, which is worth knowing before
reading anything into a single staging.  The median column is served by 16
stagings at `n == 3`, **2** at `n == 4`, and **1** at `n == 5`.  At the top
arity the typical reachable table has exactly one way in, so there is no
slack for a cleverer search to exploit — which is the same fact the
one-slice-serves-72% figure below reports from the other direction.

**No coordinate is droppable either**, at either arity.  Every one of the ten
(separator, settle) slices contributes tables reachable **nowhere else**:

| | `n == 4` | `n == 5` |
|---|---|---|
| slice reach, alone | 3.0%–24.3% | 6%–17.5% |
| unique contribution, thinnest / widest | 104 / 2212 | 16 / 3648 |
| tables served by exactly one slice | 72% (11080 of 15404) | **92.6%** (22752 of 24582) |

So the sweep cannot be shortened by trimming coordinates, and the room to do
so *shrinks* with arity — the same conclusion the "two separators reach 99 of
109" row reaches at `n == 3`, now measured on the relation rather than on the
assignment.

**The one sound shortcut is an index, not a predicate.**  Exact membership in
the harvested family is sound by construction — it *is* the family — answers
in microseconds, and costs ~125 KB at `n == 4` or ~220 KB at `n == 5`.  It is
**costed here and not taken**, for three reasons: it reverses the module's
deliberate move from stored stagings to a derivation; its validity is coupled
to the caps and separators, so any change silently invalidates it without a
regeneration story; and it saves the 143s staged sweep only on a *miss*,
which then falls through to the searches anyway, so it shaves the first act
of a failure that continues well past it.

### The pool is not the obstruction at five inputs

Checked before anything else, since a failure would block every design
downstream: the endgame's pool search succeeds at 32 lockstep machines,
**12 of 24 lookups hitting** at every separator and settle count — the same
one-in-two rate the three- and four-input arities show.

### The original counting argument, kept

The obvious next question is whether the suffix trick repeats.  It does not,
and the reason is worth separating carefully from the argument it just
overturned, since both are counting arguments and only one of them holds.

**The argument that fell** counted columns from *one spelling of the suffix*
and concluded something about the language.  Widening the spelling broke it.
**This argument** is about the ratio between what any enumeration can produce
— one column per probe, and probes are polynomial in the caps — and what an
arity demands, which is doubly exponential in `n`.  Nothing about the
spelling enters it.

Exact combinatorics, not estimates.  Writing `E(n)` for the fully-essential
`n`-input tables:

| `n` | tables | fully essential | degenerate |
|---|---|---|---|
| 3 | 256 | 218 | 38 (14.84%) |
| 4 | 65536 | 64594 | 942 (1.44%) |
| 5 | 4294967296 | 4294642034 | 325262 (**0.0076%**) |

Composition does not rescue this.  A five-input table with a narrow core is
solved at that core and renumbered back, but only **2292** five-input tables
have three or fewer essential inputs, and 322970 have exactly four — of which
the shipped family stages 23.8%.  Adding those up, the search-free share of
`n == 5` by projection is **1.8e-05**.  The other 4294642034 tables are fully
essential and need columns of their own: **1.7e+05 times more** than the
24582 essential columns this family produces *at five inputs*.

(That ratio used to read 2.8e+05 against 15404, which is the family's yield at
**four** inputs — the arity it was measured at.  Harvesting the family at five
gives 24582, so the gap is a little narrower than recorded and the conclusion
is unchanged: no constant factor closes 1.7e+05.)

That gap is immune to the axes above, because they multiply by constants.
Per-gap separators took the union to 36.1% — about 1.5x — and a second `<`
roughly doubled the yield at matched `k`.  A hypothetical axis worth a
hundredfold would move `n == 5` from 1e-05 to 1e-03.  So `n == 4` was not the
first step of a ladder; it was the last arity small enough (64594 tables) for
a family producing tens of thousands of columns to cover a real fraction of
it.  The table count squares at each step while the family grows
polynomially, and four is where those curves cross.

**What a higher arity would actually need** is a construction whose cost is
per *table* rather than a lookup into a flat pool of columns — and one now
exists: the sculpted route ("Four inputs is closed" above) chooses its
rounds against the target table, so nothing here counts it.  Its own gate is
the row separation, not any pool.  The two earlier attempts at escaping the
count were `4 -> 8` doubling and a decode from an accumulated position.  The
second has since been worked out in full and refuted with its mechanism for
*position decoding* specifically — see "Composition through the pointer"
above, whose scope note now matters: that refutation is about co-located
rows, and separated rows are what the sculpted route edits.  The companion
claim that no chain
escapes this count has since been **refuted by construction**: a chain is not
a suffix the enumeration emits, and 78 interpreter-verified four-input
programs sit outside the family counted here.

One honesty note on the above: the exact table is combinatorics and the
1.8e-05 follows from it, but "constants cannot close 2.8e+05" assumes new
axes behave like the two that were measured (1.5x and 2x).  That is an
argument about the shape of this family, not a proof that no axis is worth
more.

A *uniform* rule does not exist either, which is why all four coordinates are
still enumerated:

| attempt | reach |
|---|---|
| one fixed staging | **13 pairs**, the measured maximum over the family (mean 5.8) |
| best single `(separator, settle)` over all its `k` and accumulators | 60 of 109 |
| two separators | 99 of 109 |
| the same, with `k` to 70 and accumulators to 60 | **still 99** |
| dropping the settle field | 99 of 109 |

The first row is a counting argument, not a sweep: a staging offers one
column per accumulator and orientation — 52 slots — but they collapse,
because the walk's prefix-XOR is many-to-one and different accumulators keep
arriving at the same column.  The fourth row answers "would a bigger program
help?" — no: the ten tables missing from two separators stay missing with far
more room, so they need a different *separator*, not a longer walk.

### Disproved mechanisms, and search artifacts that looked like walls

Ruled out for real, and not to be revisited:

- **Chaining `[<` reads across planted indicators**, so disjoint minterms
  accumulate into the pointer.  `[<` sets the cell to its *right*, and the pad
  walk between reads carries that residue forward, so the second read reads
  the first read's debris rather than the planted indicator.  A sweep of every
  gap 1..9 at chain lengths 2 and 3 found no accumulating layout; guard cells
  cannot fix it, since the pads write over the guards.
- **Fixed width-2 stage chains** reach only 88/256 tables at `n == 3`
  (majority-of-3 unreachable) and 520/65536 at `n == 4`, so they cannot be
  total however good the gadgets.
- **Harvesting** — sweeping embed variants for a table that lands in a cell —
  finds all 16 at `n == 2` but 105/256 at `n == 3`: a shortcut, not a totality
  argument.
- **Relocating an ignored placeholder.**  A fill writes the live tape, so
  moving trailing fills to the front makes 2 rows wrong at `n == 2` and 6 at
  `n == 3`.  The working route emits the ignored setters *first* and then
  reconverges to a common **non-blank** state — blank is unreachable, since
  the all-ones row ends a cell right of the others and `<` clamps without
  writing.

Five apparent walls were artifacts of how the question was asked, each
costing a round to re-derive:

- **Searching on blank scratch.**  Pointer spread is pinned at 1 on an
  all-zero tape (exhaustive to length 10), making a width-doubling stage look
  impossible.  With the scratch pattern as a free parameter, stages are found
  readily.
- **Launching a joint search from a clamped origin.**  A depth-`d` search from
  pointer 0 touches only cells `<= d`, while the first input-dependent cell is
  at 16 — so every reachable state is input-*independent*.  Four searches
  failed on this alone, each looking like a separate negative.
- **Reading a fixed cell index while the rows are diverged.**  Divergence is
  the branch mechanism *and* it desynchronizes the machines, so bookkeeping
  keyed to a cell number is wrong from the first test onward.
- **Demanding too much of one gadget.**  A "converging deposit" (`acc ^= s`
  with the pointer converged *and* clean residue) does not exist across ~2400
  states achieving the deposit — and neither condition is needed, since `<`
  reconverges for free afterwards.
- **Length-bounded suffix enumeration.**  A length-8 sweep of mixed suffixes
  returned zero in 9 seconds; the pair the enumeration misses
  (`01101101` / `10010010`, once stored and now derived by `_rescue`) closes
  with a suffix interleaving two `<` into the bracket run, so no `'[' * k`
  ever spells it.  Its column is
  *abundant* — 14375 of 804600 sparse suffixes leave it standing — but the
  walk's prefix-XOR rewrites the very cell, so the answer is produced easily
  and destroyed almost every time.

A sixth is about loop order rather than the language: a candidate-major loop
projected at 5.5 hours where a staging-major loop found the same answer in 29
minutes.  The expensive object is the staging, not the table — met again at a
different layer when the whole-arity derivation replaced per-table search.

### Why input negation is not a shortcut

The sixteen two-input tables fall into four orbits under the natural group
(permute inputs, negate inputs, negate the output), and building one
construction per orbit is tempting.  Input *permutation* is fine — reordering
which placeholder is emitted where is entirely inside the template.  Input
*negation* is not: it means the harness fills `{Xi}` with the **complement**
of its bit, so the emitted program no longer computes the requested table but
one the caller pre-transformed for it.  That is the same objection the removed
`{Ci}` placeholder answers to — a generator should derive a complement at
runtime from its own `{Xi}`, as `nocomment` does with its `s`-as-NOT gate, or
do without.

## 123 (parameterized — resolved at `n <= 3`; wider arities open)

**Resolved.  All four one-input and all sixteen two-input tables build, and
the generator ships** (`esolangs.tools.boolean.one_two_three`).  What was
wrong in the ceiling this section used to record was its *scope*: the bound
belonged to a setter choice, not to the language.

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

### Why flips alone cannot leave the affine class

Flipping is XOR, so a straight-line `1`/`2` program is affine by
construction and AND/OR/NAND/NOR are out of reach — confirmed by a lockstep
search over 567 paired-setter embeds, which finds the affine tables and
nothing else.  Under the neutral setter the printing route reaches exactly
`c XOR (subset of the inputs)`: const0, const1, b0, b1, NOT b0, NOT b1, XOR
and XNOR.  Nine `1`s from location 7 reach the write position, flipping
locations 7..0 on the way, so the tape must hold `target XOR 0xFF`
beforehand — 0xCF prints `'0'`, 0xCE prints `'1'`.  Embedding an input *at*
location 7 makes its bit toggle the answer; embedding it past location 8
makes it inert, since `byte()` never reads there.

**Reconvergent guards stay affine.**  If a guard's TRUE and FALSE paths
rejoin at the same cursor *and* the same pointer, its whole contribution is
`t · (difference in flips)` for the tested cell `t`; `t` is affine in the
inputs, so the tape stays affine and no arrangement of such guards builds
AND.  Escaping that needs the two paths to exit at *different pointer
positions*, so later code reads a cell selected by the first bit — the
pointer carrying the indicator that tape XOR cannot.

**The answer is not a cell read.**  Every tape cell ends as a fixed XOR of
the setters that touched it, so the reachable cell patterns are affine and
`(0, 0, 0, 1)` — an AND indicator — never appears among them.  What a guard
decides is *where the pointer is* when the closing `3` is reached, tested
once per pass.  A verdict accumulated over passes is not a single affine
read, which is how the termination route escapes the bound that caps
printing.

### Two search artifacts, both about dead code

**A `3` never falls into the segment after it.**  At `pos >= 0` a `3` either
jumps back past the previous `3` or forward past the next one, so the body
between a `3`-pair is entered only when the opening `3` is a NOP — which
requires `pos < 0` — or by the second `3`'s backward jump.  Guards placed in
the walk home therefore sit at `pos >= 0` and are **dead code**: instrumented
runs show their bodies executing zero times across all four rows, while a
working selector's body executes 4-8 times because it reaches its first `3`
at `pos == -2`.  Four separate guard sweeps returned nothing for exactly this
reason, and none of them is evidence about the language.

**Length-bounded sweeps decide nothing here.**  A sweep that stopped at
length 8 concluded no `1`/`2` program prints exactly `'0'` or `'1'`.  Both
are printable — `'0'` at length 14, `'1'` at length 28 — and in fact every
byte 0-255 is, settled exactly rather than by cap: with no `3` a program is
straight-line, so the reachable configurations form a finite graph over
(pointer, bits at 0-7), and BFS over its 5120 states reaches all 256 output
values.  Same failure mode as %^2^-1's NOT, where constant-building finishes
past the sweep's horizon.

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

### Three inputs: resolved, and how

**All 256 three-input tables build**, under the shipped uniform-fill
contract with each `{Xi}` embedded once in name order — no per-table setter,
no repeated slot.  What this section previously called open was a search
problem, not a language one.

Three things mattered, and the first two are the reusable ones.

**The step cap was the bottleneck, not the search space.**  Deciding a row
means running until it halts or revisits a state, and a cap of 40000 steps
made every *diverging* candidate cost the full budget.  Every row of every
plan that does build decides within 100 steps (1215 of 1232 within 50), so
the cap came down to 300 — a measured 200x speedup, and the difference
between a search that saturates at 148 tables and one that reaches 251.
Lowering it is safe because an undecided row only ever *discards* a
candidate: nothing ships on the fast evaluator's word, and every stored plan
is replayed row-by-row on the real interpreter.

**Enumeration by length runs out before the tables do.**  Shortest-first
enumeration covers 148 of 256 by ten symbols and multiplies by about four
per further symbol, so eleven is already 1.08M templates for a handful of
new tables.  What worked instead was sampling the *shape* the short plans
take — a `3`-sparse skeleton with short literal runs between the slots — at
lengths the flat sweep cannot afford.  Same lesson as the length-8 printing
sweep above, one level up.

**The last table fell to mutation, not sampling.**  `01111110` (TRUE unless
all three inputs agree) is the one popcount-only signature the counter
cannot reach alone: displacement after three uniform ±1 embeds is
`3 - 2·popcount` mod 4, which is 3 for even popcount and 1 for odd, so the
bare counter carries only popcount **parity** at three inputs.  Signature
`0110` is not a parity function, so it needs `3`'s TRUE-backward re-run
rather than a longer decode tail.  Random sampling never produced it;
applying single literal edits to the plans for the *neighbouring* tables
found it in about 2000 candidates on one core.

### Still open: four or more inputs

The projection that lifts other generators' caps still does not apply, for
the reason that always applied here: an ignored input must still be
embedded, every fill moves the pointer, and the pointer phase *is* the
computed value, so a trailing inert embed shifts the quantity the plan
decodes.  65536 tables at `n == 4` also makes a stored plan per table a
different kind of artifact than the 256 stored here.  No construction is
known.

A *runtime* (reading) two-input table remains unproduced, and the sweeps run
here do not bear on it: the shortest program satisfying the contract at all
is the length-12 echo, a genuinely two-input program needs a second read, and
the digit-valued selector a generator would need is plausibly ~30 characters
since `'1'` alone costs 28.  Closing it needs the Minifuck playbook — emit a
template and lockstep-simulate all `2**n` instantiations, accepting only a
program seen to print the table — not a longer brute-force sweep.

## RAM0, Bitdeque, Minsky Swap (parameterized template blocked — resolved)

These three were once thought blocked because their jumps are *absolute*
positions in the token/command stream — RAM0's digit-`goto`, Bitdeque's
`GOTO N`, and Minsky Swap's `~` (the Nth tilde jumps to the Nth number on
the jump line) — and the bit setter had variable length (`Z` vs `Z A`;
`INVERT` vs nothing; `+` vs nothing), so substitution changed the token
count and every jump target shifted.  A *fixed-length* setter breaks the
wall for all three: RAM0 sets ``z`` with `Z A`/`Z Z`, Bitdeque pushes each
bit with `INVERT PUSH`/`PUSH INVERT`, and Minsky Swap needs only one
command — `+` for a one, or `*` to point the ``~`` at the other still-zero
register — so no absolute index moves between instantiations (see the
`ram0`, `bitdeque`, and `minsky_swap` generators in
`esolangs.tools.boolean.parameterized`).

## Eval (nested parameterized trees — resolved)

Building a decision tree requires nesting: each subtree must be a string
evaluated with `!`.  This is a **spec** limitation (the interpreter matches
the wiki exactly): the wiki defines stringmode with no way to escape a
backtick or include a literal one, so a pushed string can never contain a
backtick and a nested `!`-evaluated subtree cannot survive more than one
wrap.  The wiki's examples only ever use single-level `!`.

The shipped generator
(:func:`esolangs.tools.boolean.parameterized.eval`) resolves the wall by
avoiding nesting altogether: the tree is stored as a flat, full binary tree
in heap (BFS) order on the tree stack, with each node's two children pinned
at fixed heap offsets (a node is ``~=~?`` plus ``i+1`` semicolons and a
``!`` — the ``?`` skip discards the right number of elements, so ``!`` pops
the 0- or 1-child), and each leaf prints its table entry.  No node or leaf
contains a quote or backtick, so the strings need no escaping and the tree
grows to any ``n``.  It is a parameterized generator, total for any arity
and table, and embeds each input exactly once.

## SLOW ACV MAMMALIAN (resolved: the tree lives in code space)

**The wall here was a search that omitted the language's one conditional.**
It held that a bit could not be both read and routed, because `ACCEPT`
appends to `lst[0]` and consuming it needs `ptr == 0` while routing
`SPRINT`s move the pointer away.  That first constraint is false and it was
load-bearing: `ACCEPT` appends *whatever the pointer holds* — the
interpreter's `n == 8` arm writes `self.lst[0]`, not `self.lst[self.ptr]` —
so nothing has to be routed to be read.  The branch is `LEAPFROG`, which
jumps exactly when `curr[-1]` is nonzero, and the just-appended bit *is*
`curr[-1]`, so `ACCEPT DIGEST LEAPFROG` is a decision-tree node three tokens
long.  The earlier re-verification searched only the *branch-free* tails, so
it never contained `LEAPFROG`, and its "0-preserving tables only" result
describes that fragment rather than the language.  The other two constraints
(no resettable constant source, `DIGEST` recovering a bit only in a sum)
dissolve once the tree exists: every path has already branched on the bits it
read, so the whole machine state is a generation-time constant.

The generator solves for each jump arithmetically rather than running
anything; the details are in
`esolangs.tools.boolean.slow_acv_mammalian`.  Every table through `n == 3`
is verified against the interpreter, plus sampled `n == 4`.

**Why the size/offset fixpoint terminates** is the part worth keeping, since
it carries no iteration cap.  A node whose reach falls short of its own
0-subtree prepends a stash chunk, buying ~255 tokens of reach, and
re-derives.  Two exits, both measured over 172452 nodes: a candidate's
landing clears the 0-arm, or the gap stops closing — the parent/child lock
the 0-arm's shed exists to break.  The stall is checked over a two-chunk
window and only after the first chunk, because the first spikes the gap and
single steps sawtooth up a few tokens; measured that way the gap fell by at
least 248 tokens every window.  The descended quantity must include the
0-arm's length: the cheaper proxy (shortfall against the node alone) looks
equivalent and is not — 13512 iterations were measured where it had gone
negative while every candidate still refused.  Chunk use is small (worst 15)
and *not* predictable from what a node opens with, since the gap moves as the
subtree it must clear moves — so a rate-derived iteration budget fits noise
rather than bounding anything.  The shed is what makes this hold from
`n == 3` on: disabling it still builds every table at `n <= 2`, where arrays
are too small to carry ballast, and stalls all 256 at `n == 3`.

**Where this leans on undefined behaviour.**  The wiki is explicit about what
the wall got wrong — `ACCEPT` pushes "onto the top of array 0" while every
other array instruction says "the array under the pointer" — and about
`LEAPFROG`.  It says nothing about what a *negative* jump target does, or
about halting at all.  The leaves end with `EXCRETE LEAPFROG`, which fires
with a negative target and so halts under this interpreter's reading of that
gap; a reading that clamped or wrapped instead would need a different leaf.
The generator also inherits the repo-wide `% 256` where the wiki says
`EXCRETE`/`PRONOUNCE` are "modulo 255" (almost certainly a typo, since a cell
holds 0-255).  That is load-bearing: leaves normalize the accumulator mod
256, and under a strict mod-255 `PRONOUNCE` they would print `0`-`@` rather
than `0`/`1`.

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

## Home Row (resolved: closed-form binary-pack-and-compare, unbounded n)

`l` loops pair strictly by order, so loops cannot nest and a bf-style
decision tree is inexpressible.  The original generator routed with `j`
(guarded moves) instead of loops, which worked only through `n == 2`: an
exhaustive search over `j`-guarded sequences showed no routing separates
`2**n` combinations onto distinct cells of the fixed 5x5 torus past
`n == 2` (the search capped at 6 of 8 combinations) -- that routing
approach tried to send the beam to one of `2**n` distinct *leaf cells*,
which is a genuine capacity wall on a 25-cell grid.

**Resolved by abandoning spatial routing for a closed-form value
construction.**  The wall was specific to *that* construction, not to the
language: Home Row's cells hold unbounded integers, so the fix packs the
`n` input bits into a single binary accumulator instead of routing a beam.
Each input bit gets its own position-stable gate -- `{Xi} l s ffff
a{2**(n-1-i)} f l`, using the same "run once iff nonzero, consuming the
guard" pattern the removed generator's `j`-tests approximated, but built
from `l`/`s` so it needs no nesting -- that adds the bit's binary weight to
the accumulator only when the bit is 1.  After all `n` gates the
accumulator holds the combination's integer index `0 .. 2**n - 1`.  A
linear chain of `2**n` equality checks then walks that index: each line
fans the accumulator out into a working copy and a backup, subtracts its
own index `k`, and gates on the difference to either print the baked
answer and halt (a match) or restore the accumulator from the backup and
fall through to test `k + 1`.  Since the packing and comparison both work
on Home Row's unbounded cells (no byte masking happens until the final
`'0'`/`'1'` answer print), there is no `n` cap at all: verified exhaustive
through `n == 3` (2048/2048 checks) and sampled correct through `n == 10`.
Program length grows `O(2**n)` from the leaf chain, the expected cost of a
linear scan rather than a genuine representation limit.  See
:func:`esolangs.tools.boolean.parameterized.home_row`.

## Assessed boolean candidates that fell through

- **%^2^-1** (wall at `n >= 2` for the *reading* model, proved in Lean —
  **resolved by parameterizing**).  Its only control flow is `t`, which
  rewinds to the program start when the accumulator is nonzero, preserving
  the accumulator across the rewind.  There is no forward jump and no way to
  branch over code, so a program cannot route two inputs to different tails.

  **The Lean wall and its scope.**
  `extra/lean/esolangs/Esolangs/PctBooleanWall.lean` proves
  `computes_ignores` — every program meeting the boolean contract (halt
  cleanly, consume both bits, print one character) computes a function that
  ignores one of its two inputs — so `no_xor` and `no_and` follow.  Two
  structural facts drive it: `n` *overwrites* the accumulator, so the state
  at the last read is a function of the last bit alone; and `t` jumps only to
  position 0, so a run that halts must have input enough for every read ahead
  of the cursor (`count_le_of_halts`), which forbids the two runs from
  diverging at a `t`.  Output therefore factors as `A(b1) ++ B(b2)`, and a
  one-character output forces one factor empty.  This is an induction over
  unbounded length, not a bounded search: the axiom audit
  (`PctWallCheck.lean`) reports only `propext`, `Classical.choice` and
  `Quot.sound` — no `sorryAx`, no `Lean.ofReduceBool`.  The Lean `stepCmd`
  was differentially tested against the shipped interpreter over 44,280
  program/input pairs with zero mismatches.

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
  106/256 with the ladder, and finally to 256/256 with the band
  construction, both below — by adding a
  third construction that composes one affine setter per input and *searches*
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

  This does **not** contradict the paragraph above, and neither does the
  band construction below: the reset still cannot *separate* rows that
  agree, and the `l` tail bound stands as stated.  It merges, and the ladder is what supplies an
  order for it to merge along — the separation is done by the weights before
  the reset ever fires, and the printing tail is the ordinary gap-1 one.  The
  amplify-then-clamp tail still never fires, and the tail bound stands as
  stated.

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

  Measured over the same random tables, old (beam ladder plus retry) against
  new (single candidate), median/worst emitted characters and build time:

  | `n` | old size | new size | old time | new time |
  |----|----------|----------|----------|----------|
  | 4 | 175 / 213 | 170 / 230 | 0.77 / 1.51 ms | 0.35 / 0.51 ms |
  | 5 | 300 / 546 | 308 / 482 | 8.68 / 35.22 ms | 1.39 / 4.39 ms |
  | 6 | 913 / 13411 | **736 / 1242** | 113.65 / 393.27 ms | **7.00 / 12.32 ms** |

  The `n == 6` worst case is where the trap lived: 13411 characters and 393ms
  becomes 1242 and 12ms.

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

### The Rust cross-checks (all eight, removed)

The whole `extra/rust` directory later went the same way, for the same
independence reason applied to its provenance rather than its breadth.
Six of the eight (Forþ, Basicfuck, Painfuck, 3x, bit~, %^2^-1) were
written in one sitting alongside — and in several cases in the same
commits as — the Python interpreters they checked, as ports of earlier
C++/Ruby references; a cross-check that shares its author's reading of
the spec catches transcription slips but not spec misreadings, which was
the value being claimed for them.  The remaining two (`unsquare.rs`,
`laserfuck.rs`, both 2022) predated the Python by four years and were
genuinely independent, but keeping two binaries would have retained the
entire toolchain cost — cargo, rustfmt, clippy, a dedicated CI job, and
the Rust half of `verify_differential.py` — for a fraction of the
coverage, so the removal was all-or-nothing and went with all.

What this costs: differential coverage for those eight languages, which
keep their Python interpreters, unit tests, and generator round-trips.
Unlike the RISC-V ports, the Rust toolchain served nothing else in the
repo — `extra/assembly` shares `_riscv_common.py`, `riscv_elf_runner.py`,
and the qemu/unicorn CI setup with the thirteen RISC-V compilers under
`src/esolangs/compilers/`, so its marginal cost is near zero and it
stays.  `scripts/verify_extra_generators.py` was Rust-only end to end
and went with it.

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
