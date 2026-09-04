
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

An enumeration cap is evidence about the enumeration, not about the
language.  Where a cap no longer exists, `docs/limitations.md` records the
current status and the history is in git.

**Re-running a wider search is mostly not how an entry here falls.**  A
sweep of this file looking for walls to re-sweep under better tooling found
almost nothing to run: the searched claims nearly all carry a *structural*
argument alongside the search, and a proof does not fall to a wider sweep.
The identity's odd-width spelling is settled by a parity argument (an odd
number of the only sign-flipping command cannot compose to `+0`), ROTfuck's
by a congruence (`q ≡ p+1` against `q ≡ p`), the `%^2^-1` ladder's span by a
subset-sum floor, 3x's by prefix-sharing.  The width-6 and `n <= 4`
enumerations in those entries are confirmations of the argument, not the
grounds for it.  What *is* cheap and worth doing is the other class:
**promoting a sampled coverage claim to exhaustive**, which needs no new
idea and either strengthens the entry or produces the counterexample the
sampling missed (ArrowQueue's `n == 4` went this way — 65536 tables, 167s).
Look for the word "sampled", not the word "wall".  **Price the promotion by
its table count before starting**, though: a boolean-generator sweep runs
`2**(2**n)` tables, so the same move that costs three minutes at `n == 4`
costs about 407 CPU-days at `n == 5` (measured for ArrowQueue below) and 38
years for `%^2^-1`.  Cheap sampled→exhaustive promotions live at `n <= 4`;
past that the entry needs an argument, not a bigger sweep.

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

**Executing a generated program proves nothing when the interpreter it runs
on is the thing in question.**  The lift's verification passed on all
`2**n` inputs at `n == 6/7/8` because it ran against the permissive
interpreter that admits the undefined region.  Execution is only evidence
against a *conforming* interpreter.  See `docs/limitations.md` for the
interpreter conformance gap this exposed.

## 3x (constant-bit guard skip is unsafe)

A guard that separates differing rows from default rows sharing the same bit
prefix cannot have a "redundant" bit test dropped, because the default rows
share the prefix too — dropping the test would misclassify them.  The sibling
idea (pre-negating stored input bits to halve `not_bit`) remains open but is
marginal.

## 123 (parameterized; wider arities gated on the verdict search, not expressiveness)

All four one-input and all sixteen two-input tables build
(`esolangs.tools.boolean.one_two_three`).

**The setter is a free parameter.**  The displacement-neutral `12`/`21` pair
keeps every instantiation in position lockstep, so the computed table is
monotone by construction (1428 templates surveyed, all monotone).  The
**±1 fill** (`1` for a one, `2` for a zero) displaces the pointer
*oppositely*, breaks lockstep, and voids monotonicity — all sixteen tables
follow, XOR/XNOR/NAND/NOR included.  (±1 had been rejected for the
**printing** route, where instantiations drift apart by bit count; that
objection does not apply to the termination route, where nothing prints.)

**The mechanism is a counter modulo four.**  Displacement after the embeds is
`(#zeros - #ones)`; `{X0}{X1}` followed by `k` ones decodes a function of
popcount alone, XNOR at `k == 2` and XOR at `k == 4`.  Asymmetric tables use
`3`, whose TRUE-backward jump re-runs the preceding segment and makes pass
count input-dependent — the one non-affine operator in the language.

Every looping row is a proven state revisit (`run_until_halt_or_cycle`
catches it), never unbounded growth, and every plan emits its slots in name
order with each `{Xi}` once.

### Wider arities: three stages proven total, one conjecture left

`one_two_three_construct` builds tables past three inputs via a merge phase
(one synchronized walk-descend-pop per mark, keeping exactly one mark per
set bit), a separation phase (a planned decode tree, deterministic and
total at every arity via a `2**(n+1)` mark base), and a verdict phase that
kills 1-rows bottom-up using two mark geometries (uniform, then staggered
`+1/+3`) tried in order — together deterministic and strictly stronger than
either alone.  The endgame closes with a residue-fusion argument, replaying
in closed form rather than one command at a time (95s to 0.28s at five
inputs).

What is *not* proven is the verdict search itself: it remains a bounded DFS
over kills, boosts and ring rounds, and its totality is a conjecture —
supported by an exhaustive sweep (all 276 tables through three inputs) and
random sampling at four and five, not by an argument.  A fixed budget can
never be total across arities anyway: a table takes `2**n` bits to state, so
template length and build work are exponential in `n` no matter the
pipeline.

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
count, which is what `_POLYNOMIAL_MAX_INSTRS = 138` caps.  The generator
builds both a decision tree and a residual-merge state machine (an ordered
BDD, merging any two prefixes with the same residual subfunction) and emits
the shorter: parity renders through `n == 8` at 106 instructions, while
random dense tables, whose residuals do not merge, start refusing at
`n == 6`.  A table that collapses to few states renders at any width; what
is capped is the ones that do not collapse.

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

  **All four one-input functions are expressible**: NOT is `nss` + `i` * 31 +
  `pe` (36 commands), computing `x -> -x + 97` so that 48 -> 49 and 49 -> 48.

  **Three inputs are total — 256/256 — via the band construction, keyed on
  the printing command.**  `l` spells the accumulator in decimal and needs it
  to *be* 0 or 1; `e` prints `chr(acc & 0xFF)`, so a row only has to be
  **congruent** to 48 or 49 mod 256, and with residues as the target the
  over-3003 reset can be used repeatedly (it merges a class onto 0 without
  splitting rows that agree, so separation must happen before it fires).  The
  band construction weights each input by a multiple of 256 (all rows start
  congruent), sorts rows by the weighted sum into runs, and clears one run
  per stage from the top, since the reset only wipes the largest values.
  Survivors park back under the limit between stages via one congruence per
  stage, `U ≡ (live − band) − v (mod 256)` — nothing is searched.  Stage counts
  follow the run structure exactly: 2/14/42/70/70/42/14/2 tables at 0–7
  stages.  All 256 are interpreter-verified on every row.

- **Is the `%^2^-1` fold total?**  Rows start at `-step * r`, so the ladder
  spans `step * (2**n - 1)` and must fit inside `[-3003, 0]` (a zero
  accumulator).  Distinctness, not uniform spacing, is what the fold needs —
  two rows sharing a value merge on the first cut and can never separate —
  and the exact floor is `S >= 2**n + 1` (the `2**n` subset sums are distinct
  non-negative integers, the minimum weight is 2, so nothing sums to 1 or
  `S - 1`).  The ladder `(2, 3, 4, 8, 16, …, 2**(n-2))` meets it exactly:
  **ten and eleven inputs build and print every row on the interpreter**
  (eleven costs 2049 against a uniform ladder's 4094).

  **Twelve is walled for the whole ladder family.**  The doubling `m` — the
  only way to reorder groups, since wipes alone cap live spread at 3003 and
  leave cyclic order invariant — is offered only when spread `<= 3002`.  Any
  ladder laying `2**12` distinct positions spans at least 4095 wherever it
  sits, so no twelve-input ladder ever gets a doubling; the search from a
  twelve-input start exhausts (empty heap) after 15-121 states depending on
  the table, where four inputs finds a plan in 120 and eight hits its cap at
  17394 — real negatives, not a broken probe.  Thirteen needs no algebra at
  all: `2**13` distinct positions exceed the 6007 values a `p` can address.
  A two-sided ladder (doubling the available positions to `[-3003, 3003]`)
  was tried and served 0 of 18 tables the packed ladder didn't, because the
  span is the binding resource, not the positions.

  So: total at every arity it enumerates, reaching eleven (`n <= 4`
  exhaustive, five through eleven executed samples); walled at twelve for
  this ladder family specifically — a construction that does not lay all
  `2**n` rows before planning would not inherit the span bound.

  **Interleaving the laying (lay some inputs, fold, lay the rest) is open
  and not walled.**  It would avoid the twelve-input span bound entirely,
  since that bound comes from holding all `2**n` rows apart at once.
  Measured components: schedule arithmetic admits `n <= 13` (peak point
  count stays far below `2**n` because cofactor strings collapse — only 510
  live points at twelve inputs); merges work at every tested size; program
  size is fine (~0.1-0.3 MB at twelve inputs); and re-tightening after a
  compaction converges geometrically via "widen to exactly 3003, then
  contract at `cmin`" (verified at k = 16/32/64/128).  Chained end to end
  with the shipped move set, it **completes at eight and nine inputs**, ten
  reaches stage 6 of 10, eleven stalls at stage 6 of 11, twelve at stage 7 of
  12 — the separator is the point count at the arity's first
  merge-requiring stage (32 at eight/nine, then 64/128/256), and interior
  duplicates among that many points are reachable in principle but explode
  in search cost (113034 states at nine, a 2M cap at ten).  So interleaving
  builds today at eight inputs, short of the packed ladder's eleven; the gap
  to thirteen is planner engineering, not a discovered obstruction.

  Note what the twelve-input bound is *not*: the fold's, not the generator's
  — the cascade builds every conjunction/disjunction of literals at any
  width (138 characters), and only a *generic* table past eleven inputs
  reaches the ladder's limit.  The Lean theorem covers the reading model
  only; nothing here bounds embedded-input programs in general.

- **The Temporary Stack**: the auto-drain condition `sum(stk[1:]) / 2 >
  stk[0]` is a real input-dependent branch (checked against the interpreter
  restored from `06687a2^`; `o v49 @ v50` prints `'0'` for input `'1'` and
  stays silent for `'0'`), and in numeric mode the drain prints `front - 1`
  directly, so no 49/50 constant is needed.  But the generator this permits
  is only **partial**: two inputs reach 9 of 16 tables.  NAND, NOR, XOR and
  XNOR need an input-gated *silent* death, and none exists — a death is
  silent only at depth 1, whose condition `sum(tail) / 2 > 0` is true on
  every row once input has landed, so every death is either
  input-independent or noisy.  The language supports a partial generator of
  roughly ArrowQueue's threshold class; the removal's other ground (the
  literal-embed text generator, see `docs/limitations.md`) is untouched.

- **WII2D**: the accumulator never affects control flow (`^v<>` set the
  direction, `@` jumps unconditionally to the closest `@`), so there is no
  value-testable branch to route a decision tree on.  **Resolved by the
  n-embedding chain** (`esolangs.tools.boolean.wii2d`): the branches are
  routing, not value tests, and the *accumulator arithmetic* decodes the
  input.  Each input is embedded exactly once as a junction whose two
  branches are op strings that transform the accumulator before re-merging
  ahead of the next junction; the final accumulator is the table entry.

  The op strings are **constructed, not searched**: nothing keeps an
  alternative, widens a beam, or retries.  Because no cell's behaviour can
  depend on the accumulator, a junction's two op strings are shared by every
  prefix that reaches it, which leaves exactly one shape — a chain that
  folds the bits into a single number, then a decode that turns that number
  into the entry.

  *The chain* walks the table's decision diagram one input at a time, taking
  the first legal pair from a fixed catalogue (`_WII2D_JUNCTIONS`).  A pair
  is legal unless it lands two *different* residual functions on one
  accumulator value.  Horner's `('*', '*+')` ends the catalogue and is legal
  unconditionally — its children `2v` and `2w + 1` differ in parity, and
  `2v == 2w` forces `v == w` — so **the walk is total and cannot dead-end**.

  *The decode* is built out of folds: `s` is the only op that is not
  order-preserving, and `'-' * c + 's'` merges exactly the pairs equidistant
  from `c`, so folding drives the live values together until two remain —
  which a threshold `'-' * t + '/' * k + '+'` reads out.  At each step it
  takes the **single** best fold under a fixed ranking (magnitude, then live
  count, then length); there is no beam and no width ladder.

  **The single-candidate rule is exhaustively verified.**  All 256 patterns
  at `D == 8` and all **65536 at `D == 16`** — the widest domain the general
  path asks for — decode under it.  Four different rankings were swept
  exhaustively at `D == 16` and **all four are total**, so the result is a
  property of the fold algebra rather than a lucky tie-break.

  A guard admits or refuses a table by `min(worst case, real domain left by
  the chain walk)`.  Dense `n == 7` builds (median 2776 chars, 65.1 ms);
  dense `n == 8` is still refused (real domain 128).  A second bound,
  `_WII2D_MAX_REAL_DOMAIN = 256`, catches tables whose real domain runs
  *above* the worst case when no merge is available and the walk falls
  through to Horner — structured tables can reach 1025 points at `n == 7`,
  which does not return within minutes, so 256 refuses those while still
  admitting every overshoot measured to decode.

  **Ranking the folds by emitted width is much worse.**  Magnitude-first
  buys small centres later by keeping values small now: cheapest-centre-first
  emits 940/5168/4497 characters at `D == 32` against magnitude-first's
  260/259/235, and at `D == 64` cheapest-centre walks into a doubling trap —
  bit length climbs from 10 to 428972 over 20 steps, one step costing 52
  seconds — because `s` squares, so a fold roughly doubles every live value's
  bit length, and only magnitude-first keeps that from compounding.

  Most remaining build time is speculative compression, not the fold: a
  candidate is cheap to enumerate and expensive to compress, so
  `_WII2D_SHORTLIST` compresses only four candidates and drops the rest,
  keeping the count flat in the domain.  Compression is a genuine
  contraction (a measured 529 collapsing to 17), not a predictable one, so
  the shortlist is an approximation, not a bound: it can pick a candidate
  whose eventual compressed magnitude loses to one it discarded.

  There is no useful universal fallback (a tree would need each input
  re-embedded at every node, which WII2D has no way to store).  There is,
  however, a **total fold construction** proving representability at any
  finite domain: given two live values needing the same bit, a chosen offset
  `C` and merge modulus `M = (a-C)^2 + (b-C)^2` merges them by injective
  translation then one square-fold, excluding same-bit collisions by
  construction, so each round strictly lowers the live count.  This is an
  induction proof that the fold *algebra* can decode every finite binary
  pattern — not a practical generator path, since each round squares the
  previous magnitude (doubly exponential in the domain).  The shipped
  decoder's fixed ranking, shortlist and centre cap are size policies, not
  this construction.

  The *chain* half is total; the shipped greedy *decode* is exhaustively
  verified through `D == 16` but its centre cap is a real ceiling: for every
  even cap `K`, the pattern `0 1**K 0 1` defeats every permitted fold (a
  doubled fold at centre `c` sees the unlike pair `(0, c)`, an undoubled one
  sees `(0, 2c)` through `K/2` and `(K+1, 2c-K-1)` above it).  The actual cap
  is 4096, so this is a 4099-point counterexample — beyond the default index
  domain, but it settles the claim that the greedy rule is total.  Raising
  the cap to `K+1` admits the same-bit pair `(0, K+1)`
  (`test_decode_centre_cap_has_a_constructed_miss`).

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
  A constant slice **folds** to a single leaf rather than the branches
  that would all reach it.  The ring's corner pops must still consume
  exactly the four loop components, so a folded ``1`` leaf carries a
  *drain* per skipped bit — a ``+`` whose two exits reconverge, popping
  the bit the skipped branch never did and pushing nothing.  A folded
  ``0`` leaf needs none: it halts by leaving the grid, which no queue
  content prevents.

  **Every table at every arity is supported, and this is now proved
  rather than swept** — see
  [`docs/arrowqueue_generator.md`](arrowqueue_generator.md).  The
  construction factorises: the header is exactly ``4n + 1`` rows and hands
  the tree a queue of ``bits + R,D,L,U`` heading down column 1; the
  routing step is an induction over ``_connect``; and the leaves are
  finitely many shapes.  The table's contents only choose *which* leaves
  appear, never how the program is routed, so no lemma quantifies over
  tables.  ``n <= 4`` is also swept exhaustively — the 65536 four-input
  tables built, instantiated over all sixteen input combinations and run to
  a halt-or-cycle verdict, 0 failures in 167s — and whole programs at
  ``n = 6, 8, 10, 12`` run correctly over all ``2**n`` inputs (the
  ``n == 12`` case is 4096 inputs against a 227,937-byte program).
  Program size doubles per input level.  ``n == 4``'s sweep cost under
  three minutes because the verdict comes from state-cycle detection
  rather than a step budget, so a ``1`` leaf's sustaining ring is proved
  looping the moment it repeats a snapshot.

  One subtlety the proof had to close: a **bare** ring sustains when
  entered heading right at its ``(0, 0)`` but *halts* when entered heading
  down at ``(0, 1)``.  The two entry styles are not interchangeable.  What
  makes the construction correct is that a bare ring is never the
  top-level tree — a constant-``1`` table folds to a leaf with ``k = n``
  drains, and ``n >= 1`` is enforced — so the bare ring only ever appears
  nested at column offset 3, where entry is rightward.

  **``n == 5`` does not promote, and the reason is the table count rather
  than the runner.**  Priced by timing the same build-instantiate-verdict
  loop on random tables: 1.0 ms/table at ``n == 3``, 2.5 ms at ``n == 4``,
  8.2 ms at ``n == 5`` (programs 183, 447 and 1081 bytes — the per-table
  cost tracks the doubling program size at about 3.3x per level).  The
  ``n == 4`` figure reproduces the 167s above (2.5 ms x 65536 = 166s),
  which is what makes the next step's extrapolation trustworthy: ``n == 5``
  has ``2**32`` tables, not 65536, so the sweep is **about 407 CPU-days**.
  That is a table-count wall, not a speed one — a runner 100x faster still
  leaves four CPU-days, and no amount of per-table optimization divides
  ``2**32`` down to the three-minute job ``n == 4`` was.  This is the same
  shape as ``%^2^-1``'s ``n == 5``: the cheap-promotion pattern reaches
  exactly as far as ``2**(2**n)`` stays small, which is ``n <= 4``.

  **The coverage question is settled anyway, by proof rather than by
  sweep** ([`docs/arrowqueue_generator.md`](arrowqueue_generator.md)).
  Since the routing never depends on the table's contents, ``n == 5`` and
  every arity above it are covered without enumerating a single one of the
  ``2**32`` tables.  The 407-CPU-day figure remains the price of an
  *exhaustive sweep*, which is now a redundant way to learn what the
  induction already gives — a worked instance of the general rule that
  these walls fall to proofs rather than to wider sweeps.

  The pricing run checked its tables rather than only timing them (500
  random tables across ``n == 3``-``5`` plus the constant, half and
  alternating ``n == 5`` edge tables, 0 failures) and carries a positive
  control, since a timing sweep that silently stopped verifying would report
  the same seconds: inverting the expected table fails all 32 combinations,
  and blanking the sustaining rings' centre ``~`` fails **exactly** the
  table's one-entries (10 of 10 on the sampled table), which is the hang
  gadget's own signature.

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
``n <= 4`` tables exhaustively — the 65536 four-input tables built,
instantiated over all sixteen input combinations and checked for both
properties, 0 failures in 64s.  Past ``n == 4`` the sweep is priced out
(``2**(2**n)`` tables), and the coverage rests instead on a **uniform
argument**, recorded in ``docs/a_painter_ant_uniform_proof.md``: the leaf
geometry is arithmetic (superincreasing weights put leaves exactly 4 apart
and keep head walks off foreign leaves), a blocked run is a no-op at any
length so the arity-dependent run magnitudes drop out, and the cycle-2
dance is a paint-free fixed point over a three-offset state set whose
30-entry motif table, learned at ``n == 5``, replays with 0 prediction
errors at ``n`` of 6-9.  The general method — encode each combination as a
distinct leaf position reached by the weighted bit-moves, and anchor the
cycle-2 run back onto that leaf — is recorded in
``docs/a_painter_ant_generator.md``.

``n == 4`` was previously sampled at three tables; promoting it cost about
a minute because the stability verdict is a **state fixed point** rather
than a cycle budget.  The generator only ever paints white, so the grid is
monotone and the per-cycle transition depends only on (grid, position):
when the whole state after cycle 2 equals the state after cycle 1, every
later cycle repeats it exactly.  That is the same "a repeated snapshot
proves the loop" move ArrowQueue's promotion used, and it is *stronger*
than the ``box(1) == box(10)`` comparison the checked-in tests use — a
proof rather than ten sampled cycles — while costing two cycles instead of
ten (about 50x faster per table, which is what made 65536 tables cheap).
The sweep carries a positive control: blanking the template's painted
leaves must break exactly the table's one-entries (8 of 16 for XOR4), so
the zero-failure result is not a probe that never fired.

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
return-value-threading idiom to convert.  Its depth is still the host's
rather than the language's (measured at 248 levels, about four Python frames
per call), but `step` now converts the `RecursionError` into a `HaltError`
naming the limit, so the ceiling is reported rather than leaked.

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
