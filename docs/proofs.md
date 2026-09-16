# Boolean-generator coverage proofs

This ledger answers one question: for every exported Boolean generator and
every truth table of length `2**n`, does its construction produce a program
for every finite `n`?  “Total” here means mathematical coverage, not practical
availability.  Explicit limits on digits, instructions, lines, tape cells,
route width, work, or generation time are ignored: lifting such a guard leaves
the construction below it unchanged.  Invalid-table guards are outside the
domain.

This is not a correctness proof for every emitted program.  The execution
tests are that evidence.  Nor does a finite sweep prove the universal claim:
the exhaustive `n <= 3` and sampled `n <= 10` sweeps in
`tests/tools/test_boolean_contract.py` are counterexample searches for the
arguments below.

What is machine-checked lives in `tests/proofs/`.  `test_ledger.py` holds this
document to the registry and to itself, and `test_schemes.py` holds each row to
its scheme's measurable consequence; both are in the fast band and gate every
push.  `tests/proofs/deep/` holds the proofs themselves, at two depths.
`all_generators.py` runs a lemma battery against all sixty-five: every single
row of the table demonstrably participates in the emitted program, and the
construction completes at every arity of a ladder on both table shapes.  That
is the counting half of each scheme above, and it is what makes "finite object
covering every row" checkable per generator.  Four generators -- A Painter Ant,
ArrowQueue, Container and BIO -- additionally have a hand-derived proof of
their own specific argument, which no generic battery can reach.

Each proof declares the cost band it runs in, and
`python -m tests.proofs.deep <band>` selects on that: `verify` is the local
gate, `ci` adds the registry-wide battery, `all` is everything and is what
`just proofs` runs.  The bands are what the justfile, the workflow and
`scripts/verify.py` each invoke, so none of them carries a list of proofs;
`test_bands.py` holds every band to a cost budget and checks that no file under
`deep/` is missing one.

None of that bounds *size*: the schemes count nodes and entries, so a generator
can satisfy its row and still emit super-linear text.  `linearity.py` is the
separate, registry-wide scaling contract the roadmap asks for.  It measures
characters per table entry past each generator's last route change and holds
every generator to it except those the roadmap's scaling audit or this
document's `cap` and `exception` rows already exempt.  Read its verdicts in one
direction only: exceeding the bound is evidence, staying inside it is not, and
Factor -- proven super-linear at the language level in `limitations.md` and
measuring x2.11 -- is why.

## Proof schemes

**Decision tree.**  Recursively split the table on an input.  A leaf emits its
table bit; an internal node reads or tests that input and selects the matching
child.  The recursion measure is the number of inputs left, so it terminates
after at most `2**(n+1)-1` nodes.  Folding equal children, permuting inputs, or
choosing a greedy order changes size, not coverage.  This proves every finite
table for the generators marked `tree`.

**Minterms.**  For each row whose output has the chosen polarity, emit the
conjunction of that row's literals, then combine the terms by the language's
Boolean sum/selection operation.  There are at most `2**n` terms of length
`n`; complements handle the opposite polarity.  This proves every finite
table for the generators marked `minterms`.

**Finite lookup.**  Encode the `n` input bits as their row number and emit the
finite table, or an equivalent chunked/DAG lookup.  Index formation takes `n`
steps and the stored lookup has at most `2**n` entries.  This proves every
finite table when the language's addresses or program integers are unbounded;
where this repository imposes a finite ceiling, the row is marked `cap`.

**Parameterized tree.**  A no-input language receives each bit through an
equal-width `{Xi}` replacement.  Embedding the placeholders at the internal
nodes of a full decision tree gives the same induction as `tree`; equal width
prevents program length from becoming an extra input.  A generator may use a
smaller arithmetic construction, but the full tree is its coverage witness.

**Parameterized lookup.**  A no-input language embeds each bit once through
the same equal-width `{Xi}` replacement, and the embedded bits address a finite
stored table instead of routing a tree.  Index formation is one embedding per
input and the table has `2**n` entries, so the `finite lookup` argument applies
unchanged.

**Parameterized construction.**  A language-specific arithmetic or geometric
construction that embeds each input once and is proved total by its own row's
qualification rather than by a scheme above.

**Linear lookup.**  A finite lookup whose emitted program is also linear in the
table length.  Coverage follows from `finite lookup`; the label only records
the size result.

**Reduction.**  `essential_inputs` projects away ignored inputs.  Solving the
smaller table and restoring the omitted, equal-width placeholders preserves
every row.  This is only an optimization unless the cited inner construction
is itself total.

**Size dispatch.**  Most lookup rows ship two routes: a folded decision tree
for tables through a fixed crossover — `n <= 4`, or `n <= 6` for Container —
and the lookup above it.  Each route is total on its own domain and the lookup
carries the universal claim, so the tree below the crossover is a size
optimization rather than part of the proof.  A width-constrained build may take
the tree at any arity.  Alight, COD, Crement, Nopstacle and
SLOW ACV MAMMALIAN keep no tree route at all: Alight indexes a string literal,
COD emits four rows, the two prototypes embed the table verbatim beside their
input slots, and SLOW ACV MAMMALIAN's read chain emits one fixed-width leaf
slot per row whatever the table says.  Container's sub-crossover route is a
tree but a deliberately unfolded one, so it does not shrink on a degenerate
table.

## Generator ledger

The names are the 65 callable entries indexed by `BY_BOOLEAN`.  Rows sharing a
proof scheme share the proof above; the qualification column records the
language-specific final step or an exception.  `cap` means theoretically total
after ignoring the performance/resource ceiling as specified above.

| Generator | Proof | Qualification |
| --- | --- | --- |
| A Painter Ant | parameterized lookup | the embedded bits advance the ant along a self-painting corridor by their own weights, leaving it over the indexed answer cell |
| AddSubJump | finite lookup | packed `n`-bit cells selected by a self-modified operand |
| Algebraic Programming Language | minterms | base-26 names are unbounded |
| Alight | finite lookup | inputs folded into a row index by Horner's rule; the table is a string literal read with `at`, so the program has no branches |
| ArrowQueue | parameterized lookup | marker counts select one of `2**n` constant-size cascade stages |
| B-tapemark | tree | reflected finite grid; indexed table spans preserve the same leaves without recursive copies |
| Back | parameterized tree | — |
| BF-PDA | parameterized tree | — |
| BFStack | minterms | — |
| BIO | finite lookup | nested loops telescope from `table[0]` to `table[index]` |
| bit~ | tree | — |
| Bitdeque | parameterized lookup | head/tail discards leave the indexed entry in the deque |
| brainfuck | tree | `decision_tree_program` |
| BrainIf | finite lookup | a spatial table is addressed by the read row index |
| Circlefuck | tree | its local shape guard is equivalent to the shared guard |
| Circuit Diagram | tree | finite planar routing |
| Clockwise | tree | finite grid layout |
| COD | parameterized lookup | binary-weight water runs stop the path over one of `2**n` baked-in answer cells; this row has no tree route |
| Collatz Multiverse | tree | finite cell placement |
| Container | finite lookup | the reversed table is one decimal literal divided by ten in a fixed two-bank network |
| Crement | finite lookup | prototype instantiation |
| CV(N)(C) | tree | the halting goto squares once more whenever the program is not shorter than its reach, so every finite tree halts |
| Decleq | tree | — |
| Dig | tree | finite cell placement |
| Dimensional | tree | `decision_tree_program` with dimensional moves |
| EGL | tree | — |
| Eval | linear lookup | fixed reversed stack order selects the indexed row |
| Factor | tree | Brainfuck tree followed by a total prime encoding: Dirichlet supplies the next prime in each residue class mod 11, and the integer is arbitrary precision on both sides |
| Fargo | tree | finite folded layout |
| Flowchart | finite lookup | a five-row deque preloads `2**n` answers and discards opposite halves |
| Forbin | tree | — |
| Forþ | tree | — |
| Grapheme | tree | arbitrary integer variable keys remove the old 24 one-letter-key ceiling |
| Home Row | parameterized tree | — |
| Inject | finite lookup | one table block halved by `O(n)` conditional substitutions |
| Interprogck8 | tree | routed by a shared `DownAccLines` corridor: a read's 48/49 selects dismount against flight by landing parity, stops are phase-separated by depth, and assembly is one pass with no repair loop |
| Jaune | finite lookup | a spatial table reached with two labels |
| LaserFuck | finite lookup | weighted arms select one of `2**n` prewritten cells, cleaned in one sweep |
| Minifuck | parameterized construction | `_mux` is the total fallback; its six failure sites close uniformly in `n` |
| Minsky Swap | parameterized tree | — |
| Modulous | tree | — |
| NoComment | finite lookup | from 4 inputs the index is a run of byte-sized skips on the stack and the rows are code: a chain of uniform groups lands on the row, and the rows after it telescope to `table[index]` on six tape cells |
| Nopstacle | finite lookup | prototype instantiation |
| 123 | parameterized construction | table-independent separation plus verdict; failed tight geometry falls back to doubling geometry |
| Packlang | tree | — |
| Painfuck | tree | Brainfuck tree transliteration |
| %^2^-1 | exception | parameterized planners cover all tables through four inputs and tested tables above that, but no all-arity proof is known |
| Polynomial | tree, cap | each finite instruction list has a finite prime-product encoding |
| Qoibl | tree | — |
| RAM0 | parameterized lookup | a straight-line RAM initializer plus a unary-weight lookup |
| ROTfuck | tree | movement search stops after at most eight offsets |
| S*bleq | finite lookup | packed chunks decoded after the hoisted read block |
| 6-5 | finite lookup | past 35 inputs the positional walk loops on sixteen labels: each bit advances the pointer to the first row whose 2-adic valuation mark reads zero, and one pass per bit shifts the marks |
| SLOW ACV MAMMALIAN | linear lookup | a read chain banks each bit as a 256-multiple weight on array 16; one trampoline lands the indexed 256-token leaf |
| Sophie | tree | — |
| Streetcode | tree | — |
| Suffolk | tree | — |
| Super SNUSP | tree | each folding pass removes at least one pending unit |
| Taglate | tree | — |
| 3D Brainfuck | tree | Brainfuck tree transliteration |
| 3x | tree | — |
| Unsquare | tree | stack arrangement affects size only |
| Vandevelo | minterms | constant-one subtrees drop their suffix literals |
| WII2D | parameterized construction, cap | Horner's chain is total; the decode folds the extremal same-colour pair, whose midpoint is unique, so every fold is legal |
| ZTOALC L | finite lookup, cap | `2**k` supplies `k` ordered trajectory slots for every finite `k` |

## Exceptions and walls

The one remaining `exception` row is a proof gap, not permission to call the
language incapable.

- `%^2^-1` can refuse when none of its cascade, affine, ladder, band, or fold
  planners succeeds.

### Attempts on the open cases

**Interprogck8** left this section Sep 2026: the repair loop whose totality
was the gap no longer exists.  The corridor assembly places each gadget once
on computed coordinates, a placement is a bounded congruence scan (a free
line on one class recurs within its modulus times the longest occupied run,
and every occupied run is O(1)), and rungs are shared rather than embedded --
no simultaneous-placement lemma is needed because nothing is ever moved.
Stride classes `30 + 2k` for `k` up to 113 hand 14 residues each to
successive depth bands, 1596 read depths, past any representable table.

**`%^2^-1`.**  The proved two-read wall does not survive parameterization, and
the 3003 reset does not make the machine finite-state: negative accumulators
are unbounded and repeated `m` stores arbitrarily many bits without resetting.
That defeats the obvious counting proof of a cap.  A totality attempt can
encode the input index by doubling a negative accumulator and applying one of
two fixed offsets per placeholder.  It then needs one uniform tail mapping the
`2**n` resulting integers to the table's two output bytes.

Two things that tail cannot use.  There is no squaring: `m` doubles the
accumulator, and the “squaring” in the language's own description is of the
represented value `10**x`, so absent the reset the reachable maps are exactly
`x -> ±2**j x + c` — an affine monoid, with the reset the only non-affine
primitive and hence the only way to merge two values.  And `t` cannot
separate: it rewinds to position 0 with the state `(0, acc)`, deterministic in
`acc`, so a run either diverges or leaves that `t` with `acc == 0`, after
which every surviving input agrees and all later behaviour is
input-independent.  The only input-dependent signal is how many times the
program repeated, i.e. the output *length*, which a one-byte answer cannot
carry.  So a separating program may be taken to be `t`-free, which is what
every shipped one already is.

That leaves a purely order-theoretic question, and it turns on a move that is
not the obvious one.  The reset fires before *every* command, hence between a
scaling and an offset: `m**j` then an offset spells `x -> R(2**j x) + b`, not
`R(2**j x + b)`, so a block driven past the limit lands on `b` — freely
chosen — rather than on 0.  Spelling a single `R(a x + b)` needs either
`a | b`, offset first, or `b > 0` with no premature clamp, scale first, and
that divisibility binds: over every state reached from a row-index start at
three inputs, the window for swapping the top two values is non-empty 254
times out of 254 and spellable 0 times out of 254, always because `a` does not
divide `b`.  The one move such a state does admit is the rotation parking the
survivors against 3003 and leaving the ex-top at 0, which opens one interior
slot per turn.

So the honest primitive is a *cut*: `sub(c)`, then `m**j`, then an offset,
merging everything above `c + 3003/2**j` onto that offset.  Since `c` may sit
just under the top survivor the power-of-two condition is trivially met, and
the ratio question dissolves into a span budget — each cut scales the
surviving span by about `3003/gap`, and the span may only grow from 15 to
6006.  One barrier is proved: a value below `-3003` can only decrease or be
destroyed, every increasing route passing through a `p` that overflows, so
there is no mirrored bottom cut and the last cut must land in window, `e`
needing a final gap congruent to ±1 modulo 256 that a scaled gap never is.
Cuts do separate the alternating four-row table that block collapses and end
swaps provably cannot, and reach `01101001` in twelve, while the eight- and
sixteen-row alternating tables were not found by a beam search — a search
failure, not an impossibility.  Whether the span budget always suffices is the
finite-map lemma, and it is the whole open case.

### Resource-ceiling audit

The remaining `cap` rows do have a uniform lift argument.

- Polynomial's `k == n` candidate is the finite decision tree.  Each of its
  finitely many instructions receives a distinct prime root, and removing the
  interpreter-cost screen does not change that encoding.
- ZTOALC L's command list is finite.  For any list of `k` commands, choose
  start value `2**k`: its Collatz trajectory is
  `2**k, 2**(k-1), ..., 2, 1`, giving exactly `k` distinct executable lines
  in visit order before line 1 halts.  The emitted source may have `2**k`
  lines, but existence is unconditional and uses no Collatz conjecture.  The
  committed anchors merely find much smaller programs under `_MAX_LINES`.
- WII2D's chain is total already (Horner's children `2v` and `2v+1` differ in
  parity, so that junction is legal at every level).  The decode is total too,
  and the argument is a choice of fold rather than a wider search.  Squaring
  is the only merging op, so after a shift by `c` it identifies `x` and `y`
  exactly when `x + y = -2c`: one fold merges precisely the pairs sharing a
  midpoint, and it is legal exactly when every pair with that midpoint is
  monochromatic.  The two largest values have strictly the largest sum, since
  any other pair swaps one of them for something smaller, so *no* other pair
  shares their midpoint and folding them is legal whatever the rest of the
  colouring does.  One `*` first makes every value even, hence every midpoint
  an integer.  Some colour class has two members whenever three values are
  live, and when neither extremal pair is monochromatic, repeated squaring on
  a positive set makes all pair sums distinct — for distinct positive integers
  `a**M + b**M = c**M + d**M` forces `{a,b} = {c,d}` once `M` is large enough
  — after which every same-colour pair is foldable.  The live count therefore
  falls to one per colour, and `_wii2d_threshold` reads out any two distinct
  values.  What the shipped decode does instead is rank folds by magnitude and
  take the cheapest, which is what ratchets; the extremal fold costs unary
  offsets and always works.  Every WII2D magnitude guard is repository policy,
  the interpreter bounding only the *printed* value, which is 48 or 49.

Grapheme's lift is already applied, so it is a `tree` row rather than a
`cap` row.  Its folded tree needs one variable per essential input, but
variable names are arbitrary integers, not just the 24 collision-free
one-letter literals the old emitter used.  `FAF` pushes 10; repeating it and
combining the copies with `A` constructs `10(i+1)` for every finite `i`.
Reserving a disjoint key for the normalization constant therefore extends the
same finite tree proof to every arity.  Decimal digit 6 is split into `1 + 5`,
since `F` delimits integer mode and cannot occur inside its literal.

6-5 left this section when its walk stopped spending a label per input.
NoComment left when its rows stopped living on the tape: the index is pushed
as byte-sized stage amounts, a chain of uniform six-command groups pops and
skips its way to the row's group, and every group after it adds the
difference between its row and the next, so the landing cell telescopes to
`table[index]` on six cells at any arity.
`8n` names the n-th `4` of the program and the operand characters stop at
35, so a walk that branches every bit with its own jump ends at 35 inputs;
the looped walk (`_six_five_looped`) marks each row with its 2-adic
valuation in sixes, and a bit's advance is a loop to the first row past
the pointer whose mark reads zero — the first row whose valuation is
exactly `n-1-i`, which is the row `2**(n-1-i)` ahead, because the pointer
stands on an even multiple of that stride.  The marks are kept at
`6 * (v - (n-1-i))` by `n-1` decrement passes before the first bit and one
increment pass after each, so every loop tests a sentinel or a zero and
the label bill is the loop count, sixteen.  The marks sum to `2**n - n - 1`,
so the program is linear; every row of every table at seven inputs and
under has been executed, and the dispatch reaches the loop only past 35.
Factor left when its digit budget was retired: the budget (4300, then
16000, then 500000 digits) was a size policy pinned to the arity the
suite swept, never a ceiling of the language's -- the generator renders
the integer and the interpreter parses it with CPython's conversion
guard lifted on both sides -- so the lift argument above *is* the
construction.  Parity at thirteen inputs is 966568 digits, built in
three seconds with the prime powers multiplied as a balanced tree, and
the interpreter decodes it to the tree the generator encoded.
WII2D reads the other way: the shipped decode keeps
ranking folds by magnitude, so it still refuses about four in ten dense
tables at the widest admitted domain, and reaching the extremal-fold
construction means choosing a different fold rather than relaxing a constant.
Prompt refusal is the better behaviour there — the extremal fold spells its
centres in unary, and a refused table costs seconds where the total
construction costs minutes and a megabyte.

There is one proved language wall, but it does not classify the shipped
generator.  In the ordinary reading model, every `%^2^-1` program satisfying
the two-input Boolean contract ignores one input: `n` overwrites the sole
accumulator, and the only branch, `t`, rewinds to the program start, so a clean
run cannot preserve the first bit through the second read.  XOR and AND are
therefore impossible at every program length.  The exported generator is
parameterized and contains no `n`; substituting `{Xi}` changes the program
before execution and voids the theorem's hypothesis.

Accordingly, this ledger records 64 theoretical totality arguments and one
open exception.  It records no structural impossibility for an exported
generator's actual parameterized contract.  Turning any exception into
“incapable” requires an unbounded-program proof; a failed search or a live cap
is not one.
