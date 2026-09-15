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
| CV(N)(C) | tree, cap | the halting-goto reach is a renderer ceiling |
| Decleq | tree | — |
| Dig | tree | finite cell placement |
| Dimensional | tree | `decision_tree_program` with dimensional moves |
| EGL | tree | — |
| Eval | linear lookup | fixed reversed stack order selects the indexed row |
| Factor | tree, cap | Brainfuck tree followed by a total prime encoding; Dirichlet supplies the next prime in each residue class mod 11 |
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
| NoComment | finite lookup, cap | fixed interpreter tape is the ceiling |
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
| 6-5 | finite lookup, cap | constant-label arithmetic evaluates `(T >> index) & 1` |
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
| WII2D | exception | Horner makes the input chain total, but the deterministic final fold is not proved to decode every finite domain |
| ZTOALC L | finite lookup, cap | `2**k` supplies `k` ordered trajectory slots for every finite `k` |

## Exceptions and walls

The two `exception` rows are proof gaps, not permission to call the languages
incapable.

- `%^2^-1` can refuse when none of its cascade, affine, ladder, band, or fold
  planners succeeds.
- WII2D can refuse when its deterministic decode hits the magnitude/width
  guards or has no legal fold.  The exactly-once embedding convention has a
  measured wall; re-embedding inputs at tree nodes escapes it, so it is not a
  language wall.

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
`2**n` resulting integers to the table's two output bytes using only unary
affine operations, squaring, the asymmetric reset, and rewind-to-zero.  The
existing folds solve many such finite maps, but no argument shows that every
two-colouring admits the required collision sequence.  That missing finite-map
lemma is the whole open case.

**WII2D.**  There is no language cap: repeating placeholders at the nodes of a
plain grid decision tree computes every finite table.  It is disallowed only
by the repository's exactly-once parameterized contract.  Under that contract,
an absolute-heading fill makes both arms rejoin at the same position and
heading; only the unbounded accumulator can distinguish their histories.  Its
unboundedness and `s` squaring defeat a finite-state counting wall, while the
measured doubling traps refute only the shipped greedy fold.  The matching
totality attempt uses Horner junctions to assign every input row a distinct
integer, then seeks a unary op composition taking those integers to their
table bits.  Totality reduces to the same unproved statement the decoder needs:
every finite two-coloured integer set admits a sequence of legal square/shift
folds with no cross-colour collision.  Search success on bounded domains is
not that proof.

### Resource-ceiling audit

The remaining `cap` rows do have a uniform lift argument.

- CV(N)(C)'s tree is finite.  Its halt gadget squares a positive accumulator
  before jumping by it; adding squarings makes the reach grow by repeated
  squaring and eventually exceeds any fixed finite tree, including the extra
  gadget characters.
- Factor first builds the total Brainfuck tree.  Its finite encoding loop
  assigns each command run the next prime in one of the nonzero residue
  classes 1 through 8 modulo 11.  Dirichlet guarantees such a prime above
  every bound, and an arbitrary-precision integer holds their finite product.
- NoComment's wide construction needs a finite number of cells for every
  finite table and already accepts the tape size as a parameter.  The language
  specifies static memory but no fixed size; choosing that finite size removes
  the interpreter's default ceiling.
- Polynomial's `k == n` candidate is the finite decision tree.  Each of its
  finitely many instructions receives a distinct prime root, and removing the
  interpreter-cost screen does not change that encoding.
- 6-5 has a cap-free arithmetic construction using a constant number of its 35
  labels.  Read the bits into `x`, encode the finite table as
  `T = sum(table[i] * 2**i)`, halve `T` exactly `x` times, and print its parity:
  `(T >> x) & 1 = table[x]`.  The cell operations construct every finite `T`
  with a finite run of `+5`/`+6`; the retired implementation refused only
  when that run exceeded about 2 MB.  Its source is recoverable immediately
  before commit `87478ea8`, which removed it because no table inside the
  practical size bound escaped the newer tree/walk paths.  Thus 35 limits the
  shipped positional walk, not theoretical 6-5 coverage.
- ZTOALC L's command list is finite.  For any list of `k` commands, choose
  start value `2**k`: its Collatz trajectory is
  `2**k, 2**(k-1), ..., 2, 1`, giving exactly `k` distinct executable lines
  in visit order before line 1 halts.  The emitted source may have `2**k`
  lines, but existence is unconditional and uses no Collatz conjecture.  The
  committed anchors merely find much smaller programs under `_MAX_LINES`.

Grapheme's lift is already applied, so it is a `tree` row rather than a
`cap` row.  Its folded tree needs one variable per essential input, but
variable names are arbitrary integers, not just the 24 collision-free
one-letter literals the old emitter used.  `FAF` pushes 10; repeating it and
combining the copies with `A` constructs `10(i+1)` for every finite `i`.
Reserving a disjoint key for the normalization constant therefore extends the
same finite tree proof to every arity.  Decimal digit 6 is split into `1 + 5`,
since `F` delimits integer mode and cannot occur inside its literal.

The shipped 6-5 function still refuses past its optimized construction.  Its
classification is theoretical in this section's stated sense: removing the
resource policy requires restoring a known construction, not merely changing
one numeric constant.

There is one proved language wall, but it does not classify the shipped
generator.  In the ordinary reading model, every `%^2^-1` program satisfying
the two-input Boolean contract ignores one input: `n` overwrites the sole
accumulator, and the only branch, `t`, rewinds to the program start, so a clean
run cannot preserve the first bit through the second read.  XOR and AND are
therefore impossible at every program length.  The exported generator is
parameterized and contains no `n`; substituting `{Xi}` changes the program
before execution and voids the theorem's hypothesis.

Accordingly, this ledger records 63 theoretical totality arguments and two
open exceptions.  It records no structural impossibility for an exported
generator's actual parameterized contract.  Turning any exception into
“incapable” requires an unbounded-program proof; a failed search or a live cap
is not one.
