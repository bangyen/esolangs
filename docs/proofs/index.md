# Boolean-generator coverage proofs

The standalone [Polynomial proof](polynomial.tex) has a
[Markdown companion](polynomial.md) for implementation bounds, measurements
and counterexamples. [Factor](factor.md) proves `Theta(T log T)` text;
[FRACTRAN](fractran.md) proves a super-linear address budget but linear
language complexity through packing, trading characters for steps.
[brainfuck-count](brainfuck-count.md) bounds distinct behaviours of
`C`-character programs. Polynomial's lower bound imports
Corollary 3.4 of [coefficient-mass](https://github.com/bangyen/coefficient-mass/blob/v1/coefficient-mass.tex), the companion
manuscript bounding the coefficient mass of a polynomial multiple.
`tests/proofs/test_citations.py` holds the numbered cross-references
between them to the labels they name.

The ledger records coverage of every `2**n`-bit table for every finite `n`.
“Total” means mathematical coverage. Ignore explicit digit, instruction,
line, tape, route-width, work and generation-time guards when lifting them
leaves the construction unchanged; invalid tables are outside the domain.

The exhaustive `n <= 3` and sampled `n <= 10` sweeps in
`tests/tools/test_boolean_contract.py` seek counterexamples; they do not prove
the coverage arguments.

In `tests/proofs/`, fast-band `test_ledger.py` checks registry consistency,
and `test_schemes.py` checks lookup and parameterized rows (`tree` and
`minterms` have no per-row check). Deeper checks live in `tests/proofs/deep/`.
`all_generators.py` checks all 77 constructions: flipping each table row
changes the emitted program at the tested arities, and each construction
completes an arity ladder on both table shapes. This checks the counting half
of each scheme. Four generators -- A Painter Ant, ArrowQueue, Container and
BIO -- also have construction-specific proofs.

`python -m tests.proofs.deep <band>` selects declared cost bands: `verify`
for the local gate, `ci` for the registry battery, `by-hand` for expensive
checks, and `all` for everything, as with `just proofs`. The justfile,
workflow and `scripts/verify.py` select bands; `test_bands.py` requires each
file's declaration and enforces its stated budget, not a measured runtime.

Coverage does not bound source size: the schemes count nodes and entries,
so a total generator can still emit super-linear text.  `linearity.py` is the
separate, registry-wide scaling contract the roadmap asks for.  It measures
characters per table entry past each generator's last route change and holds
every generator to it except those the roadmap's scaling audit or this
document's `cap` and `exception` rows already exempt. Exceeding the bound is
evidence against linearity; passing it is not a
proof. Factor passes at x2.11 despite its language-level super-linear bound
([factor](factor.md)).  Polynomial's block-incidence lemma forces
`Omega(T/log T)` distinct real instruction-root values even when roots
repeat, and the slack certificate prices every multiple of their distinct-root
product, giving `Omega(T**2 / log T)` for every program, whatever its read
count: only the last two reads before a routing position can carry a residual
that depends on its next input and not on it alone.  The argument is in
[polynomial](polynomial.md).

A `linear` row is within a constant of the worst-case optimum. A language with `c`
source characters has fewer than `c**(L+1)` programs of length at most `L`,
against `2**T` tables of length `T`, so some table needs
`L >= T / log2(c)` characters -- `T/3` for brainfuck's eight commands.
Factor at `Theta(T log T)` and Polynomial at `Theta(T**2 / log T)` provably
exceed that floor; the `open` rows may also exceed it.


Fargo's build bound uses a word RAM with `Theta(log T)`-bit words; input and
output characters are charged. It does not claim linear bit complexity.
For `T = 2**n`, its packing width is `w = max(2, 2**floor(log2(n)))`.
For `n >= 2`, `n/2 < w <= n`. The within-word butterfly takes
`(T/w) log2(w)` word operations, and the remaining transform takes
`(T/w) (n - log2(w))`: together `T*n/w < 2T`. Mask construction costs
`O(w log w)` characters; packing and unpacking cost `O(T)`.

The arm rule uses the same truth functions and coefficient counts as the
unpacked emitter. Counts come from a derived table: start with `[0]` and
append every existing count plus one, `w/2` times. Its `2**(w/2)` entries
are at most `sqrt(T)`; two lookups count a word. Above word width, each
logical level scans `O(T/w)` words, for `O(T*n/w)` work. Below it, scalar
nodes use a fixed number of word operations and lookups; their binary tree
has at most `2T-1` nodes. The bounded five-input alternatives add only
constant-size work.

Identity-order literal indices at height `k` need `O(log(k+1))` characters;
at most `O(T/2**k)` nodes emit them. Their sum is `O(T)`. Other orders can
repeat high indices at leaves and emit `Theta(T log n)` characters, so their
append-only emitters stop as soon as they cannot beat the identity source.
The best source only shrinks. Four named permutations cost `O(T)` by index
doubling, and each reordered emitter writes at most that linear budget.
Thus both order selection and the final join stay inside the build bound.

For narrow output above five inputs, a bottom-up pass ranks prefix nodes
using integer child IDs. Nodes are bucketed by syntax height, at most `2n+2`.
Stable radix passes with `2**ceil(n/2)` bins intern each bucket by operator
and child ranks. There are a constant number of passes per bucket, so total
work is `O(T + n sqrt(T)) = O(T)`, without a hash-table assumption.
At logical height `k` there are at most `T/2**k` occurrences
and `2**(2**k)` truth functions. A deterministic arm/ANF rule produces only
a constant number of wrapper nodes per function, plus `O(n)` literals.
Split the height sum at `m = floor(log2(n/2))`: lower levels total
`O(sqrt(T))` distinct nodes, upper levels `O(T/n)`. Since `sqrt(T)` and `n`
are `O(T/n)`, there are `O(T/n)` definitions. Each label needs `O(n)`
characters and is built with one final join, so both naming and definition
text cost `O(T)`. Expanding a definition recovers the original expression;
no source loop or additional input read is introduced. Default programs are
unchanged; executed scaling regressions cover both layouts.

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

**Size dispatch.**  Some lookup rows ship two routes: a folded decision tree
for tables through a fixed crossover — `n <= 4`, or `n <= 6` for Container;
BrainIf's tree counts only the inputs it branches on — and the lookup above it.  Streetcode builds both at five inputs and keeps
the shorter, so its crossover is where the two meet rather than a constant.
BrainIf also competes with its input-forgetting residual DAG, proved below.
Each route is total on its own domain and the lookup
carries the universal claim, so the tree below the crossover is a size
optimization rather than part of the proof.  A width-constrained build may take
the tree at any arity.  A Painter Ant, Alight, BIO, B-tapemark,
bit~, Bitwise Cyclic Tag, Circlefuck, Clockwise, Collatz Multiverse,
Cyclic tag, ///, Subleq, Dimensional, EGL, Eval, Fish, Flowchart,
Forbin, Minsky Swap, Modulous, NoComment, Packlang, Qoibl, SLOW ACV MAMMALIAN,
Suffolk, Thue and Unsquare keep no tree route at all: A Painter
Ant's
answer strip is smaller than a tree at every arity, Alight indexes a string
literal, bit~ lands the pointer on one tape cell an entry and walks the
bit it finds home, Bitwise Cyclic Tag has no branch to fold a tree into --
the commands it runs are a fixed cyclic sequence, so every table of a given
arity emits the same length, Befunge and Fish read one grid cell per table
entry with `g`, BIO's
telescope is one nested level per row whatever the table says (a degenerate
table only spares it the flat edges' adjustments, under the fold threshold
once the doubling between the input runs is in the text), B-tapemark copies
one mark per row onto the blank grid and walks the pointer to it, Circlefuck
deletes the entries before the one the index names and prints what the
deletions leave under the pointer, Clockwise
writes one cell per entry in a countdown row and stops the pointer on the
one the index names, Collatz
Multiverse writes one cell per four table rows at every arity, Dimensional
paints one cell an entry along dimension 1 and a bare `>` displaces the
pointer onto it by the bit it is standing on, EGL paints one
cell an entry and walks a pointer to it, Eval is one linear
lookup at every arity, Flowchart pushes one deque entry a row and walks
the cursor to it (its tree is the width-constrained route), Forbin paints a
128-entry block as one call's argument list at every arity and its branches above seven inputs choose a block rather
than route a table, Packlang paints one array block and indexes it at every
arity, Minsky Swap's `~`
cascade routes the index to one of two shared leaves with a one-digit target
per row, Modulous pushes the whole table as one string literal and spends
the row index popping it down to the answer, NoComment switches between two lookups at four inputs, Qoibl divides one
literal by the power of two its reads build,
SLOW ACV MAMMALIAN's read chain emits one fixed-width leaf slot per
row whatever the table says, Suffolk sweeps a countdown past every row,
Unsquare pushes the whole table onto the stack a cell a row and pops the row
index off the top of it, Thue makes the table its starting state and rewrites
every adjacent pair down to one per input; none has a subtree to
fold.  Collatz Multiverse, Eval, NoComment, Suffolk and Unsquare fold a degenerate
table anyway, because their lookup route is what shrinks it -- Suffolk through
`essential_inputs`, which halves the sweep per input dropped, Unsquare through
the same call, which halves its table, and Collatz
Multiverse because a table with few distinct nibbles needs fewer cell
constants and a shorter decoder; that is why the fold discriminator
in `test_schemes.py` carries them as documented exceptions.

## Generator ledger

Names are the callable entries in `BY_BOOLEAN`. Proof names the coverage
witness, which may differ from the shipped route; Qualification supplies
the language-specific step or exception. Shared schemes use the proofs
above. `cap` means total after the stated resource ceiling is lifted.

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

The Execution column is the generated program's commands to halt, worst
sampled row; the Workspace column is its peak written state in bits, every
top-level part of the VM snapshot the run ever changes, counted whole
(`scripts/benchmark.py`'s `WrittenState`), so read-only code is excluded and
a preallocated tape or a self-modified program counts.  `poly n` grows at
most x1.5 an input, `linear` at most x2.15, `T log T` (T cells of `log T`-bit
values) at most x2.5; `unmeasured` says why.  `tests/proofs/deep/execution.py`
and `tests/proofs/deep/workspace.py` measure halting rows on parity tables,
and a `poly n` cell on a seeded dense table too: parity has n ANF terms and
hid Fargo's, Forþ's, INTERCAL's, Vandevelo's, S\*bleq's and 6-5's `T`.  That
dense series runs to n=12 and its increments, which cancel a fixed overhead,
may grow at most x1.4 an input: NoComment's `T/32`-byte stack read x1.00 on
the ratio behind a 32,768-bit tape and x1.99 on the increments, SLOW ACV
MAMMALIAN x1.43.  Vandevelo is exempt from the increments: its registers grow
~sqrt(T) until an n*n cap binds at n=14, past what the band can step.  A
`poly n` cell also names its mechanism, read from the generator.  A cell
that opens `worst` gives a formula derived from the code and reached by some
table; `at most`, one never exceeded.  `bl(x)` is the bit length of x, `L`
the program's length and `T` is 2^n.  `tests/proofs/test_execution_formulas.py`
and `tests/proofs/test_workspace_formulas.py` run them at small n; Painfuck's
`at most` is also proved for every n.

<!-- PROOF-STATUS:START -->

| Generator | Proof | Qualification | Scaling | Execution | Workspace |
| --- | --- | --- | --- | --- | --- |
| A Painter Ant | parameterized lookup | each embedded bit keeps the ant on a self-painting corridor or lifts it off, and the template walk after it advances the ant by that bit's weight, stopping at the corridor's end, leaving it over the indexed answer cell or the trailing run's first, which answers alike | linear: table walk; corridor weights sum to T | unmeasured: halts on no row; a proven cycle answers | unmeasured: halts on no row, so there is no peak |
| AddSubJump | finite lookup | packed `n`-bit cells selected by a self-modified operand | linear: T/n packed cells of O(n) digits, O(n) decoder | linear: worst (11n+4)⌊T/n⌋ + 11T + 13n - 17 past n = 5, one more from n = 10 | linear: the self-modified program, T/n packed cells |
| Algebraic Programming Language | minterms | base-26 names are unbounded | linear, time n log: greedy order scoring, capped at n <= 10 | poly n: worst ceil(65n / 2) - 21 commands, one guarded path | poly n: an expression work stack two nodes per input level |
| Alight | finite lookup | inputs folded into a row index by Horner's rule; the table is a string literal read with `at`, so the program has no branches | linear: one T-character literal, O(n) Horner reads | poly n: worst 2n + 5 commands, n Horner reads and one `at` | poly n: worst 72n + 762 + bl(6n+12) + bl(n) bits, n in 2..25 |
| ArrowQueue | parameterized lookup | one stage per input doubles the queued markers and adds the bit (Horner), and the count selects one of `2**n` constant-size cascade stages | linear: at most 6n + 3T rows, the constant tail folded | linear: within x2.15 an input, by the execution contract | linear: worst T + 11 + bl(3T+6n+5) bits past n = 4: a queue of T markers |
| B-tapemark | finite lookup | the blank grid is the table, one mark per row copied by `*`; a stage per input walks the mark pointer by that input's weight and `+` prints the mark it lands on | linear: 3T copy cells, T pointer steps, one stage per input | linear: within x2.15 an input, by the execution contract | T log T: two mark grids keyed by coordinates, about 4T marks |
| Back | parameterized tree | — | linear: leaf moves sum geometrically, sparse row render | linear: worst max(T,6n-1) + T + 3n + 6 commands: the load column, then the all-ones path | poly n: worst n + 5 + bl(max(6n-2,2^n-1)) + bl(3n+4) + bl(n) bits |
| Befunge | exception | six-bit ASCII lookup ships through thirteen inputs; finite source space excludes some sixteen-input tables | linear: T table cells, one g at the index | unmeasured: exempt as an exception row | poly n: at most six stack items; the grid is never written |
| Bitwise Cyclic Tag | parameterized lookup | the table is the program, one four-bit cell per row; each embedded bit appends two walk zeros per unit of its place value, and a cell consumes exactly two, so the zeros carry the program pointer to the indexed cell and the held-back sentinel arrives there to fire it; the cell's second `0` consumes the answer it just appended, without which a 1 would cascade into the rows below | linear: 4T table cells, 4T walk appends, 5T + n steps | linear: worst 5T + n commands on every table: input segments, then 3 per walk cell | linear: worst 16T + 8 + bl(8T+n-2) + bl(2T+n+1) bits: a data queue of 2T bits |
| BF-PDA | parameterized tree | — | linear: span walk, leaf drains sum geometrically | poly n: worst 10n + 2 commands, one path of n tests | poly n: worst 3n + 4 bits: 2n stack bits and an (n+4)-bit cursor |
| BFStack | minterms | — | linear: zero-row walk telescopes to T | poly n: worst 60n + 475 commands past n = 7 | poly n: a loop stack of at most 128 and an O(n) data stack |
| BIO | finite lookup | nested loops telescope from `table[0]` to `table[index]` | linear: T - 1 loop pieces joined once | linear: worst 18T - 10n + 30 commands: Horner doubling 13T, decrement loops 5T | T log T: worst max(2n,8) + Σ_{j<T-1} bl(10n-8+3j) + bl(4T+10n+37) bits: T - 1 return indices |
| bit~ | linear lookup | one tape cell an entry, and each input's one-shot loop jumps the pointer left by that input's weight, so the reads chain into a Horner index and a self-erasing walk carries the landed bit to one of two print windows | linear: bounded dependency scan and canonical residual IDs | linear: worst 7T + 17n + 92 commands past n = 1: row 0 walks the odd lane | linear: worst 2T + 49 + bl(2T+41) + bl(5T+18n+74) + bl(n) bits: 2T + 49 tape cells |
| Bitdeque | parameterized lookup | head/tail discards leave the indexed entry in the deque | linear: 2T commands, discard blocks sum to T | linear: worst 3T + 9n - 3 commands past n = 4: load 2T, then the stage walk | linear: worst T + 2 + bl(4T+10n-5) bits past n = 4: a deque of T + 1 bits |
| brainfuck | tree | `decision_tree_program` | linear: decision_tree_program, span walk, leaf moves geometric | poly n: worst 69n + 44 commands, the AND table's all-ones row | poly n: worst 2n + 6 + bl(2n) + bl(n) + bl(L) bits |
| Boolfuck | tree | each input byte's low bit is read onto its own cell and tested in place by a flip-only decision tree, one flag interleaved beside each bit, consuming and emitting complete bytes | linear: constant cost per node, difference ratio ~3.9 at n=8..12 | poly n: worst 2n^2 + 27n + 8 commands; reads shuttle to scratch | poly n: a bit and a flag per input, plus scratch |
| Cyclic tag | parameterized lookup | weighted zero padding advances the cyclic rule pointer to the indexed answer; the next empty rule deletes it | linear: 5T + 2n + 1 characters, weighted padding | linear: worst 2T + n + 1 steps on every table: n input rules, 2 per row, 3 closers | linear: worst 16T + 1 + bl(2T+n) bits: a queue of up to 2T - 1 bits |
| /// | parameterized lookup | binary-to-unary substitutions form the row index; T escaped sweeps consume indexed entries before decoding one answer and deleting the suffix | linear: T fixed-size sweeps and 2T table characters | linear: worst 6T + n + 19 steps: rule parses, failed searches and substitutions | linear: worst 8L + 56 + 8max(0,T-15) bits: the program string, rewritten in place |
| Subleq | finite lookup | direct-jump packed decoder with byte reads and self-modifying chunk selection | linear: T/n packed chunks of n bits, O(n) decoder | linear: worst 8T + (7n+5)(⌊T/n⌋-1) + 23n - 8 steps: the last full chunk, all ones | linear: the self-modified program, T/n packed chunks |
| BrainIf | tree | equal cofactors share one layered DAG node; spatial lookup remains a candidate | linear: O(T/n) nodes with O(n)-digit addresses | poly n: worst 4n + 50 commands, one DAG path and a tail | poly n: worst 13 + bl(lines) + bl(n) bits: two cells, a line cursor |
| Circlefuck | linear lookup | the tape is the program, so the table is its tail past the `@` that stops the run, entry 0 abutting the index digits at the ring's end; `}` deletes the cell under the pointer and slides the digits down into it, so counting the index out against one `}` apiece leaves the entry it names under the pointer | linear: bounded dependency scan and canonical residual IDs | linear: worst (2n+13)T + 63n + 89 + 2S to n = 7, S the codes of program characters 1..n | linear: worst 6L + 10n + 7 + bl(L-1) + bl(L-T-2) + bl(n) bits: the program is the tape |
| Circuit Diagram | tree | finite planar routing | linear: H-layout side C sqrt(T), area Theta(T) | poly n: worst 2n + 1 commands; 2n + 2 past n = 7 | T log T: gate latches and live pulses over O(T) gates |
| Clockwise | linear lookup | the ring is the table: one `!` per entry in a countdown row, and the index in the accumulator picks which one it is zero on, turning the pointer down that entry's own column; seven `.` an input build the index by Horner's rule, doubled between inputs by a two-row gadget that spends the accumulator as distance and buys back two per unit | linear: five table rows of 2T columns, doubling gadgets whose widths halve downward | linear: worst 10T + 20n + 30 steps on every table: the pointer's path to the last row | poly n: worst 57n + 50 + bl(2n+14) + bl(2^(n+1)+9n+1) bits: 7n-character queue |
| Collatz Multiverse | finite lookup | an array subscript may name `lineNumber`, so a cell is addressed by the number of the line that writes it | linear: one line per four rows, a 64-cell decoder, 3n index lines | linear: at most T/4 + 3n + 130 lines to n = 8: one step per line, no branching | T log T: array A, T/4 cells keyed by a log T-bit index |
| Container | finite lookup | the table is the prefix sum of its own steps, summed against a row counter that is live for one tick | linear: one line per step in the table, halting in 2n+2 ticks | poly n: worst 2n + 2 commands, a threshold build past n = 6 | poly n: worst 25n + 154 + bl(2n+2) + 2bl(n) bits, n in 7..24 |
| Crement | parameterized tree | each input is the data of one jump in a two-line tester; a node patches the tester's two targets to its children and jumps in, a folded subtree targets the shared self-jump or the line past the end, and a subtree already emitted at its level is targeted, not repeated | linear: at most 3(T - 1) + 2n + 3 lines, subtree ids | poly n: worst 5n + 2 commands, shared self-patching testers | linear: the whole program tuple, about 3T/n patched lines |
| CV(N)(C) | tree | the halting goto squares once more whenever the program is not shorter than its reach, so every finite tree halts, and a subtree already emitted at its level is entered by climbing the accumulator to its syllable and `j`, where shorter | linear, time n log: greedy order scoring, capped at n <= 10 | linear: at most 17 + 4n + (n-1)(3 + sqrt(2L)) tokens: the path plus shared-subtree climbs | poly n: worst 2n + 20 + bl(2n-1) bits, n in 4..13 |
| Decleq | tree | the tree stops `k` levels short, `2**k >= 2n`, and each leaf is a `2**k`-cell table indexed by an unrolled counter, since `T - 1` absolute jump targets would be `Theta(T log T)` digits | linear: bounded dependency scan and canonical residual IDs | poly n: worst 49n + 3*2^k + 2 commands, k = bitlen(2n-1) | linear: the memory tuple, T table cells patched in place |
| Dig | tree | finite cell placement, six inputs left to a painted leaf table | linear: leaves are 64-cell rectangles two `$` counts index, area O(T) | linear: worst 128 + 46·2^((n-6)/2) for even n, 128 + 64·2^((n-7)/2) for odd, past n = 6 | linear: worst 8RC + bl(R-1) + bl(C-1) + bl(2n-1) + bl(n) + 10 bits past n = 4: the R×C grid |
| Dimensional | linear lookup | a bare `>` takes its dimension from the byte it stands on, so `d>` is a pointer displacement by the bit read: the index is a coordinate, doubled between reads by a two-loop `{`/`}` gadget, and it addresses one painted cell an entry along dimension 1 | linear: 2T table characters plus a fixed gadget per input | linear: worst 15T - 8n + 37 commands: paint 2T + 2, then 13 per index unit doubled | T log T: worst Σ_{k<T} bl(k) + 5T + n(n-1)/2 + 4n + 6 + bl(2T+20n+40) + bl(2n-1) bits |
| EGL | finite lookup | row 1 is painted with the table and each input's `(-...)` guard walks the row-0 pointer right by that input's Horner weight, so `v=` prints the indexed cell | linear: T painted cells, guard weights sum to T - 1 | linear: worst 3T + 52n + 4 commands: paint the table, 50 per input, weights summing to T - 1 | linear: worst 2T + 2n + 7 + bl(L-d-3) + bl(L-d-9) + 2bl(n) bits, d the digits of T |
| Eval | linear lookup | fixed reversed stack order selects the indexed row | linear: T literal plus halving `;` runs under T | linear: worst 2T + 13n + 1 commands: one per program character, then the final frame pop | linear: worst 8L + T + n + 2 + bl(L) bits: frame program text and a stack |
| Factor | tree | Brainfuck tree followed by a total arbitrary-precision segmented-sieve encoding; fixed-modulus short intervals bound its adaptive residue sequence | lower bound: tight language and generated Theta(T log T) ([factor](factor.md)) | poly n: worst 265n + 231 commands, after a 247n + 240 prelude | poly n: worst 7n + 12 + bl(2n+1) + bl(n) + bl(27·2^(n-1)+16n+14) bits |
| FALSE | tree | — | linear: 12 characters an internal node, two a leaf | poly n: at most min(12n + 69, 10n + 99) commands, 26 stored lambdas | poly n: at most (2n+56)(n+4) + n + 1 + bl(n) bits: 26 lambdas |
| Fish | finite lookup | the inputs form a Horner row index and `g` reads that column from the table row | linear: T table cells, one g at the index | poly n: worst 9n + 9 commands, n Horner reads and one `g` | poly n: worst n + 13 + bl(9n+8) + bl(n) bits: one stack, x |
| Fargo | tree | finite folded layout | linear: word-packed transform and budgeted emission | linear: within x2.15 an input, by the execution contract | linear: the top frame's token tuple, the whole expression |
| Flowchart | finite lookup | a pair of answers per deque, and the input walks the deque cursor to the pair it wants | linear: T pushes, `T/2 - 1` cursor steps, two rows | linear: worst 3T + 9n + 4 nodes: preload T plus runs, then 8n of selection reads | T log T: about 4T exit-memory entries and T/2 deques |
| Forbin | finite lookup | the last seven inputs paint a block of `2**7` table entries as one call's literal argument list, and each of them halves the callee's parameter window with one multi-assignment, so the first parameter ends up holding the addressed entry | linear: two characters an entry, halvings sum to `2 * 128` | poly n: worst 2 max(n - 7, 0) + 2 commands | linear: call frames embedding the parsed main body |
| Forþ | tree | — | linear: span walk, constant dispatch, step literals geometric | linear: within x2.15 an input, by the execution contract | T log T: at most (2n+364)T + 43n + 2bl(n) bits: frame text and the scope dictionary |
| FRACTRAN | parameterized tree | the bits are the exponents of `n` primes in the starting value, a tree over the high bits reaches a block of `w` entries carried as one exponent, a fixed decoder shifts the block by the offset the low bits spell, and the first-match rule is the else-branch | linear: 3T/w blocks of w = Theta(n) entries, one exponent each | linear: worst n + 2 to n = 4, n + 60 for n = 5..9: the block decoder halving | poly n: n prime exponents of O(n) bits each |
| Grapheme | linear lookup | the whole table is one int-mode literal read in base 10, and each `W` squares an accumulator and doubles it on a 0, which is Horner's rule for the complemented index, so the accumulator is exactly the power of two that `R` shifts the wanted entry down to bit 0 | linear: bounded dependency scan, one table literal, n read blocks | linear: worst 14n + 32 + d commands, d the digits of 2^T: one per program character | linear: worst 16d + 112n + 312 + bl(14n+d+17) + 2bl(10^(d+1)+2^T-1) + bl(2n) + bl(n) bits, d the digits of 2^T |
| Home Row | parameterized tree | — | linear: bounded dependency scan and canonical residual IDs | linear: worst 10T + 10n + 95 commands: all T - 1 guarded leaves run | poly n: worst n + 32 + bl(14·2^n+10n+15) bits: index cell and cursor |
| Inject | finite lookup | one table block halved by `O(n)` conditional substitutions | linear: T literal, `.` halvings sum to 2T | poly n: worst 8n + 10 commands past n = 4, halving per level | linear: the T-character table line, halved in place |
| INTERCAL | parameterized tree | equal-width constants set each input once; fully grouped mingle, unary logic, and select expressions form a Shannon tree | linear: reverse-depth numbering confines long names near the root | linear: at most 2n + 3 + Σ_{0<l<n} min(2^l, 2^(2^(n-l)) - 2) statements, one per named node | linear: about T/n shared-node variables |
| Jaune | finite lookup | a spatial table reached with two labels, against a hoisted tree that lays out each distinct subtable once and jumps to it | linear: two cells per row, unary weights sum T - 1 | poly n: at most 8n - 2 commands, one root-to-leaf path | poly n: at most n + 1 + bl(5·2^n+5n-4) + bl(n-1) + bl(2n-1) bits |
| LaserFuck | finite lookup | weighted arms select one of `2**n` prewritten cells, cleaned in one sweep | linear: three rows of linear appends, ~15T | linear: worst 18T + 56n + 5 commands past n = 4: one pass along the weighted row | linear: worst 12T + 2n + 11 + 2bl(n) bits past n = 4: 3T + 1 tape cells |
| Line | tree | finite decision trees read inputs and choose a Boolean leaf; separated strokes preserve every branch | linear: alternating subtree extents bound rectangular area by O(T) | poly n: worst 5n commands, one fork per level | poly n: worst n + 1 + bl(3n-2) + bl(n-1) + bl(2n-1) + Σ_{c<n} (max(1,bl(c)) + 1) bits past n = 4 |
| Malbolge | exception | finite source space rules out some 18-input tables; the shipped branch-free five-cell mixer covers every table through ten inputs, a two-level pointer cascade covers eleven, a selector that splits the last input off that cascade covers twelve, answer stubs that read the last input cover thirteen, and four copies of that table selected by inputs twelve and thirteen cover fourteen; fifteen and sixteen replace the hash with a positional address, three input bits per two-trit digit, so no row collides; the cap is sixteen, and seventeen is open ([malbolge-scaling](malbolge-scaling.md)) | measured: fixed 59049-cell store through n <= 16 | unmeasured: exempt as an exception row | unmeasured: a fixed 59,049-word memory, too slow to step |
| Minifuck | parameterized construction | `_mux` is the total fallback; its six failure sites close uniformly in `n` | linear: mux lookup, constant strings times O(T) counts | linear: at most L commands: straight-line, the cursor never moves back | linear: worst 6T + 30 + bl(6T+28) + bl(6T+30) + bl(L) bits past n = 4: a tape bit-integer |
| Minsky Swap | parameterized lookup | every input is one `++`/`**` run; a stage per input adds its weight to the index register, and a `~` cascade routes the index to one of two shared leaves at the head of the program, so every table of one arity renders to the same length | linear: cascade routes to two shared leaves, one-digit targets | linear: worst 2T + 6n + 4 commands: a unary index add, then the ~ chain down | poly n: worst n + 3 + bl(2^(n+1)+6n+5) bits: two registers and cursor |
| Modulous | linear lookup | the table is one `PSH STR` literal, pushed so that row 0 lands on top, and the inputs add their weights into the counter of how many characters to discard | linear: T-character literal, one read block an input | linear: worst 5T + 5n - 2 commands past n = 1: n reads, then 5 per entry discarded | linear: worst 6T + n + 2 + bl(6n+5) + bl(2n-1) + bl(n) bits: table codes on the stack |
| NoComment | finite lookup | from 4 inputs the index is a run of byte-sized skips on the stack and the rows are code: a chain of uniform groups lands on the row, and the rows after it telescope to `table[index]` on six tape cells | linear: bounded dependency scan and canonical residual IDs | linear: worst 12T + 50n + 79 commands for n = 4..6, then 3T + 3T/32 + 240n - 491 | linear: worst 32768 + T/4 + 30 + bl(L) bits past n = 4: byte tape and stack |
| 123 | parameterized construction | table-independent separation plus verdict; failed tight geometry falls back to doubling geometry | linear: geometric paint per input, one-pass endgame | linear: within x2.15 an input, by the execution contract | T log T: at most 9 + Σ_{c≤M} bl(c) + bl(L) + bl(M) bits past n = 3, M = 5T+3n-3 |
| Packlang | linear lookup | one 128-row array block, painted inside the `If` that selects it | linear: one write per differing row, block-bounded index digits | linear: worst 19T/2 - n - 4 steps for n = 2..7, then 3T/64 + 1206 - n | poly n: a 128-cell array and O(n)-bit block registers |
| Painfuck | tree | decision tree emitted directly in Painfuck's own commands; numeric I/O pays no ASCII offset, and `d` resets the pointer to the answer cell | linear: brainfuck-shaped decision tree; `d` reset keeps leaf returns O(1) | poly n: at most ceil(3n^2 / 4) + 20n + 4 commands, one path | poly n: 2n + 2 cells and a loop stack of at most n |
| Piet | finite lookup | each table entry is pushed and an input index selects its output; literal products replace conjunction tables | linear: one bounded-width strip with O(T) codels | linear: worst 2T + 4n + 14 steps past n = 1: one colour block per operation | linear: worst T + 2n + 7 + bl(3T+5n+15) + bl(2n-1) + bl(n) bits past n = 2: the stack |
| Polynomial | tree, cap | each finite instruction list has a finite prime-product encoding; every program for a maximal-width table needs Omega(T/log T) distinct real roots ([polynomial](polynomial.md)) | lower bound: coefficient mass is Omega(T**2 / log T), matching the uncapped residual-DAG construction; equal-root blocks force Omega(T/log T) distinct real roots and the slack certificate prices every multiple ([polynomial](polynomial.md)) | unmeasured: exempt as a cap row | poly n: one register of O(n) bits |
| Qoibl | linear lookup | the table is one binary literal, divided by the power of two the reads build | linear: T-bit literal, one squaring statement per input | poly n: worst n + 2 commands, one statement per input | linear: worst T + 3 + bl(n) + bl(n+2) bits: variables 0 and 1 |
| RAM0 | parameterized tree | the inputs are stored once and each node loads its bit with `L`; a subtree already emitted is reached by `goto`, so only the distinct subtables are laid out, and the straight-line lookup is kept as a candidate | linear: O(T/n) distinct subtables, O(n) commands each | poly n: worst n^2 + 8n + 5 commands, one root-to-leaf path | poly n: worst n + bl(S) + 2max(1,bl(n-1)) + Σ_{a<n} max(1,bl(a)) bits, S the token count |
| ROTfuck | finite lookup | every loop's cycle is 0 (mod 8), so its exit rotation is the same whatever its trip count | linear: bounded dependency scan and canonical residual IDs | linear: within x2.15 an input, by the execution contract | linear: 2T + 2 tape cells |
| S*bleq | finite lookup | packed chunks decoded after the hoisted read block, against a hoisted tree that lays out each distinct subtable once and jumps to it | linear: T/n packed chunks of n bits, O(n) decoder | linear: worst 3n + 2 instructions to n = 9, the tree route: n reads, 2n - 1 tests | linear: at most 3L bits: the self-modified program, decimal cells |
| 6-5 | finite lookup | past 35 inputs the positional walk loops on sixteen labels: each bit advances the pointer to the first row whose 2-adic valuation mark reads zero, and one pass per bit shifts the marks | linear, time n log: greedy order scoring, capped at n <= 10 | linear: within x2.15 an input, by the execution contract | linear: worst 2T + 7n + 9 + bl(n) bits past n = 6: a tape of 2T cells |
| SLOW ACV MAMMALIAN | linear lookup | a read chain banks each bit on array 16 and the dispatch's `DIGEST LEAPFROG` reads that sum as the leaf address; the five lightest weights are CONSUMEd from planted cells, so they never read the sum and need not be multiples of 256, which puts the stride at an eight-token leaf | linear: per-node landing search sized in O(1), not an O(weight) dry build | poly n: n read nodes after a fixed dispatch and leaf | linear: two arrays keep every excreted byte, about 8T/255 each |
| Smallfuck | parameterized tree | each level owns a bit, branch flag, and result cell; a child transfers its result three cells upward, so the depth-first pointer walk crosses each tree edge only a constant number of times | linear: six characters an input, approaching 48.5T characters | poly n: at most 9n^2 + 100n + 20 commands, one tree path | linear: worst L + bl(L) + bl(3n) bits: one tape bit per source character |
| Sophie | tree | — | linear: canonical child IDs, shared states, one token join | linear: at most 5n + T/4 + 1 commands: forward only, one per skipped labelled block | poly n: at most bl(L) + bl(n) + 7 bits: cursor, accumulator, input count |
| Streetcode | linear lookup | the street writes one cell per entry, then each input's mouth forks on its bit and its side room walks the cell pointer left by that bit's weight, leaving the car over the indexed entry | linear: nine rows of street, ~1.8T columns | linear: within x2.15 an input, by the execution contract | T log T: a cell dictionary, one address-keyed entry per 1 |
| Suffolk | linear lookup | a countdown built from the row index reads zero exactly on the rows below it, so counting the table's rising and falling steps against it telescopes to the indexed entry | linear: bounded dependency scan and canonical residual IDs | linear: worst L + 151 commands: one straight pass, then the wrap to the first read | poly n: worst bl(L-1) + max(6,n-1) + max(19,4n-1) + bl(n) + 4 bits: eight cells, four counters |
| Super SNUSP | tree | each folding pass removes at least one pending unit | linear: one `*` per entry; ANF only below five inputs | linear: worst 2T + 19n + 22 commands past n = 4: one straight line, the all-ones table | linear: worst T + 2n + 12 + bl(L) + bl(n) bits past n = 4: the packed-table cell |
| Taglate | tree | — | linear: bounded dependency scan and canonical residual IDs | linear: worst 16T + (7n^2+26n-22)/2 for even n > 2, 28T + (7m^2+22m-36)/2 for odd, m = n + 1 | linear: worst 24·2^m + 12m + 12 + bl(m) + bl(L-4·2^m-7m+1) bits, m = n rounded up to even |
| Thue | linear lookup | the table is the starting state, one character an entry, and the bit read rewrites every adjacent pair to one of its two members, so the state halves per input and the last character is the answer; the rules never overlap, so the language's random rule choice has nothing to choose | linear: T state characters, nineteen fixed rules | linear: worst 2T + 3n - 2 rewrites: n rounds, each a marker sweep out and back | linear: worst 8T + 24 + bl(2n) bits: the T + 3 character state string |
| thisthat | tree | inputs go to either end of one bistack row, an ignored one to the column; each end pop drives the next alternating-axis decision node, or goes to the column where the halves agree, in an order the row can pop | linear: the planar H-tree has `O(sqrt(T))` width and height | linear: worst 32·2^(n/2) - 29 for even n, 48·2^((n-1)/2) - 29 for odd, past n = 2: about sqrt T | poly n: worst 4n + 89 + 2bl(n) + Σ_{c<n} max(1,bl(c)) bits past n = 2 |
| 3x | tree | — | linear, time n log: greedy order scoring, capped | linear: worst L commands: the all-ones row enters every guard, no loop repeats | linear: one fraction per executed guard, never popped |
| Underload | parameterized tree | equal-width input programs leave one selector apiece; each node stores both branches as strings and the selector evaluates exactly one, while a constant leaf discards the unused selectors; a repeated subtree is pushed once and carried above the next selector, and the plain tree stays a candidate | linear: 7n input characters plus at most 11T - 4 tree characters | poly n: at most 14n - 1 commands, one path of n selections | linear: spliced program text plus a branch-string stack |
| Unlambda | tree | each half is a `d` promise, forced by the `?` test that selects it, since an argument spelled inline would be evaluated before the application; the shipped node instead returns `s` over its selected promises, so a repeated subtree bound once as a promise reaches every half below, and the plain tree stays a candidate | linear: 29 characters an internal node, four a leaf | poly n: only selected d-promises are forced; one path of n | linear: the program term, held in task and continuation frames |
| Unsquare | linear lookup | the table is one `O`/`I` push per row, reversed, and each read pops its bit's weight in cells off the top of it | linear: `2**n` cells and `2**n - 1` pops, two bytes a row | linear: worst 2T + 79n + 26 commands: T pushes, 76 per input read, weight pops | linear: worst T + 12 + bl(L) + bl(L-33) + 2bl(n) bits: T + 1 table cells on the stack |
| Vandevelo | minterms | an affine-cube peel emits one guard line per coset of an affine cover of the 1-set | open: O(T) lines and commands for every table, O(T log n) identifier text; the build costs at least T*(n - log2 k) with k zeros, and core work is only O(T*n) | linear: at most Q - G + 3C steps: Q ? reads, C comparisons, G guards' final loop? skipped | poly n: at most n * n registers; sqrt T below the cap |

<!-- PROOF-STATUS:END -->

## Exceptions and walls

- Befunge starts with an empty stack and a fixed 80x25 source grid. Each
  Python character has fewer than `2**21` possible values, so there are fewer
  than `2**42000` initial grids, including every padded shorter source. With
  stdin restricted to the input bits and randomness fixed, each grid computes
  at most one truth table at a given arity. Sixteen inputs have `2**65536`
  tables, so some have no program. Unbounded stack integers and self-modification
  do not change this source-count bound. For byte-only source the bound is
  `2**16000`, already excluding some fourteen-input tables. The shipped
  six-bit printable-ASCII lookup covers every table through thirteen inputs,
  meeting the byte-source arity bound. For row `r`, it reads cell `r//6`,
  subtracts 32 and divides by `2**(r%6)` before taking modulo two. The three
  binary digits of `u = r%6` build the divisor as
  `(1+u%2)*(1+3*((u//2)%2))*(1+15*(u//4))`, without a loop. Enlarging the torus
  or supplying the table as extra input changes the generator contract.

- Malbolge has 59,049 source cells and exactly eight valid decoded
  instructions at each occupied cell.  Including shorter programs gives fewer
  than `sum(8**k for k in range(59050)) < 2**177148` distinct programs, while
  the 18-input domain has `2**(2**18) = 2**262144` truth tables.  One program
  computes at most one table, so some 18-input tables have no Malbolge program;
  no generator can be total under this interpreter's language semantics.  The shipped
  construction reaches sixteen inputs, one below that wall:
  [malbolge-scaling](malbolge-scaling.md) measures why the hashed cascade stopped at
  fourteen (the depth a truth table forces climbs past any decoder pass count as the
  answer-cell load rises), gives the positional build that covers fifteen and sixteen with
  no collisions, and shows why seventeen is beyond any build spending a cell per row
  pair.  Whether some 17-input table has no program is open.

The former exception, `%^2^-1`, left with its language. Every row outside
these two exceptions is `Total`, or theoretically total past the resource
ceiling below.

### Resource-ceiling audit

The remaining `cap` rows do have a uniform lift argument.

- Polynomial's `k == n` candidate is the finite decision tree.  Each of its
  finitely many instructions receives a distinct prime root, and removing the
  interpreter-cost screen does not change that encoding.

Grapheme left this section when its tree did: the table is one int-mode
literal and the index is an accumulator, so no arity needs a second variable
and there is nothing left to run out of.  6-5 left when its walk stopped
spending a label per input.
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

Accordingly, this ledger records 74 theoretical totality arguments and two
proved language exceptions under the source-embedded contract.
Every other row is `Total` or theoretically total past a resource ceiling.

## Ordered reads without retained inputs

Call a layered construction input-forgetting when, just before each read,
its data store and pointer depend only on depth; the control location carries
the residual function. Ordered reads alone do not imply this property:
`,>,>,<<.` reaches one cursor with four stores after two reads. The shipped
BrainIf residual-DAG candidate does satisfy it. Its first input cell is zero;
before each later read, `if 48 increment` maps the prior Boolean byte to 49.
The one input then overwrites it. No earlier input remains in the store.

After `k` reads, distinct residual functions require distinct states: equal
states would execute identically on every common suffix. At depth `k` there
are at most `min(2**k, 2**(2**(n-k)))` distinct residuals. Intern equal pairs
bottom-up to attain this bound level by level, with one node per distinct
cofactor. No order search is needed; all pairs visited number below `T`.

The worst-case total node count is `Theta(T/n)`. Let `r` be maximal with
`2**r+r<=n`. For remaining depths through `r`, the double-exponential counts
sum to at most `2*2**(2**r) <= 2T/2**r`. Larger remaining depths have at
most `T/2**s` nodes and sum below `T/2**r`. Since `2**r>n/4` for `n>=4`,
the total is below `12T/n`. For a matching lower bound, at remaining depth
`r+1` assign every prefix a different zero-padded rank as its residual table.
There are `T/2**(r+1) >= T/(2n)` prefixes and enough different residuals
by maximality of `r`; every input-forgetting realization needs that width.

BrainIf emits four lines per DAG node, three at the root. Destinations have
`O(n)` digits, so the worst-case source is `O(T)`. Two shared output tails
add constant text. A run consumes exactly `n` inputs in order and executes
at most `4n+50` lines. The zero tail moves to a virgin cell only when the
last byte is 49, then builds 48; the one tail increments 48 if needed and
prints 49. All gotos go forward, so termination is structural.
Interning and writing the labels cost `O(T)` in the repository's
`Theta(n)`-bit table/index word model. This does not assert linear bit work.

The public generator keeps the shorter source against the tree/spatial
candidate; width requests retain that older route. Every three-input table
shrinks: total characters `319576 -> 292492` (8.47%), summed executed
lines `134984 -> 74752` (44.62%), with no table growing or slowing.
All 2,120 rows through three inputs execute; constants, parity and four
seeded tables per arity four through six also execute every row. A separate
200-table five-input sample gives `573675 -> 360230` characters and
`1501446 -> 280080` lines. Full-store boundary checks confirm erasure before
the next read. The controls are in `tests/proofs/test_research_tracks.py`.


## Vandevelo identifier and fallback audit

The construction bounds register upkeep by `O(T)` lines, but identifiers
cost `O(log n)` characters per occurrence. Command count is proved linear
below. The candidate charge in the generator's docstring fails on
near-full tables, and dual-basis core work lacks an aggregate bound. The
audit marks size `Measured`, keeping its regression gate without claiming
an asymptotic proof.

`scripts/profile_vandevelo.py` counts identifier characters, sampled
fallback calls, pair draws and the points each draw visits. A forced
six-input span-invariant control fires the fallback once: four draws of
12 points each. Its selected direction has exactly eight pairs, checked
directly. The default corpus executes 66 tables through six inputs and
2,772 rows across original and renamed programs; one fallback call draws
four times and visits 48 points.

The tested naming rule assigns the shortest existing names to the most
frequent identifiers, replacing tokens simultaneously. On `Random(0)`'s
12-input dense table, source shrinks from 32,269 to 31,942 characters
(1.01%); its 4,414 identifier occurrences occupy 5,273 characters before
renaming. Sixteen evenly spaced input rows, including both endpoints,
execute under both spellings and match the table. Reproduce with
`--min-inputs 12 --max-inputs 12 --random-cases 1 --sample-rows 16`.
The rule misses the 5% shipping threshold and retains growing identifier
lengths, so it remains an experiment. Neither gap is closed by this audit.

The clause bound holds for every table. Its proof needs one direction
per level holding half the pigeonhole average, on two chains: the first,
which sets the opening phase, and the certified one, which alone may drop
it. `_assure` checks that at every level of both. When no candidate
qualifies, it finds one in `O(|S| * (j + 1))` work. Bucket the coset
representatives by all but `a` free coordinates, with `2**a >= 2**(m+1)/q`
in a quotient of dimension `m` holding `q` cosets. Cauchy--Schwarz puts
`(2**a - 1)` times the threshold inside buckets, so about `2*q` pair
differences reach it by pigeonhole. Such a direction gives
quotient density `eps' >= eps**2/4`, so `log2(1/eps) + 2` at most doubles
a level, and the chain's cubes exceed `n/(2*(log2(1/eps) + 2))` points.
Over the density bands `(2**-(i+1), 2**-i]` that is under `16*2**n/n`
dense clauses; the sparse tail, below density `1/max(48, n)`, adds at most
`2**n/n`. On a corpus through n=13 `_assure` checked 1,712 levels and
never computed, so output is byte-identical. With candidates and the
sampled fallback disabled, it alone keeps n=8 and n=10 random tables under
`T/n` clauses (`tests/proofs/test_vandevelo_fallback.py`).

Commands per row are therefore linear. A halting row fails one part of
each guard, and every value is a strict boolean. So a register toggle
costs five commands, a part at most five, and an input read one. Upkeep
is at most the constraints' total weight, `4*n*C + 4*T` with `C` clauses,
and parts are at most `n*C`. With `C <= 17*2**n/n`, a row runs under
`25*n*C + 20*T + n + 1 = O(T)` commands, so the execution-time cell is
Linear. The affine, coset and complement paths emit at most `n` parts
in all.

Generation time is not linear as built. The sampled fallback scores
`_SAMPLES` uniform pair differences, `_SAMPLES * |S|` work, so it fits the
candidate charge. The charge itself fails: it bills a node's build to
its points once per level, which assumes chains of bounded depth. With
`k` zeros, level `l` of the first chain misses at most `k*2**l` points.
So it keeps two cosets for `n - log2(k) - 1` levels, and each build visits
all of `|S|`: at least `T*(n - log2(k) - 2)` work. Three and eight zeros
measure 845 to 1,090 `n*T` of scoring at n=10..15. Random tables of
density 0.1 to 0.9 stay flat, 13 to 4,500 `T`; so does a planted-cube
family, and quadratic forms reach 2,660 `T`. A linear build needs
near-full levels to cost their complement: `S & (S ^ v)` misses `Z | (Z ^
v)`, so a level's misses at most double while its points stay near `T`.

The dual-basis completion's other terms charge to the output. Column
extraction costs `n*dim` a clause and the echelon reduction at most `n` a
dual, while the clause's guard alone writes `n - dim` parts of `O(log n)`
characters. Cubes of dimension above `2*log2(n)` pay from their own
`2**dim` points. So these terms are linear in `T` plus the output, and the
character-level time gap coincides with the identifier gap. Measured on
seed 0, n=12..16: 2.0--2.5 `T` for columns and 0.75--0.91 `T` for
reduction.

The core build, `|core|**3/3` a clause, is the one term that charges to
neither. A core with no relation of weight four or less can hold all `n`
inputs: the extended-BCH columns `(1, x, x**3)` over GF(16) do, with
`dim = 9`. Half the cosets of that subspace at n=16 reach a 16-input core,
but the peel merges coset pairs into cubes of dimension 10--12. That gives
12 clauses and `0.13*T` core work. Any two cosets of a subspace form a
cube of one dimension more. Blocking that merge leaves a Sidon set of
cosets, too sparse to matter, and globally popular directions do not see
planted cubes. On random tables the greedy core stops at about
`(6*2**dim)**(1/3)` inputs: at most 6 to n=16, and a flat `0.43*T`. The
proved bound is still `O(T*n)`; no executed table exceeds a constant.

What linear text would take. While no guard part reads `Inp`, every value
is affine and a guard hangs on one coset. A coset of codimension `c` needs
`c` parts with independent values, so at least `c` distinct live names
and at least `c*(log65(c) - 1)` characters. `O(T)` text therefore needs
cubes of `Omega(n log n)` points on average. A random set of density 1/2
holds cosets only up to `2**d ~ (d+1)*(n-d)`, about `n*log2(n)` points
(first moment). So the cover must stay within a constant factor of the
largest coset, where the chain above finds `n/(4*log2(1/eps))`. That is
the greedy-versus-maximum gap of cliques in random graphs, and no
polynomial search is known to close it. The one way to repeat a name
within a line is a lazy `r -> Inp?`, which reads afresh on each access.
A guard that fails midway has then consumed a data-dependent prefix and
misaligns every later read. Alignment survives only if each row passes
at most one reading gate, and then each gate class gets one prefix
pattern. Neither route is a lower bound: no language-wide `Omega(T log
n)` is proved, and counting gives only `Omega(T)`.

Both routes meet an open problem. A guard is one term of a DNF of
parities, so the minimum term count is Cohen and Shinkar's `DNF+(f)`
([ECCC TR14-099](https://eccc.weizmann.ac.il/report/2014/099/)). They
prove `DNF+(f) <= O(2**n/n)` for every `f`, tight only up to `O(log n)`.
A random `f` has `2**n/(n*log n)` w.h.p., and no function is known to
need more. Take tables whose cubes have dimension at most
`2*log2(n) - 2*log2(log2(n))`. A term there costs about `n - k` distinct
names, about `log65(n)` characters each. The short-relation basis keeps
its upkeep at `O(n)` names from `O(n**2)` identifiers. So a coset program
costs `Theta(DNF+(f) * n * log n)` characters. Linear output for every
table therefore needs `DNF+ = O(2**n/(n log n))` for all `f`. A
super-linear lower bound on any such table needs `DNF+(f) = omega(2**n/(n
log n))`. Either one settles the open factor. Guards that read `Inp` only
add programs, so they make a lower bound harder, not easier. The size
cell stays `Measured`.

The open factor depends on one extremal function. Let `D(n, delta)` be
the least, over sets of density `delta`, of the largest affine flat
inside. Cohen and Shinkar's chain gives `D >= log2(n) - log2(log2(1/delta))
- 2`, and random sets give `D <= log2(n) + log2(log2(n)) + O(1)`. If
`D(n, 1/2) <= log2(n) + c`, that set's indicator needs `Omega(2**n/n)`
terms and their upper bound is tight. If `D(n, delta) >= log2(n) +
log2(log2(n)) - log2(log2(1/delta)) - O(1)` for every `delta`, the peel
gives `O(2**n/(n log n))` for every table. SAT data (Glucose, every affine
`d`-flat forbidden, `0` in the set) on the largest density with no
`d`-flat:

| n | `d=3` | `d=4` |
| --- | --- | --- |
| 4 | 11/16, exact | |
| 5 | 18/32, exact | |
| 6 | at least 29/64; 32/64 undecided at 300 s | |
| 7 | at least 44/128 | 64/128 reached |
| 8 | | 128/256 reached |

An independent recursive flat finder confirms the `n=7` and `n=8`
half-density sets have largest flat 3. It recovers a planted 3-flat and
gives 1 on the Sidon set `{0,2,3,4,8,13}`; the same SAT model at `d=2`
gives the known Sidon maxima 6, 7, 9 and 12 for n=4..7. So `D(7, 1/2) <=
3` and `D(8, 1/2) <= 3 = log2(8)`. Random half-density sets reach 4 in
six of ten draws at n=7 and in five of five at n=8. The algebraic set
`{x : Tr(1/x) = 1}` in GF(2**n) reaches 2, 3, 3, 4 and 4 at n=5..9, no
better than random. So at n=7 and 8 the extremal sets sit a dimension
below random, the side that would make `Omega(2**n/n)` the truth. These
sizes cannot separate `log n` from `log n + log log n`, and the SAT sets
(degree 6 and 7, no translation symmetry) suggest no family.

The lower side has better constants than the chain. Bastioni, Giannoni and
Lobillo-Olmedo (arXiv 2605.05455, section 6) count affine 2-planes by
Fourier, at least `(s**4/2**n - 3s**2 + 2s)/24`, and quotient by the most
popular 2-dimensional direction. Mixing that step with the chain's
one-dimensional step, from the Sidon base `s(s-1)/2 <= 2**n - 1`, forces
a 3-flat in every half-density set from n=7, a 4-flat from n=12, a 5-flat
from n=21 and a 6-flat from n=38. That is about `log2(n) + 0.2` against the
chain's `log2(n) - 2`, the same rate with a better constant. With the
SAT-exact bases above a 3-flat is forced from n=6. Since `D` cannot drop
as `n` grows (one hyperplane half keeps density `1/2`), this pins
`D(6, 1/2) = D(7, 1/2) = D(8, 1/2) = 3`. There the extremal value sits on
the density-increment bound, a dimension below random.

A Delsarte bound moves the 4-flat threshold to n=11. A Sidon set of
size `N` in `F_2^9` gives the even code of the columns `(1, a)`: dimension
at least `N - 10` and no words of weight 2 or 4. At `N = 32` an exact
rational dual certificate bounds such codes by 3,710,516.55, below
`2**22`, so every 32 points of `F_2^9` hold a 2-flat. A 1024-point set in
`F_2^11` has a difference `v` with `|S & (S+v)| >= 1024*1023/2047`, so at
least 512 (the count is even), which leaves 256 cosets in `F_2^10`. The same
step leaves 32 in `F_2^9`. That 2-flat lifts twice, so `D(11, 1/2) >= 4`.
`D(9, 1/2)` and `D(10, 1/2)` are 3 or 4. At n=9 four local searches
(Metropolis, steepest tabu, noise, clause weighting) all stall at 530 to
620 4-flats. Every linear group tried with at most 44 orbits admits no
invariant 256-point set without a 4-flat, 12 groups in all. Groups with
60 to 80 orbits, Frobenius among them, were undecided at the time
limit.
