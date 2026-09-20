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
`all_generators.py` runs a lemma battery against all sixty: every single
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
Factor -- proven super-linear at the language level in [factor](factor.md) and
measuring x2.11 -- is why.  Polynomial's `Omega(T**2 / log T)` is proved for
distinct real instruction roots only; repeated roots are legal and the missing
multiplicity lemma is named in [polynomial](polynomial.md), so its audit row is
`Open`, not a language lower bound.

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

A generator carries a ceiling exactly when some table inside the contract's
arity range cannot finish under the suite's budget on an audited axis --
output size, build time or execution time -- by the shipped construction,
and a uniform lift (below) proves the program exists without it.  The
ceiling is one named constant; reaching it refuses, never truncates.  A
construction that is polynomial in the table and inside the budget gets no
ceiling: super-linear growth there is an open roadmap cell for the linearity
contract to hold, and a ceiling would hide it.  A refusal with no lift
argument is `exception`, not `cap`.  Audited across every one:
every other arity threshold is a route switch to a total construction or an
unreachable invariant guard.

**Parameterized tree.**  A no-input language receives each bit through an
equal-width replacement of its run.  Embedding the runs at the internal
nodes of a full decision tree gives the same induction as `tree`; equal width
prevents program length from becoming an extra input.  A generator may use a
smaller arithmetic construction, but the full tree is its coverage witness.

**Parameterized lookup.**  A no-input language embeds each bit once through
the same equal-width replacement, and the embedded bits address a finite
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
the tree at any arity.  A Painter Ant, Alight, BIO, Minsky Swap and
SLOW ACV MAMMALIAN keep no tree route at all: A Painter Ant's answer strip
is smaller than a tree at every arity, Alight indexes a string literal,
BIO's telescope is one nested level per row whatever the table says (a
degenerate table only spares it the flat edges' adjustments, under the fold
threshold once the doubling between the input runs is in the text), Minsky
Swap's `~` cascade routes the index to one of two shared leaves with a
one-digit target per row, and SLOW ACV MAMMALIAN's read chain emits one
fixed-width leaf slot per row whatever the table says.  Container's sub-crossover route is a
tree but a deliberately unfolded one, so it does not shrink on a degenerate
table.

## Generator ledger

The names are the callable entries indexed by `BY_BOOLEAN`.  Rows sharing a
proof scheme share the proof above; the qualification column records the
language-specific final step or an exception.  `cap` means theoretically total
after ignoring the performance/resource ceiling as specified above.

The Scaling column is the worst-case cost of the construction in `T = 2**n`,
read from the code rather than measured (the size contract in
`tests/proofs/deep/linearity.py` cannot see a `log T` in twelve doublings).
Each cell is one of: `linear: <argument>` (size and time O(T) for every
table; the clause names the argument in twelve words or fewer); `linear,
time n log: <term>` (size O(T), one stated `log T` factor in generation
time); `measured: <what is unbounded>` (no invariant bounds it); `open:
<term>` (a super-linear term with its bound -- exactly the rows open on size
or time in the roadmap's audit); `lower bound: <bound>` (the language forces
it).  Where a generator dispatches on table size, the cell describes the
wide route.  `tests/proofs/test_ledger.py` checks the grammar and
`tests/proofs/test_linearity.py` checks the column against the audit.

| Generator | Proof | Qualification | Scaling |
| --- | --- | --- | --- |
| A Painter Ant | parameterized lookup | each embedded bit keeps the ant on a self-painting corridor or lifts it off, and the template walk after it advances the ant by that bit's weight, leaving it over the indexed answer cell | linear: table walk; corridor weights sum to T |
| AddSubJump | finite lookup | packed `n`-bit cells selected by a self-modified operand | linear: T/n packed cells of O(n) digits, O(n) decoder |
| Algebraic Programming Language | minterms | base-26 names are unbounded | linear, time n log: greedy order scoring, capped at n <= 10 |
| Alight | finite lookup | inputs folded into a row index by Horner's rule; the table is a string literal read with `at`, so the program has no branches | linear: one T-character literal, O(n) Horner reads |
| ArrowQueue | parameterized lookup | one stage per input doubles the queued markers and adds the bit (Horner), and the count selects one of `2**n` constant-size cascade stages | linear: 6n + 3T rows, three per entry |
| B-tapemark | tree | reflected finite grid; indexed table spans preserve the same leaves without recursive copies | linear: T - 1 fixed-footprint nodes, rows rendered from their cells |
| Back | parameterized tree | — | linear: leaf moves sum geometrically, sparse row render |
| BF-PDA | parameterized tree | — | linear: span walk, leaf drains sum geometrically |
| BFStack | minterms | — | linear: zero-row walk telescopes to T |
| BIO | finite lookup | nested loops telescope from `table[0]` to `table[index]` | linear: T - 1 loop pieces joined once |
| bit~ | tree | — | linear, time n log: essential_inputs |
| Bitdeque | parameterized lookup | head/tail discards leave the indexed entry in the deque | linear: 2T commands, discard blocks sum to T |
| brainfuck | tree | `decision_tree_program` | linear: decision_tree_program, span walk, leaf moves geometric |
| BrainIf | finite lookup | a spatial table is addressed by the read row index | linear: n + T strip cells of 51 lines |
| Circlefuck | tree | its local shape guard is equivalent to the shared guard | linear, time n log: essential-input byte compare; greedy candidate's walk |
| Circuit Diagram | tree | finite planar routing | linear: H-layout side C sqrt(T), area Theta(T) |
| Clockwise | tree | finite grid layout | linear: alternating rectangle of area O(T), exits in walk order |
| Collatz Multiverse | tree | finite cell placement | linear: folded tree, shortest names deepest, flat appends |
| Container | finite lookup | the reversed table is one decimal literal divided by ten in a fixed two-bank network | linear: one T-digit literal in a fixed network |
| Crement | parameterized tree | each input is the data of one jump in a two-line tester; a node patches the tester's two targets to its children and jumps in, and a folded subtree targets the shared self-jump or the line past the end | linear: 3(T - 1) + 2n + 3 lines, span walk |
| CV(N)(C) | tree | the halting goto squares once more whenever the program is not shorter than its reach, so every finite tree halts | linear, time n log: greedy order scoring, capped at n <= 10 |
| Decleq | tree | the tree stops `k` levels short, `2**k >= 2n`, and each leaf is a `2**k`-cell table indexed by an unrolled counter, since `T - 1` absolute jump targets would be `Theta(T log T)` digits | linear, time n log: essential_inputs |
| Dig | tree | finite cell placement | linear: axis-swapping rectangle of area O(T), five cells per node |
| Dimensional | tree | `decision_tree_program` with dimensional moves | linear: decision_tree_program with dimensional moves |
| EGL | tree | — | linear, time n log: greedy order scoring, capped at n <= 10 |
| Eval | linear lookup | fixed reversed stack order selects the indexed row | linear: T literal plus halving `;` runs under T |
| Factor | tree | Brainfuck tree followed by a total prime encoding: Dirichlet supplies the next prime in each residue class mod 11, and the integer is arbitrary precision on both sides | lower bound: Theta(T) prime runs of Theta(log T) digits; language Omega(T log T / log log T) ([factor](factor.md)) |
| Fargo | tree | finite folded layout | linear, time n log: Moebius transform, n passes over 2**n |
| Flowchart | finite lookup | a five-row deque preloads `2**n` answers and discards opposite halves | linear: 2T preload nodes and T arm cells on five rows |
| Forbin | tree | — | linear, time n log: greedy order scoring, capped at n <= 10 |
| Forþ | tree | — | linear: span walk, constant dispatch, step literals geometric |
| Grapheme | tree | arbitrary integer variable keys remove the old 24 one-letter-key ceiling | linear, time n log: essential_inputs |
| Home Row | parameterized tree | — | linear, time n log: essential_inputs |
| Inject | finite lookup | one table block halved by `O(n)` conditional substitutions | linear: T literal, `.` halvings sum to 2T |
| Jaune | finite lookup | a spatial table reached with two labels | linear: two cells per row, unary weights sum T - 1 |
| LaserFuck | finite lookup | weighted arms select one of `2**n` prewritten cells, cleaned in one sweep | linear: three rows of linear appends, ~15T |
| Minifuck | parameterized construction | `_mux` is the total fallback; its six failure sites close uniformly in `n` | linear: mux lookup, constant strings times O(T) counts |
| Minsky Swap | parameterized lookup | every input is one `++`/`**` run; a stage per input adds its weight to the index register, and a `~` cascade routes the index to one of two shared leaves at the head of the program, so every table of one arity renders to the same length | linear: cascade routes to two shared leaves, one-digit targets |
| Modulous | tree | — | linear: span walk, fold digits geometric |
| NoComment | finite lookup | from 4 inputs the index is a run of byte-sized skips on the stack and the rows are code: a chain of uniform groups lands on the row, and the rows after it telescope to `table[index]` on six tape cells | linear, time n log: essential_inputs |
| 123 | parameterized construction | table-independent separation plus verdict; failed tight geometry falls back to doubling geometry | linear: geometric paint per input, one-pass endgame |
| Packlang | tree | — | linear: folded tree, shortest names deepest, flat pieces |
| Painfuck | tree | Brainfuck tree transliteration | linear: brainfuck tree, O(L) transliteration |
| Polynomial | tree, cap | each finite instruction list has a finite prime-product encoding | open: multiplicity is priced at Omega(T**2 / log**2 T) by the confluent certificate; the extra log reduces to `N' <= 6 L_real + E` (m_routing <= 3 L_real), with the per-condition closer-nesting step verified but not formalized ([polynomial](polynomial.md)) |
| Qoibl | tree | — | linear: span walk, O(1) node tests by halves |
| RAM0 | parameterized lookup | a straight-line RAM initializer plus a unary-weight lookup | linear: 16-17 tokens per row, unary runs 2T - 2 |
| ROTfuck | tree | movement search stops after at most eight offsets | linear, time n log: essential_inputs |
| S*bleq | finite lookup | packed chunks decoded after the hoisted read block | linear: T/n packed chunks of n bits, O(n) decoder |
| 6-5 | finite lookup | past 35 inputs the positional walk loops on sixteen labels: each bit advances the pointer to the first row whose 2-adic valuation mark reads zero, and one pass per bit shifts the marks | linear, time n log: greedy order scoring, capped at n <= 10 |
| SLOW ACV MAMMALIAN | linear lookup | a read chain banks each bit as a 256-multiple weight on array 16; one trampoline lands the indexed 256-token leaf | linear: per-node landing search sized in O(1), not an O(weight) dry build |
| Sophie | tree | — | linear, time n log: shared-state build, n 2**n state characters |
| Streetcode | tree | — | linear: alternating-axis H-tree, area Theta(T) |
| Suffolk | tree | — | linear, time n log: essential_inputs |
| Super SNUSP | tree | each folding pass removes at least one pending unit | linear: one `*` per entry; ANF only below five inputs |
| Taglate | tree | — | linear, time n log: essential_inputs |
| 3D Brainfuck | tree | Brainfuck tree transliteration | linear: brainfuck tree, O(L) transliteration |
| 3x | tree | — | linear, time n log: essential_inputs; greedy order scoring, capped |
| Unsquare | tree | stack arrangement affects size only | linear: span walk, pricer sums geometrically |
| Vandevelo | minterms | constant-one subtrees drop their suffix literals | linear: amortised peel; sqrt(log T) dual-basis core; proof fallback n 2^n |

## Exceptions and walls

No `exception` row remains: the one such generator, `%^2^-1`, left with its
language.  Every remaining row is `Total`, or theoretically total past the
resource ceiling below.

### Resource-ceiling audit

The remaining `cap` rows do have a uniform lift argument.

- Polynomial's `k == n` candidate is the finite decision tree.  Each of its
  finitely many instructions receives a distinct prime root, and removing the
  interpreter-cost screen does not change that encoding.

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

Accordingly, this ledger records 59 theoretical totality arguments and zero
open exceptions; every row is `Total` or theoretically total past a resource
ceiling.
