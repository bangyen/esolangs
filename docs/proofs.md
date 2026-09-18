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
their own specific argument, which no generic battery can reach, and
`pct_squared_minus_one.py` executes the wall below.

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
measuring x2.11 -- is why.  Polynomial is the second such proof, at
`Omega(T**2 / log T)` ([polynomial](polynomial.md)).

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
argument is `exception`, not `cap`.  Audited across all 63 on 2026-09-17:
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

The names are the 63 callable entries indexed by `BY_BOOLEAN`.  Rows sharing a
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
| COD | parameterized tree | each input's run sets the cod's value at its own fork box, once; the leaf cascade prints the entry | open: a level's zero test spends Theta(R) cells per block of R values |
| Collatz Multiverse | tree | finite cell placement | linear: folded tree, shortest names deepest, flat appends |
| Container | finite lookup | the reversed table is one decimal literal divided by ten in a fixed two-bank network | linear: one T-digit literal in a fixed network |
| Crement | parameterized tree | each input is the data of one jump in a two-line tester; a node patches the tester's two targets to its children and jumps in, and a folded subtree targets the shared self-jump or the line past the end | linear: 3(T - 1) + 2n + 3 lines, span walk |
| CV(N)(C) | tree | the halting goto squares once more whenever the program is not shorter than its reach, so every finite tree halts | linear, time n log: greedy order scoring, capped at n <= 10 |
| Decleq | tree | the tree stops `k` levels short, `2**k >= 2n`, and each leaf is a `2**k`-cell table indexed by an unrolled counter, since `T - 1` absolute jump targets would be `Theta(T log T)` digits | linear, time n log: essential_inputs |
| Dig | tree | finite cell placement | linear: axis-swapping rectangle of area O(T), five cells per node |
| Dimensional | tree | `decision_tree_program` with dimensional moves | linear: decision_tree_program with dimensional moves |
| EGL | tree | — | linear, time n log: greedy order scoring, capped at n <= 10 |
| Eval | linear lookup | fixed reversed stack order selects the indexed row | linear: T literal plus halving `;` runs under T |
| Factor | tree | Brainfuck tree followed by a total prime encoding: Dirichlet supplies the next prime in each residue class mod 11, and the integer is arbitrary precision on both sides | lower bound: Theta(T) prime runs of Theta(log T) digits; language Omega(T log T / log log T) |
| Fargo | tree | finite folded layout | linear, time n log: Moebius transform, n passes over 2**n |
| Flowchart | finite lookup | a five-row deque preloads `2**n` answers and discards opposite halves | linear: 2T preload nodes and T arm cells on five rows |
| Forbin | tree | — | linear, time n log: greedy order scoring, capped at n <= 10 |
| Forþ | tree | — | linear: span walk, constant dispatch, step literals geometric |
| Grapheme | tree | arbitrary integer variable keys remove the old 24 one-letter-key ceiling | linear, time n log: essential_inputs |
| Home Row | parameterized tree | — | linear, time n log: essential_inputs |
| Inject | finite lookup | one table block halved by `O(n)` conditional substitutions | linear: T literal, `.` halvings sum to 2T |
| Interprogck8 | tree | routed by a shared `DownAccLines` corridor: a read's 48/49 selects dismount against flight by landing parity, stops are phase-separated by depth, and assembly is one pass with no repair loop; the residue pool is probed per arity and places every depth through forty inputs, an unreachable guard | open: a read at depth d is 3 + 2 floor(d / 14) lines, Theta(T n / 14) |
| Jaune | finite lookup | a spatial table reached with two labels | linear: two cells per row, unary weights sum T - 1 |
| LaserFuck | finite lookup | weighted arms select one of `2**n` prewritten cells, cleaned in one sweep | linear: three rows of linear appends, ~15T |
| Minifuck | parameterized construction | `_mux` is the total fallback; its six failure sites close uniformly in `n` | linear: mux lookup, constant strings times O(T) counts |
| Minsky Swap | parameterized lookup | every input is one `++`/`**` run; a stage per input adds its weight to the index register, and a `~` cascade routes the index to one of two shared leaves at the head of the program, so every table of one arity renders to the same length | linear: cascade routes to two shared leaves, one-digit targets |
| Modulous | tree | — | linear: span walk, fold digits geometric |
| NoComment | finite lookup | from 4 inputs the index is a run of byte-sized skips on the stack and the rows are code: a chain of uniform groups lands on the row, and the rows after it telescope to `table[index]` on six tape cells | linear, time n log: essential_inputs |
| 123 | parameterized construction | table-independent separation plus verdict; failed tight geometry falls back to doubling geometry | linear: geometric paint per input, one-pass endgame |
| Packlang | tree | — | linear: folded tree, shortest names deepest, flat pieces |
| Painfuck | tree | Brainfuck tree transliteration | linear: brainfuck tree, O(L) transliteration |
| %^2^-1 | exception | one setter pair, the weight as doublings in the template; the fold's planners cover all tables through four inputs and tested tables through fourteen, but no all-arity proof is known | measured: point relocations, no invariant; x4.8 per input at n=13..14 |
| Polynomial | tree, cap | each finite instruction list has a finite prime-product encoding | lower bound: Theta(L**2 log L) digits for every multiple of the mandatory root product; language Omega(T**2 / log T) |
| Qoibl | tree | — | linear: span walk, O(1) node tests by halves |
| RAM0 | parameterized lookup | a straight-line RAM initializer plus a unary-weight lookup | linear: 16-17 tokens per row, unary runs 2T - 2 |
| ROTfuck | tree | movement search stops after at most eight offsets | linear, time n log: essential_inputs |
| S*bleq | finite lookup | packed chunks decoded after the hoisted read block | linear: T/n packed chunks of n bits, O(n) decoder |
| 6-5 | finite lookup | past 35 inputs the positional walk loops on sixteen labels: each bit advances the pointer to the first row whose 2-adic valuation mark reads zero, and one pass per bit shifts the marks | linear, time n log: greedy order scoring, capped at n <= 10 |
| SLOW ACV MAMMALIAN | linear lookup | a read chain banks each bit as a 256-multiple weight on array 16; one trampoline lands the indexed 256-token leaf | open: ballast loop, 296..878 chunks per build at n=6..12, no bound by inspection |
| Sophie | tree | — | linear, time n log: shared-state build, n 2**n state characters |
| Streetcode | tree | — | open: hall per level spans every leaf row, Theta(T log T); uncapped greedy Theta(T log**2 T) |
| Suffolk | tree | — | linear, time n log: essential_inputs |
| Super SNUSP | tree | each folding pass removes at least one pending unit | linear: one `*` per entry; ANF only below five inputs |
| Taglate | tree | — | linear, time n log: essential_inputs |
| 3D Brainfuck | tree | Brainfuck tree transliteration | linear: brainfuck tree, O(L) transliteration |
| 3x | tree | — | linear, time n log: essential_inputs; greedy order scoring, capped |
| Unsquare | tree | stack arrangement affects size only | linear: span walk, pricer sums geometrically |
| Vandevelo | minterms | constant-one subtrees drop their suffix literals | linear: amortised peel; sqrt(log T) dual-basis core; proof fallback n 2^n |
| WII2D | parameterized construction, cap | Horner's chain is total; the decode folds the extremal same-colour pair, whose midpoint is unique, so every fold is legal | open: a readout rule within a constant of the optima, none known |

## Exceptions and walls

The one remaining `exception` row is two-sided: the language provably
cannot compute every table under the parameterized contract, and below that
wall the generator's reach is not characterized.

- `%^2^-1` can refuse when neither of its fold planners succeeds -- the
  all-row fold on a popcount or distinct ladder, or the staged fold past
  eleven inputs; every table tried through fourteen inputs builds, any
  table symmetric under a complementation of its inputs builds at any
  arity, and from fifteen only tables whose eleven-input cut compacts far
  enough for the next lay to fit do (the dense fixture's has 2017 distinct
  cofactors among 2048 rows, and the lay jams).  No construction can be total: the suite's dense fixture at
  seventeen inputs is computed by no template at any program length
  (proof below), so the totality question is the finite one of which tables
  below the wall a construction misses.

### Attempts on the open cases

**Interprogck8** left this section Sep 2026: the repair loop whose totality
was the gap no longer exists.  The corridor assembly places each gadget once
on computed coordinates, a placement is a bounded congruence scan (a free
line on one class recurs within its modulus times the longest occupied run,
and every occupied run is O(1)), and rungs are shared rather than embedded --
no simultaneous-placement lemma is needed because nothing is ever moved.
Stride classes `30 + 2k` hand residues to successive depth bands; a
class-`k` read's `1 + k` odd lines need `1 + k` free consecutive residues
in every class below it, so the pool per class is probed on the placer at
each arity (fourteen through fourteen inputs, thirteen to 26, twelve to 36,
nine to 40) and the generator refuses a forty-first input, a guard no
representable table reaches.  The earlier text's 1596 depths assumed a
full class leaves room for the next; it leaves one residue, and a class-1
read needs two.

**`%^2^-1` is not total under the parameterized contract.**  A template
program computing a table `f` embeds each input once, reads no stdin (`n`
would raise), halts on every row, and prints exactly the answer byte.  Its
state is the pair `(position, accumulator)`, and the position is uniform
across rows, so between two placeholders the accumulator is the whole state.

*The reset makes every state class-finite.*  In-window values `-3003..3003`
are 6007.  A value above 3003 is zeroed before the next command.  A value
below `-3003` can only decrease or be destroyed -- `s`, `i` and `m` take it
deeper, `p` lifts it past the limit and the next command zeroes it, `'`
zeroes it -- so two deep values congruent mod 256 are never separated: every
command keeps them congruent and deep, or zeroes both, and `e` prints the same
byte (`l` on a deep value prints several characters, which is not an answer
byte for either).  Two rows whose accumulators are equal, both over the limit,
or deep and congruent mod 256 therefore print the same byte for every
completion of the remaining inputs, and the distinguishable classes number at
most `6007 + 256 = 6263`.  Executed on the shipped interpreter
(`tests/proofs/deep/pct_squared_minus_one.py`): 3000 random words on
congruent deep pairs printed identically and left one class, and 1985 of
2000 incongruent pairs printed differently.

*`t` is inert.*  A firing `t` rewinds to position 0, and a halting row's
final pass runs the whole text passing every `t` on a zero accumulator.  A
row prints once, so it prints only in that final pass -- anything printed
before a firing `t` is printed again -- and after the first `t` in the text
its print lies past every position that ever fired.  From that first `t` the
final pass continues from `(t_1 + 1, 0)` on every row, so the output depends
only on the placeholders after `t_1`, which for a table depending on every
input is all of them, and the program is the straight-line run of the text
from there.

*Counting.*  Cut the text after the `k`-th placeholder in text order and let
`S` be the inputs laid so far.  Two prefixes with different `S`-cofactors --
different functions of the remaining inputs -- must lie in different classes,
since the same completion prints different answers.  So for every `k`, the
number of distinct cofactors after fixing `S` is at most 6263, for the `S`
the template's placeholder order induces.  The suite's dense fixture at
seventeen inputs (`_dense(17)` in `tests/tools/test_boolean_contract.py`)
has, for *every* one of the 2380 thirteen-input subsets, at least 7640
distinct four-input cofactors -- computed exhaustively, 8 s, in the same
proof -- so no placeholder order fits, at any program length.  Padding the
fixture with ignored inputs gives a witness at every wider arity.  The bound
is tight enough to place the wall: sixteen inputs never exceed `2**12 = 4096`
distinct cofactors at any cut and the fixture's worst twelve-input cut has
3932, so the counting cannot bite below seventeen; the dense fixture's build
ends at fourteen for a different reason: the staged fold lays an input only
onto a state the conveyor can still merge, and at fifteen the eleven-input
cut has 2017 distinct cofactors among 2048 rows -- nothing to compact before
the lay, and 4096 laid points at unit gaps jam the one-slot window within
1.9k hops.  Reading only the output's last character
would admit `l` on deep values and raise the deep classes to 1280 and the
bound to 7287; the same witness still exceeds it.

What remains is finite: for each arity through sixteen, which tables the
language admits that the shipped planners refuse.  The retired search for a
uniform tail (a doubled negative accumulator plus one offset per placeholder,
the cut `sub(c) m**j add(b)` merging everything above `c + 3003/2**j`, the
span budget of about eight doublings) is bounded by the same count and is not
resumed.

### Resource-ceiling audit

The remaining `cap` rows do have a uniform lift argument.

- Polynomial's `k == n` candidate is the finite decision tree.  Each of its
  finitely many instructions receives a distinct prime root, and removing the
  interpreter-cost screen does not change that encoding.
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
ranking folds by predicted magnitude, so it still refuses about one in six dense
tables at the widest admitted domain, and reaching the extremal-fold
construction means choosing a different fold rather than relaxing a constant.
Prompt refusal is the better behaviour there — the extremal fold spells its
centres in unary, and a refused table costs seconds where the total
construction costs minutes and a megabyte.

Two language walls are proved for `%^2^-1`.  In the ordinary reading model,
every program satisfying the two-input Boolean contract ignores one input:
`n` overwrites the sole accumulator, and the only branch, `t`, rewinds to the
program start, so a clean run cannot preserve the first bit through the second
read.  XOR and AND are therefore impossible at every program length.  The
exported generator is parameterized and contains no `n`, which voids that
theorem's hypothesis -- and under the parameterized contract the state-class
count above is the wall: a seventeen-input table exists that no template
computes.

Accordingly, this ledger records 62 theoretical totality arguments and one
open exception, whose row can never read `Total`: the impossibility is an
unbounded-program proof, which is what turning an exception into “incapable”
requires -- a failed search or a live cap is not one -- and what stays open
is the generator's reach below the wall.
