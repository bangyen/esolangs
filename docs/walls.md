
# Generator and transpiler walls

The full wall arguments behind the blocker tables in
[`docs/limitations.md`](limitations.md) — the negative result and the
structural reason it cannot be lifted.  Completed constructions (the
working generators, and how they work) live in the commit history, not
here.

## 6-5 (35 branch labels bound the tree)

The generator is a decision tree that folds its constant subtrees, and 6-5
has exactly 35 branch labels (`0..9`, `A..Z`), one spent per internal node
the fold leaves standing.  That makes the limit a property of the *table*,
not of `n`: the fold's worst case is an alternating table, which folds
nothing and spends `2**n - 1`, so the tree is total through `n == 5` (31)
and begins refusing at `n == 6` (63).  Tables that fold hard still render at
any width — AND-`n` needs only `n` labels.

An arithmetic kernel used to catch the `n > 5` region by embedding the table
as a single integer (6-5's pointer cannot net-advance, so there is no
computed array indexing), at O(`2**(2**n)`) characters for dense tables
behind a ~2 MB setup guard.  It was **retired**: a buildable `T` confines
the ones to low indices, which leaves the rest of the table constant, which
folds well inside the label budget — so it never covered a table the tree
could not.  A search over contiguous families at n=6,7,8 and ~18000 random
tables found no counterexample.

## ZTOALC L (dense non-symmetric n > 3 wall, re-verified)

All Collatz trajectories converge to the `16, 8, 4, 2, 1` tail, so a dense
full tree like XOR4 has every leaf's tail sweep through another leaf.  For
**popcount-symmetric** tables the generator falls back to a branch-free
*linear* program: sum the input bits into one accumulator and look the
result up in a small `n + 1`-entry table (XOR4's linear program is 524,288
lines, `2**19`, under the `2**22` gate).  That shape does not carry over to
dense **non-symmetric** tables, and not just because the result table is
bigger: a non-symmetric table needs each combination's raw *position*
(`0..2**n - 1`), not its popcount, and ZTOALC L's expression grammar has no
multiply, so computing a positional index from `n` bits would need a
weighted accumulation (`bit_i * 2**(n-1-i)`) that `+`/`-`/`=` cannot
express in one step.  Even approximating it with repeated addition and a
full `2**n`-entry result table (one distinct literal per combination,
instead of the symmetric case's shared `n + 1` values) reaches `2**33`
lines at `n == 4` — past the `2**22` gate by a wide margin, not under it.

Re-verified against the interpreter: sweeping the tree placement's search
parameter (`b1`) to ~500,000 values per table (125x the shipped budget) found
no collision-free placement for three independent dense, non-symmetric
`n == 4` tables, each exhausting in under a minute — a search-budget problem
would show as a timeout, not a fast, complete exhaustion.  The wall holds;
`n <= 3` exact plus popcount-symmetric tables at higher `n` is the ceiling
for the tree-shaped construction.

## 3x (constant-bit guard skip is unsafe)

A guard that separates differing rows from default rows sharing the same bit
prefix cannot have a "redundant" bit test dropped, because the default rows
share the prefix too — dropping the test would misclassify them.  The sibling
idea (pre-negating stored input bits to halve `not_bit`) remains open but is
marginal.

## Minifuck (0-preserving functions, n <= 3)

The two-input limitation is structural: the decode suffix flips the pool LSB
only when the pointer sits at cell 7, and `[`'s skip always maps bit 0 to
the higher pointer position, fixing the pointer orientation.  XNOR, NAND,
NOR, NOT-b0, NOT-b1, and const-1 were not reachable in the original analysis
(no complemented read-prefix exists to length 11, full-program search to
length 14 finds none, and a re-verification search to length 34 still finds
none).  The n == 4 walker stage additionally cannot reach the 8 distinct
pointer positions a third bit needs.  The single-input case is *not*
0-preserving-bound (a re-verification found NOT and const-1 at lengths
17-18), so the generator covers the four one-input functions plus the
0-preserving two-input tables, and nothing past `n == 3`.

## 123 (four one-input functions)

A decision tree needs the `3` jump, which on a TRUE/FALSE bit jumps to the
*nearest* preceding/following `3` (not bracket-matched): FALSE always lands
just past the next `3` (skip forward), TRUE always lands just past the
previous one — which, absent an intervening `3`, is the start of the very
segment already being executed.  So the only constructible pattern is
"repeat the region before the `3` while TRUE," never a jump to an
independent branch target.

Re-examined after the tape was corrected from a single capped byte to
genuinely unbounded bit storage (see the pointer-cap fix in
`one_two_three.py`): the wall is not the tape size, it is two mechanisms
that survive the fix unchanged. First, `1` flips the bit under the pointer
*before* moving, and a read always resets the pointer to location 0 (the
byte's MSB); reaching the write position at -2 requires passing through
location 0 via `1`, so the read result is corrupted en route on every
attempt — confirmed by tracing a read-then-navigate-to-write program, whose
output byte differs from the input by exactly its MSB. Second, since a
`3` that can ever evaluate TRUE must re-run the segment before it, and that
segment is the only place a second input's read could plausibly follow the
first's, a TRUE evaluation re-reads stdin and desyncs every input read
after it — so no read can safely precede a `3` capable of going TRUE.  A
structured search (400k+ programs built from read/march/jump blocks, not
raw random characters) found no two-input AND/OR/XOR/NAND/NOR/XNOR under
either bit-encoding.  The four one-input programs were too trivial to keep,
so the boolean generator was removed and stays removed.

**The parameterized case is also walled, on a third mechanism.**  Embedding
each input at compile time (the WII2D-style convention) does clear both
mechanisms above -- with no ``,`` there is no pointer-reset corruption and
no re-read desync -- and it buys real input-dependent behavior the runtime
case never reached: over templates to length 7 with each ``{Xi}`` placed
exactly once and a same-width setter (``1`` for a one, an executed no-op
for a zero), ``{X0}{X1}211`` emits for ``(1, 1)`` and stays silent
otherwise, an AND.  What blocks a ``'0'``/``'1'`` generator is *output*.
Location 0 is both the byte's MSB and the only cell the ``-4`` pointer wrap
returns to, so the tape walk that builds a target byte is the same loop
that would have to be stopped to print exactly once -- and ``3`` cannot
stop it, since a TRUE ``3`` re-runs the segment it sits in rather than
reaching an independent target.  Confirmed against the interpreter: no
program over ``1``/``2`` to length 8 prints exactly ``"0"`` or exactly
``"1"``, and every short program that writes byte 48 or 49 does so inside a
loop that enumerates all 256 bytes, printing each -- the digits are
incidental to the sweep, not selected.  What survives is emission-vs-silence,
which is the termination convention (see below), not a printed answer;
whether that convention covers all 16 two-input tables here is a separate
assessment, unbuilt.

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

The wall recorded here held that the n-bit case was blocked by three
mutually conflicting constraints: that `ACCEPT` appends the bit to `lst[0]`
and consuming it needs `ptr == 0`, while routing `SPRINT`s move the pointer
away, so a bit could not be both read and routed; that the only constant
source accumulates rather than resets, so the `[48, C, m]` triple a branch
needs cannot be assembled; and that `DIGEST` recovers a buried bit only as
part of a sum.

**The first constraint is false, and it was load-bearing.**  `ACCEPT`
appends to `lst[0]` *whatever the pointer holds* — the interpreter's `n == 8`
arm writes `self.lst[0]`, not `self.lst[self.ptr]` — so nothing has to be
routed to be read.  The branch is `LEAPFROG`, which jumps exactly when
`curr[-1]` is nonzero, and the just-appended bit *is* `curr[-1]`.  Entering
with `acc % 256 == 48` normalizes the digit to a clean `0`/`1`, so

```
ACCEPT DIGEST LEAPFROG
```

is a decision-tree node three tokens long: a `0` falls through, a `1` jumps.
The pointer never leaves array 0 and the tree lives in code space.

The earlier re-verification searched only the *branch-free* tails, so it
never contained `LEAPFROG` — the language's one conditional — and its
"0-preserving tables only" result describes the branch-free fragment rather
than the language.  The other two constraints dissolve once the tree exists:
every path has already branched on the bits it read, so the whole machine
state is a generation-time constant, and an accumulating constant is not a
problem when the generator knows exactly what accumulated.

The shipped generator
(:func:`esolangs.tools.boolean.slow_acv_mammalian.slow_acv_mammalian_boolean`)
aims each jump by *measuring* rather than solving.  Every arithmetic knob
here ties the array head to the array sum — `SEED` bumps both — so offsets
that look independent cancel, and each state reaches only a handful of token
indices.  What makes that enough is that a subtree ends in a halting leaf,
so the tokens after it are unreachable: the generator emits the node,
measures where the 1-branch actually lands, and pads the dead gap out to
meet it.  `EXCRETE` stashes bytes to raise the reachable band and `CONSUME`
pops them back to lower it; both directions are needed, since a 0-subtree
inherits its parent's array and a grow-only sum would track the layout it
has to clear, which is what stops the tree converging past two levels.

The tree is uniform depth `n`, so a constant table still reads all `n`
inputs.  Verified against the interpreter: every table through `n == 3`
(4 at `n == 1`, 16 at `n == 2`, all 256 at `n == 3`, zero failures), plus
an `n == 4` spot check.  Programs run 2697-5776 tokens at `n == 3`.

**Generation cost, not a cap.**  Aligning a node rebuilds its 0-subtree
once per candidate landing, so the builds compound with depth: 10 at
`n == 1`, 155 at `n == 2`, 5504 at `n == 3`.  A table takes ~3.5s at
`n == 3` and ~18 minutes at `n == 4` (10880 tokens), which is slow but not
a wall -- memoizing `_subtree` on its state would flatten it if `n == 4`
ever needs to be routine.

**Where this leans on undefined behaviour.**  The wiki is explicit about
the fact the wall got wrong — `ACCEPT` pushes "onto the top of array 0",
while every other array instruction says "the array under the pointer", so
the read genuinely is pointer-independent — and about the branch:
`LEAPFROG` jumps "if the last value in the array under the pointer is not
0".  It says nothing, though, about what a *negative* jump target does, or
about halting at all.  The leaves here end with `EXCRETE LEAPFROG`, which
fires with a negative target and so halts under this interpreter's reading
of that gap (see the interpreter's module docstring).  A reading that
clamped or wrapped instead would need a different leaf.

The generator also inherits the repo-wide `% 256`, where the wiki says
`EXCRETE`/`PRONOUNCE` are "modulo 255" — almost certainly a typo, since a
cell holds 0-255, and the same choice is already baked into the text
generator's `gcd(q + 1, 256) == 1` walk.  It is load-bearing here: leaves
normalize the accumulator mod 256, and under a strict mod-255 `PRONOUNCE`
they would print `0`-`@` rather than `0`/`1`.

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

## Polynomial (numeric root-finding ruled out; caps at n <= 4)

The generator emits exact integer polynomials whose coefficients far exceed
float64's exact-integer range (2**53) once a few instructions accumulate —
`'Hello, World!'` has coefficients up to 10**95 — so every floating-point
solver (high-precision `mp.polyroots`, companion-matrix QR, change-of-scale)
silently solves the wrong polynomial, and a residual-based gate cannot work
(the ill-conditioning ~1e16 makes wildly wrong roots look right).  The
interpreter factors the monic integer polynomial over Z with sympy instead.
That exact factorization defines the boolean generator's practical bound:
`n == 4` (degree 184) factors in ~10s, while `n == 5` (degree 376) does not.

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

- **%^2^-1** (wall at `n >= 2`, proved in Lean): its only control flow is
  `t` — rewind to the program start when the accumulator is nonzero — with
  the accumulator preserved across the rewind.  There is no forward jump and
  no way to branch over code, so a program cannot route two inputs to
  different tails.

  **All four one-input functions are expressible**, which an earlier
  length-8 search missed: identity is `ne`, the constants go through `'`,
  and NOT is `nss` + `i` * 31 + `pe` (36 commands), which computes
  `x -> -x + 97` and so maps 48 -> 49 and 49 -> 48.  A NOT program needs
  ~20+ commands to build the additive constant out of `s`/`i`, well outside
  a length-8 sweep — the old entry's claim that NOT fails was wrong.

  The real wall is at two inputs, and it holds at *any* program length:
  `extra/lean/esolangs/Esolangs/PctBooleanWall.lean` proves
  `computes_ignores` — every program meeting the boolean contract (halt
  cleanly, consume both bits, print one character) computes a function that
  ignores one of its two inputs — so `no_xor` and `no_and` follow.  Two
  structural facts drive it: `n` *overwrites* the accumulator, so the state
  at the last read is a function of the last bit alone; and `t` jumps only
  to position 0, so a run that halts must have input enough for every read
  ahead of the cursor (`count_le_of_halts`), which forbids the two runs from
  diverging at a `t`.  Output therefore factors as `A(b1) ++ B(b2)`, and a
  one-character output forces one factor empty.

  This is an induction over unbounded length, not a bounded search: the
  axiom audit (`PctWallCheck.lean`) reports only `propext`,
  `Classical.choice`, and `Quot.sound` — no `sorryAx`, and no
  `Lean.ofReduceBool` (so no `native_decide`).  The Lean `stepCmd` was
  differentially tested against the shipped interpreter over 44,280
  program/input pairs with zero mismatches.
- **The Temporary Stack**: the auto-drain is the only output, and it prints
  `front - 1` for the *oldest* stack element when `sum(rest) / 2 > front`.
  An input-dependent `'0'`/`'1'` (48/49) output therefore needs the input to
  select a 49/50 constant, but the only value-to-length conversion — the
  front element popping — requires `front < input / 2 < 24`, so the front is
  at most 24 and prints garbage, while the raw input at the front prints
  `input - 1` (47/48).  Neither is a `'0'`/`'1'`.  Exhaustive search to
  length 5 finds no identity or NOT program, and `\` (while nonempty) never
  terminates except via the fixed 15-command stack reset, so there is no
  input-dependent branch either.  The language was removed: its text
  generator is a literal-embed (the text is pushed as a `*` string literal)
  and, with the boolean generator walled, it had no computational generator
  to stand on — see the tightened generator-story criterion in
  `docs/limitations.md`.
- **WII2D**: the accumulator never affects control flow (`^v<>` set the
  direction, `@` jumps unconditionally to the closest `@`), so there is no
  value-testable branch to route a decision tree on.  **Resolved by the
  n-embedding chain** (:func:`esolangs.tools.boolean.wii2d.wii2d`):
  the branches are routing, not value tests, and the *accumulator arithmetic*
  decodes the input.  Each input is embedded exactly once as a junction whose
  two branches are op strings that transform the accumulator before re-merging
  ahead of the next junction; the final accumulator is the table entry.  The
  ops are not monotone (`s` sends -1 to 1), so the decoding works for any
  table at small arity (two inputs use a closed form — bit 0 packed as -1/0,
  each column decoded by a single op).  The op strings are **constructed, not
  searched**: because no cell's behaviour can depend on the accumulator, a
  junction's two op strings are shared by every prefix that reaches it, which
  leaves exactly one shape.  The first `n - 1` junctions accumulate the bits
  into an index by Horner's rule (`('*', '*+')`), and the last junction's two
  branches decode that index into the table's two columns.  The decode is
  built out of *folds*: `s` is the only op that is not order-preserving, and
  `'-' * c + 's'` merges exactly the pairs equidistant from `c`, so folding
  drives the live values together until two remain — which a threshold
  `'-' * t + '/' * k + '+'` = `[x >= t]` reads out.  Compression (`/`,
  steered with `+` when a plain halving would collide two values needing
  different bits) keeps the fold centres narrow enough to spell out in the
  grid.  Every 0/1 pattern on 16 points (the `n == 5` decode domain) folds,
  so every table through five inputs is reachable, and dense non-symmetric
  tables reach `n == 6`.  Symmetric tables (AND/OR/XOR/majority/threshold-k
  of any arity) get their own routes first: parity/XNOR is exact and O(1) at
  any `n` (pack bit 0, then fold every later bit with `-s`, which flips 0/1
  since `(v-1)**2` sends 0->1 and 1->0), and other symmetric tables take a
  popcount-accumulator prefix plus the same fold decode over `n` points
  instead of the full `2**n` rows — majority-of-20 constructs in a fraction
  of a second.  Past `n == 6` the general (non-symmetric) path raises
  :class:`ValueError`: the decode domain doubles with each input and the op
  strings it produces grow past any width worth emitting (a 64-point decode
  measured 187243 cells), so large dense non-symmetric tables are out of
  reach, and there is no universal fallback (a tree would need each input
  re-embedded at every node, which WII2D has no way to store).

  **This replaced an earlier chain search.**  A previous note here recorded a
  search-free chain as "assessed and found not to generalize", on the ground
  that the final decode must hit one specific function out of
  `2**(2**(n-1))`, while the count of *usable* (pure 0/1-output) op-strings
  up to length 6 barely grows with length (8, 15, 24 at lengths 4, 5, 6) --
  coverage falling from 94% at `n == 3` to 0.04% at `n == 5`.
  That measurement was of the wrong thing.  It counted how many decodes could
  be *drawn from a fixed pool of short op-strings*, which is a real bound on
  picking a decode but not on **building** one: the fold construction above
  composes a decode of whatever length the pattern needs, so the pool never
  has to contain the answer.  Every one of the 65536 patterns on the 16-point
  `n == 5` domain folds -- the case the old note put at 0.04% coverage.  The
  counting bound is still real, and it is why the general path stops at
  `n == 6`; it just binds at a much higher arity than a fixed-length pool
  suggests.

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
instead of waiting out a wall-clock timeout.  It requires: a **complete**
snapshot (the machine's internal fields, including the input-cursor
position — the VM's language-shaped `ip`/`memory`/`stack` view is not
enough); determinism (LaserFuck's random heading, WII2D's `?`, and
Painfuck's `y` are excluded); and a `step()`/`halted` state object (only
the VM set qualifies — whole-program `run()`s expose no internal state to
hash).  It catches *cycles*, not every hang: an unbounded-growth loop
(`+[>+]`, the tape grows forever) never revisits a state, so the wall-clock
timeout stays as the backstop for that class, and for the fuzzers (which
don't control the program shape the way hand-written tests do).

Detection uses Brent's two-pointer algorithm rather than a hash set of
every visited state: one stored "tortoise" snapshot is compared against
the live machine on every step, doubling the gap between checkpoints each
time the gap is closed.  This holds O(1) snapshots instead of O(cycle
length), at the cost of stepping up to ~2x past the cycle's start before
returning — callers only get the True/False verdict, not the machine's
state at the moment of detection.

`tests/fuzz/test_interpreters_robustness.py` decides the empty-program invariant
by state-cycle detection for forty-eight string-based step-capable
machines (brainfuck, S*bleq, Dimensional, 123, Eval, Modulous, Qoibl,
Point Break, Forþ, AddSubJump, Bitdeque, BrainIf, Minifuck, Taglate,
ROTfuck, Circlefuck, BFStack, Decleq, 6-5, Back, BIO, NoComment, 3D
Brainfuck, Factor, Basicfuck, bit~, Collatz Multiverse, Polynomial,
Grapheme, RAM0, Minsky Swap, Home Row, Unsquare, %^2^-1, Suffolk,
Container, Nevermind, BF-PDA, 3x, Sophie, Jaune, SLOW ACV MAMMALIAN,
ZTOALC L, Between, MyScript, Lamfunc, Forbin, Suptiftam), and keeps the
SIGALRM backstop for the rest (Painfuck's `y`, WII2D's `?`, and
LaserFuck's random heading are non-deterministic).  Every registry
language is now step-capable: `_VM_ADAPTERS` in `esolangs.vm` covers
the whole registry, so `make_vm`'s `KeyError` -> `UnknownLanguageError`
fallback for a registered-but-uncovered language is exercised in the
tests by temporarily removing an adapter, not by a real example.
MyScript's frame stack only unrolls a *top-level* `while` into
resumable steps; a `while` nested inside a function call still runs to
completion within one `step()` via the original recursive evaluator,
since that nesting is bounded by call depth in a working program and
only a top-level `while` is unbounded by construction.  Forbin's frame
resumes `main`'s own statements and top-level `for`-loop rows the same
way; a nested call or a `for` loop inside a function body still runs
to completion within one `step()`.

Forbin's *expression-position* calls (`x = f(y)`) are the one remaining
gap: `_Machine` tracks one cursor for the single resumable frame there, and
a nested function call invoked from inside an expression still runs to
completion inside one `step()` through the original recursive
`_eval`/`_call`/`_run` -- its own frames are never part of `snapshot()`.
This path is deliberately left native-recursive: the language has no
realistic program shape that recurses that way (`return` exits a call
immediately, so there is no return-value-threading idiom to convert), so
the larger continuation-stack machinery needed to resume mid-expression is
not worth it for a case Forbin programs do not actually use.  It is still bounded only by Python's own default recursion limit, not
a documented cap.

**Suptiftam's call machinery, Forbin's statement-position calls, and all of
Lamfunc's calls were converted to an explicit frame stack**
(`_Machine.frames`, replacing native Python recursion for that path the
same way Forth/Grapheme already track a call stack of `_Frame`s) so that
recursion is uncapped -- a correct, terminating recursion of any depth now
completes, confirmed by a 300-level chained-function test for Suptiftam and
Forbin and a 2000-level one (past Python's own default 1000-frame limit)
for Lamfunc.  Lamfunc needed the fuller design: unlike Forbin and
Suptiftam, it has no statement/expression split whose "statement" side
always discards its value -- every prefix call is a value, and a realistic
recursive call (e.g. `loop`'s self-call inside `i x loop fb x 0`) sits in
*argument position* relative to `i`, not in some safely-discardable
position, since the lazy `i` builtin is the language's only conditional.
So every call, at any nesting depth, pushes a `_Frame` (`"scan"` -> resolve
the leading token; `"gather"` -> collect arguments up to arity, pushing a
child frame per non-literal argument; `"body"` -> run a callee's body or a
forced `i`-branch as a token sequence) rather than only the outermost or
only a discardable-statement subset.

This does *not* make infinite recursion cycle-detectable via
`run_until_halt_or_cycle`, though, for any of the three: unlike a backward
jump in a loop, a call that never returns pushes exactly one new frame per
`step()` and none is ever popped, so `snapshot()`'s frame tuple grows by
one element every step and two *whole-machine* snapshots can never compare
equal.  This is the same unbounded-growth class as a brainfuck `+[>+]`
tape loop (below) as far as Brent's-algorithm-over-`snapshot()` is
concerned -- that specific mechanism cannot catch it, regardless of how
much of the call stack `snapshot()` covers.

That is a statement about the *existing* detector, not a claim that
infinite recursion is undetectable in general.  A narrower, separate check
-- comparing a newly-pushed frame's own local state (code position,
bindings) against the frames already on the stack, rather than comparing
whole-machine snapshots across time -- would catch the common case of a
call whose local state repeats identically relative to an ancestor (e.g.
`f(x) { f(x) }`, an accidental unconditional or non-decrementing
self-call): frame N+1 is then provably about to replay exactly what frame
N already did.  It does not catch every infinite recursion (a call like
`f(x) { f(x - 1) }` that recurses forever without any local state ever
repeating exactly still slips through -- though *how* much slips through
is language-dependent: Forbin's only datatype is bits, so even a changing
argument has to come back around, and `f x { f !x; }` repeats its key
within two frames), and it does not fit the existing
`snapshot()`/Brent's-algorithm protocol -- it needs its own per-`step()`,
per-frame comparison against the live stack (O(depth) per push, not the
current mechanism's O(1)), so it is new machinery, not a tweak to the
existing one.

Built as `esolangs.vm.run_until_halt_or_ancestor`, keyed on a frame's
function, bindings and *input position*.  That last component is what
makes it sound rather than merely eager: a recursion whose base case
depends on a byte it has not read yet enters with identical bindings on
every lap, and a bindings-only key calls it a hang while it is one read
away from returning.  A machine opts in by exposing `frames` and a
`frame_entry_key`; Forbin does, and gained its first hang test as a
result -- it had none, every one of its hangs being in this class.
Suptiftam and Lamfunc recurse too and are the obvious follow-up.  The
wall-clock backstop stays for the recursion this cannot prove.
`scripts/verify_differential.py`'s NoComment Python side is likewise
bounded by state-cycle detection, keeping the alarm as backstop for its
unbounded-growth class (a loop that keeps pushing the stack never revisits
a state); the remaining differential Python sides on SIGALRM alone are
LaserFuck and Painfuck, whose headings/skips are random.

**The wall-clock backstop is broken under `pytest --cov`.**  Raising from
the SIGALRM handler while the coverage C tracer is active can deadlock the
tracer: the exception unwinds through the tracer's C code while it holds
its internal lock, so the *next* traced run spins forever instead of
finishing.  An interpreter that evaluates a `next(genexpr)` in its hot loop
makes it near-deterministic — the signal lands inside the suspended
generator frame and leaves the lock held — while a genexpr-free loop
reduces it to a rare race.  This is why state-cycle detection matters
beyond speed: it removes the deadlock hazard entirely for the machines it
covers.  The one alarm that stays by design is `test_api.py`'s `+[]` case:
it is a feature test of `esolangs.run`'s `timeout` parameter (the backstop
for unbounded-growth loops), not a hang-detection strategy, so it keeps
raising from the handler once per process.
