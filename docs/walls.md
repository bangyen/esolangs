
# Generator and transpiler walls

The full wall arguments behind the blocker tables in
[`docs/limitations.md`](limitations.md) — the negative result and the
structural reason it cannot be lifted.  Completed constructions (the
working generators, and how they work) live in the commit history, not
here.

## 6-5 (constant program size is impossible)

A generator that must work for any table has to embed the table, and the
single-integer representation 6-5 requires (the pointer cannot net-advance,
so there is no computed array indexing) costs O(`2**(2**n)`) characters for
dense tables.  A ~2 MB setup guard rejects the `n > 5` and large-`T` region
(AND-n is the pathological case), and runtime is O(x*T) — minutes at the
size guard.  The shipped decision tree stays primary (total through
`n <= 5`); the arithmetic kernel is the fallback for small-`T` tables past
that.

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
*nearest* preceding/following `3` (not bracket-matched), so the only
constructible pattern is "repeat the region before the `3` while TRUE" — no
`3`-based branch exists (a random search finds no NOT even at n == 1), and
the single data byte makes multi-bit state impossible (every read overwrites
it).  The four one-input programs were too trivial to keep, so the boolean
generator was removed.

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

## SLOW ACV MAMMALIAN (general n-bit open)

The n-bit case is blocked by three mutually conflicting constraints:

- `ACCEPT` unconditionally appends the normalized bit to `lst[0]`, and
  consuming that bit needs `ptr == 0`, but routing `SPRINT`s move the
  pointer to a node — so the bit cannot be both read and routed without a
  way to return the pointer to 0.
- The read's clean normalization needs `lst[0][0] == 48` (the `^ 48` base),
  and `SEED` skips empty arrays, so the only constant source is `K SEEDs
  CONSUME` starting from `lst[0] = [0]` — which empties the array, so every
  later constant **accumulates** on the previous one (`42 + 5 = 47`, never a
  clean `5`).  The `[48, C, m]` triple a branch needs therefore cannot be
  assembled in one array.
- `DIGEST` normalizes by XORing the *sum* of `lst[ptr]`, so a bit buried
  among previous bits is only recoverable as part of a sum, and `48 ^ (48 +
  m1 + m2)` is not `m1 ^ m2` when both bits are set.

Re-verified against the interpreter: a search over the branch-free tails
after the `b1`-normalize prefix reaches only the 0-preserving two-input
tables, matching the structural argument.  (Unlike Minifuck, this wall
holds.)

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

## Home Row (j-guarded-move boolean generator, n <= 2)

`l` loops pair strictly by order, so loops cannot nest and a bf-style
decision tree is inexpressible.  The shipped generator routes with `j`
(guarded moves) instead of loops, which works through `n == 2`.  `n >= 3`
raises: an exhaustive search over `j`-guarded sequences shows no routing
separates `2**n` combinations onto distinct cells of the fixed 5x5 torus
past `n == 2` (the search caps at 6 of 8 combinations).

## Assessed boolean candidates that fell through

- **%^2^-1**: its only control flow is `t` — rewind to the program start
  when the accumulator is nonzero — with the accumulator preserved across
  the rewind.  A program is therefore a whole-program `while` loop, and each
  `n` in the body consumes one input line, so a `t` loop iterates over the
  input bits.  It cannot count them: there is no increment-by-1 for an
  arbitrary value, and a counter in the rewind path grows without bound (the
  `acc > 3003` reset only fires on huge magnitudes), so the loop stops only
  when a body pass ends with `acc == 0` — a uniform predicate that cannot
  tell pass 1 from pass n.  The all-ones row of any truth table therefore
  either stops the loop early or rewinds past the input.  Exhaustive search:
  of the four one-input functions only identity and the two constants are
  expressible; NOT and every two-input table fail even at length 8.
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
  n-embedding chain** (:func:`esolangs.tools.boolean.parameterized.wii2d`):
  the branches are routing, not value tests, and the *accumulator arithmetic*
  decodes the input.  Each input is embedded exactly once as a junction whose
  two branches are op strings that transform the accumulator before re-merging
  ahead of the next junction; the final accumulator is the table entry.  The
  ops are not monotone (`s` sends -1 to 1), so the decoding works for any
  table at small arity (every table through four inputs is verified against
  the interpreter — exhaustively through three, sampled dense at four; two
  inputs use a closed form — bit 0 packed as -1/0, each column decoded by a
  single op).  The search tries op strings of length 2
  through 6 with a growing budget and generally fails past `n == 5` for dense
  non-symmetric tables.  Symmetric tables (AND/OR/XOR/majority/threshold-k of
  any arity) get their own closed forms first: parity/XNOR is exact and O(1)
  at any `n` (pack bit 0, then fold every later bit with `-s`, which flips
  0/1 since `(v-1)**2` sends 0->1 and 1->0), and other symmetric tables
  reduce to a popcount-accumulator prefix plus a decode search over `n`
  points instead of the full `2**n` rows — see `_wii2d_search`'s docstring
  for the counting-bound proof that the general (non-symmetric) search must
  eventually fail at high arity regardless of tuning, and why parity's exact
  case is a speed win rather than a reachability one.  When the search
  cannot fit a table in its budget the generator raises :class:`ValueError`
  — a genuine cap, not a representation limit: the counting bound shows no
  chain with bounded op strings can represent every table once ``n`` is
  large, so large dense non-symmetric tables (past ``n == 5``) are out of
  reach, and there is no universal fallback (a tree would need each input
  re-embedded at every node, which WII2D has no way to store).

  **A search-free chain (no BFS/DFS at all, just a formula) was assessed and
  found not to generalize.**  The idea: pack the first `n - 1` bits into a
  single non-negative integer with a fixed, table-independent prefix
  (`("*", "*+")` per junction — double on a 0 bit, double-and-increment on a
  1 bit), leaving only the last junction's two op-strings to depend on the
  table.  At `n == 3` this is total (a decode search up to length 7 covers
  all 256 tables, including non-monotone ones like XOR3, since the *decode
  string* can dip negative even though the packing prefix stays
  non-negative).  It collapses fast past that: the decode step must hit one
  specific function out of `2**(2**(n-1))` possible 0/1-valued functions on
  the `2**(n-1)`-point packed domain, and the count of *usable* (pure
  0/1-output) op-strings up to length 6 barely grows with length (8, 15, 24
  at lengths 4, 5, 6) while the target count doubles-of-doubles — coverage
  falls from 94% at `n == 3` to 9% at `n == 4` to 0.04% at `n == 5`.  Moving
  the hard part into a single final decode junction does not avoid the
  counting-bound wall; it relocates a smaller copy of the same pigeonhole
  problem (arbitrary lookup table, short formula) to that junction.

## 2dFish (the WII2D-style merging chain is affine-only; a decision tree is the universal construction)

2dFish can host a WII2D-style parameterized generator: its direction cells
(`/` east, `v` south, `^` north) steer a pointer carrying a single
accumulator, and there is no runtime conditional nor a way to combine two
`%` reads (each overwrites the accumulator).  The WII2D merging-chain
technique transfers almost verbatim — junction cells filled `/` (bit 0,
continue east) or `v` (bit 1, detour onto a lower row and remerge ahead),
branch op strings from the fish alphabet `i d s` (increment, decrement,
square) transforming the accumulator, and the BFS behavior-dedup /
backward requirement-set search
(:func:`esolangs.tools.boolean.parameterized`'s `_wii2d_sequences` /
`_wii2d_domain` / `_wii2d_search_start`) is op-agnostic — but the chain is
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

## A Painter Ant boolean generator (general; any n)

A Painter Ant has no I/O, so its boolean generator (in
:mod:`esolangs.tools.boolean.parameterized.a_painter_ant`) uses the parameterized
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

A brainfuck prototype was built and verified: read+normalize each digit
(ASCII minus 48), multiply via a nested loop, and print the product with the
itchyny 8-bit decimal printer.  **n = 1 works exhaustively (all 100
single-digit pairs 0-9 × 0-9).**

For n > 1 the right construction is grade-school long multiplication:
allocate 2n cells for the 2n operand digits (each 0-9, fitting a byte) and
carry over between result cells, so no single cell ever holds the full
product.  This avoids the single-cell overflow that blocks accumulating the
product in one cell.  But the per-digit *carry* needs a "while >= 10"
operation, and with the interpreter's documented 8-bit wrapping cells (mod
256) the standard divmod/carry algorithms assume non-wrapping cells and do
not transfer directly — the itchyny decimal printer embeds a working divmod,
but it is tied to the printer's cell layout, not reusable as a standalone
carry.  So n = 1 is proven; n > 1 needs a wrapping-safe carry, which is a
genuine brainfuck-algorithms construction rather than a quick extension.

**Jaune realizes the capability:** its cells do not wrap (the author's
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

`tests/test_interpreters_robustness.py` decides the empty-program invariant
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

Lamfunc and Forbin's cycle detection only sees the *outermost* call: each
`_Machine` tracks one cursor (Lamfunc's `ind`, Forbin's `(pos, for_ind)`)
for the single top-level frame, and a nested function call still runs to
completion inside one `step()` through the original recursive
`_eval`/`_call`/`_run` -- its own frames are never part of `snapshot()`.
That bound is not free -- `_MAX_DEPTH` (Forbin) or Python's own
`RecursionError` (Lamfunc) is an invented cap with no basis in either
wiki, so it also wrongly halts a *terminating* program whose correct
recursion happens to run deeper than the cap; see `docs/limitations.md`'s
interpreter-conventions section.

**Suptiftam's call machinery was converted to an explicit frame stack**
(`_Machine.frames: list[_CallFrame]`, replacing native Python recursion for
calls the same way Forth/Grapheme already track a call stack of `_Frame`s)
so its recursion is uncapped -- a correct, terminating recursion of any
depth now completes.  This does *not* make infinite recursion
cycle-detectable, though: unlike a backward jump in a loop, a call that
never returns pushes exactly one new `_CallFrame` per `step()` and none is
ever popped, so `snapshot()`'s frame tuple grows by one element every
step and two snapshots can never compare equal.  This is the same
unbounded-growth class as a brainfuck `+[>+]` tape loop (below) --
proven, not caught, is out of cycle detection's reach by construction,
regardless of how much of the call stack `snapshot()` covers.  A future
conversion of Lamfunc/Forbin to the same explicit-stack pattern would
still be worth doing to remove their invented caps and fix the same
wrongly-halted-deep-program bug, but should not be sold as adding cycle
coverage for infinite recursion -- there is none to add.
`scripts/verify_differential.py`'s 2dFish and NoComment Python sides are
likewise bounded by state-cycle detection, with NoComment keeping the
alarm as backstop for its unbounded-growth class (a loop that keeps
pushing the stack never revisits a state); the remaining differential
Python sides on SIGALRM alone are LaserFuck and Painfuck, whose
headings/skips are random.

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
