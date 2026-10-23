# Boolean-generator coverage proofs

Construction summaries use `T = 2**n` table entries; logarithms have a
fixed base unless specified. Detailed derivations and research history are
archived in Git at `9c4d0b392:docs/proofs/`. Executable proof tests remain.

- Polynomial: <a id="polynomial-bound"></a> worst-case expanded integer-polynomial
  source is `Theta(T**2 / log T)`. Ordered input overwrites the register;
  maximal-width tables force `Omega(T/log T)` distinct positive real instruction
  roots even with repeated roots, arbitrary read counts, operand signs and
  unrecognized cofactors. Every multiple of their root product pays
  `Omega(r**2 log r)` coefficient digits for `r` distinct roots. An uncapped
  residual DAG has `O(T/log T)` states and at most six instructions per state;
  multiplying its factors gives the matching text upper bound. Product notation
  is outside this expanded-source model. The public 1934-instruction cap
  still refuses some tables.
  For worst-case minimum length `C_P(n)`, the limiting bracket for
  `C_P(n)*n/T**2` is `(13/4)*log10(2)` through `(325/8)*log10(2)`
  (0.978 through 12.23); the factor-12.5 gap and existence of the limit remain open.
  Corollary 3.4 (Logarithmic mass) of [coefficient-mass](https://github.com/bangyen/coefficient-mass/blob/v1/coefficient-mass.tex) supplies the mass bound.
  Lemma 2.1, Corollary 2.3 and Theorem 4.2 of [coefficient-mass-complex](https://github.com/bangyen/coefficient-mass/blob/v1/coefficient-mass-complex.tex) supply multisection and sign refinements.
  Proposition 2.1 of [coefficient-mass-attainment](https://github.com/bangyen/coefficient-mass/blob/v1/coefficient-mass-attainment.tex) gives the confluent attainment construction.
  With rendered length `L`, fixed libmpdec uncapped generation costs
  `Theta((T**2/log T)**log2(3))` word operations; within the direct-FNT range
  admitted by the public cap it is `Theta(T**2)`. Generated-family cold parsing
  has the conservative bit bound `O(L**2 + D**4 M(H + D log D))`, where
  `D` is degree, `H` coefficient bit length and `M` integer multiplication.
  Arbitrary-source parsing is deterministic polynomial time in source length
  `s`, except that an all-zero source with largest written exponent `E > 2s`
  returns `E` instructions in `O(E)` output work. Sparse parsing avoids a
  degree-sized list, uses gap splitting and exact integer/Gaussian-root recovery;
  nearest-plane recovery is unique when the lattice minimum exceeds
  `sqrt(16/3)*B` for a candidate norm bound `B`.
  The separate common-norm Gaussian-factor result assumes
  `a_j**2+c_j**2=R`, distinct prime powers `c_j=p_j**b_j`, `b_j>=2`, and
  `Q(y)=prod(y**2-2(a_j**2-c_j**2)*y+R**2)` over `K>=2` factors.
  Every nonzero integer multiple has at least `(K+3)/2` terms. Raw factors and
  scaled reciprocal or anti-reciprocal multiples have logarithmic coefficient
  mass at least `K**2*log(R)/16 >= K**2*log(K)/4`; arbitrary multiples remain
  conjectural, and general register roots need not share a norm.
  Controls: `src/esolangs/languages/polynomial/tests/test_boolean_polynomial.py`,
  its `tests/test_polynomial_negatives.py`, and
  `src/esolangs/languages/polynomial/tests/proof_polynomial.py`.
- FRACTRAN: <a id="fractran-bound"></a> worst-case Boolean source is `Theta(T)`.
  The counting floor is `T/log2(15)-O(1)` characters. A shared decision diagram
  stores `C=sum_d min(2**d, 2**(2**(n-d)))=O(T/log T)` states,
  at most `C+n+1` primes and `2C+n` fractions. Its first-match rule branches
  on an input prime; leaf fractions produce the answer and trailing fractions
  clear unread set inputs. Runs fire at most `n+1` fractions on
  `O(n log n)`-bit values. Distinct row addresses instead cost
  `Theta(T log T)` text; that is a construction bound, not a language bound.
  Indexed execution and literal scanning have different costs.
  Controls: `src/esolangs/languages/fractran/tests/proofs/test_fractran_bound.py`
  and `src/esolangs/languages/fractran/tests/proof_fractran.py`.
- Malbolge: <a id="malbolge-bound"></a> positional addressing reaches
  sixteen inputs at every arity, and seventeen remains open. Finite source space excludes some eighteen-input
  tables, so mathematical totality is impossible. The load law allows at most
  two final rows per answer cell; a one-cell-per-row-pair construction cannot
  cover seventeen in the 59,049-cell store. This is not a universal seventeen-input
  obstruction. Table-free memoized planning and one-pass fill are separate:
  fill is `Theta(T+59049)`, with exactly half a cell assignment per row in the
  positional build. Prefix sharing over the gadget groups makes the readout
  map `Theta(T)` at every arity, so generation is `Theta(T+59049)`.
  A native three-field capture control ran from reset over all 4,096 legal
  record-and-neighbor glyph combinations at one fixed record address: 59,049
  characters, 3,187 instruction cells and at most 3,607 steps. It preserved
  the record and neighbor; seven cases matched Python and C whole states,
  and an omitted-fold negative control failed. These scratch measurements
  do not establish an integrated generator. The seventeen-input prefix,
  native Boolean decoder placement and named source-symbol rules remain
  unverified; the shipped cap stays sixteen.
  Controls: `src/esolangs/languages/malbolge/tests/`; archived
  seventeen-input tools are available at `09ab2fad:scripts/malbolge17/`.

- Ascenic: <a id="ascenic-bound"></a> worst-case source is `Theta(T**2)`
  characters for both the language and generator. Arguments rise strictly
  and are unary, so `L` lines cost at least `L(L+1)/2` characters, and a
  size-`S` program is one of at most 20 opcodes per line over `L <= sqrt(2S)`
  lines with arguments forming a partition of at most `S` into distinct parts:
  `2**O(sqrt(S))` behaviours, so some table needs `S = Omega(T**2)`. Blank
  lines and spaces add no behaviours. The threshold scan has at most
  `2T + 6n + 6` lines with arguments below `4T + 16n + 4`, the matching
  upper bound. Controls: `src/esolangs/languages/ascenic/tests/`.

The ledger records coverage of every `2**n`-bit table for every finite `n`.
“Total” means mathematical coverage. Ignore explicit digit, instruction,
line, tape, route-width, work and generation-time guards when lifting them
leaves the construction unchanged; invalid tables are outside the domain.

The exhaustive `n <= 3` and sampled `n <= 10` sweeps in
`tests/generators/test_boolean_contract.py` seek counterexamples; they do not prove
the coverage arguments.

In `tests/proofs/`, fast-band `test_ledger.py` checks registry consistency,
and `test_schemes.py` checks lookup and parameterized rows (`tree` and
`minterms` have no per-row check). Deeper checks live in `tests/proofs/deep/`.
`all_generators.py` checks every construction: flipping each table row
changes the emitted program at the tested arities, and each construction
completes an arity ladder on both table shapes. This checks the counting half
of each scheme.

- A Painter Ant also has construction-specific proofs.
- ArrowQueue also has construction-specific proofs.
- Container also has construction-specific proofs.

`python -m tests.proofs.deep <band>` selects declared cost bands: `verify`
for the local gate, `ci` for the registry battery, `by-hand` for expensive
checks, and `all` for everything, as with `just proofs`. The justfile,
workflow and `scripts/verify/gate.py` select bands; `test_bands.py` requires each
file's declaration and enforces its stated budget, not a measured runtime.

Coverage does not bound source size: the schemes count nodes and entries,
so a total generator can still emit super-linear text.  `linearity.py` is the
separate, registry-wide scaling contract the project enforces.  It measures
characters per table entry past each generator's last route change and holds
every generator to it except those the scaling audit or this
document's `cap` and `exception` rows already exempt. Exceeding the bound is
evidence against linearity; passing it is not a
proof.

- Polynomial's block-incidence lemma forces
  `Omega(T/log T)` distinct real instruction-root values even when roots
  repeat, and the slack certificate prices every multiple of their distinct-root
  product, giving `Omega(T**2 / log T)` for every program, whatever its read
  count: only the last two reads before a routing position can carry a residual
  that depends on its next input and not on it alone.  The argument is in
  [summary](#polynomial-bound).

A `linear` row is within a constant of the worst-case optimum. A language with `c`
source characters has fewer than `c**(L+1)` programs of length at most `L`,
against `2**T` tables of length `T`, so some table needs
`L >= T / log2(c)` characters -- `T/3` for brainfuck's eight commands.
The `open` rows may exceed that floor.

- Polynomial at `Theta(T**2 / log T)` provably exceeds the counting floor.


- Fargo:
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
ceiling: super-linear growth there is an open scaling-audit cell for the linearity
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

**Size dispatch.** Some lookup rows ship a folded decision tree through a
fixed crossover (normally `n <= 4`) and a lookup above it. Each route is total
on its own domain; the lookup carries the universal claim, so the tree is a
size optimization rather than part of the proof. A width-constrained build
may take the tree at any arity.

- Container builds both routes at every arity and keeps the shorter; its
  workspace bound is counted from the program, so it covers either.
- BrainIf's tree counts only branched-on inputs. It also competes with its
  input-forgetting residual DAG, proved below.
- Streetcode builds both routes at five inputs and keeps the shorter, so its
  crossover is where the two meet rather than a constant.
- Suffolk competes with a NOR cofactor DAG within its workspace ledger.

- Befunge reads one grid cell per table entry with `g`.

These generators keep no unconstrained tree route and have no subtree to fold:

- A Painter Ant: Its answer strip is smaller than a tree at every arity.
  Its corridor stops at the trailing run of equal answers (36.4% saving).
  An ignored input costs a bare `SN` through `input_weights`.
- Alight: Indexes a string literal.
- B-tapemark: Copies one mark per row onto the blank grid and walks the pointer
  to it.
- bit~: Lands the pointer on one tape cell per entry and walks the bit home.
  Indexes the projected table it is handed.
- Bitwise Cyclic Tag: Has no branch to fold a tree into: commands run in a fixed
  cyclic sequence. Every table of a given arity whose inputs all matter emits
  the same length.
  An ignored input costs a bare `0` through `input_weights`.
- Circlefuck: Deletes entries before the indexed one and prints what remains
  under the pointer.
  Tabulates only essential inputs.
- Clockwise: Writes one cell per entry in a countdown row and stops on the
  indexed cell.
  An ignored input reads seven bits before the next input overwrites them.
- Collatz Multiverse: Writes one cell per four table rows at every arity.
  Degenerate tables with few distinct nibbles need fewer cell constants and a
  shorter decoder; the fold discriminator in `test_schemes.py` records this
  exception.
- Cyclic tag: Alternating table-bit and empty productions select the indexed
  answer.
  An ignored input costs an empty rule through `input_weights`.
- ///: Fixed substitution sweeps select the indexed table entry.
  An ignored input costs an `X`-deleted bit through `input_weights`.
- Subleq: A packed decoder selects the indexed table bit.
- Dimensional: Paints one cell per entry along dimension 1; a bare `>` displaces
  the pointer by the bit it stands on. Painting only as far as the last
  essential input makes a constant-zero tail cheaper (6.9% on the best
  one-dependency table), without a subtree.
- EGL: Paints one cell per entry and walks a pointer to it.
- Eval: Uses a linear lookup at every arity. Its lookup shrinks degenerate
  tables; the fold discriminator in `test_schemes.py` records this exception.
- Fish: Reads one grid cell per table entry with `g`.
  An ignored input is read and popped with `i~`.
- Flowchart: Pushes one deque entry per row and walks the cursor to it. Its tree
  is the width-constrained route.
  An ignored input skips its eight bits.
- Forbin: Paints a 128-entry block as one call’s argument list at every arity;
  branches above seven inputs choose a block rather than route a table.
  An ignored input is read into the scratch name through `input_weights`.
- Minsky Swap: Its `~` cascade routes the index to two shared leaves with a one-
  digit target per row.
  An ignored input costs a drained `~ ~` through `input_weights`.
- Modulous: Pushes the whole table as a string literal and spends the row index
  popping down to the answer.
- Packlang: Paints one array block and indexes it at every arity.
- Qoibl: Divides one literal by the power of two its reads build.
- SLOW ACV MAMMALIAN: Its read chain emits one fixed-width leaf slot per row
  whatever the table says.
- Sonata: Doubles a unary row index and strips one table entry per unit.
  `essential_inputs` halves degenerate tables; the fold discriminator in
  `test_schemes.py` records this exception.
- SwitchCase: A switch a hundred rows turns the row index into its row's bit.
  `essential_inputs` halves degenerate tables; the fold discriminator in
  `test_schemes.py` records this exception.
- Thue: Makes the table its starting state and rewrites every adjacent pair down
  to one per input.
- Unsquare: Pushes one stack cell per row and pops the row index off the top.
  Pushes only cells the essential inputs address.
  `essential_inputs` halves degenerate tables; the fold discriminator in
  `test_schemes.py` records this exception.

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
or time in the scaling audit); `lower bound: <bound>` (the language forces
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
can hide a generator's T-dependent work. The dense series runs to n=12; its
increments, which cancel fixed overhead, may grow at most x1.4 an input.
A `poly n` cell also names its mechanism, read from the generator. A cell
that opens `worst` gives a formula derived from the code and reached by some
table; `at most`, one never exceeded. `bl(x)` is the bit length of x, `L`
the program's length and `T` is 2^n. `tests/proofs/test_execution_formulas.py`
and `tests/proofs/test_workspace_formulas.py` run them at small n.

- Fargo's T-dependent work was hidden by parity.
- Forþ's T-dependent work was hidden by parity.
- INTERCAL's T-dependent work was hidden by parity.
- S*bleq's T-dependent work was hidden by parity.
- 6-5's T-dependent work was hidden by parity.
- SLOW ACV MAMMALIAN read x1.43 on the increments.
- Painfuck's `at most` formula is also proved for every n.

<!-- PROOF-STATUS:START -->

| Generator | Proof | Qualification | Scaling | Execution | Workspace |
| --- | --- | --- | --- | --- | --- |
| /// | parameterized lookup | binary-to-unary substitutions form the row index; T escaped sweeps consume indexed entries before decoding one answer and deleting the suffix | linear: worst 20T + n + 53 characters: T sweeps, 2T table | linear: worst 6T + n + 19 steps: rule parses, failed searches and substitutions | linear: worst 8L + 56 + 8max(0,T-15) bits: the program string, rewritten in place |
| 1 + i | tree | a node pushes its two children as function literals, reads its bit with `B` and `?` invokes one; constant subtables read their remaining bits unbranched | linear: worst 37T/4 - 10 characters past n = 1: ten a node | poly n: worst 6n + 5 steps: six a level, eleven to print 1 - b | poly n: worst W bits, n = 2..26: frame, stack and input position |
| 3x | tree | — | linear: at most K characters: the plain tree under fixed keys | linear: worst L commands: the all-ones row enters every guard, no loop repeats | linear: at most n·bl(L) + bl(2n-1) + 3G + 2n + 2K(N) + 6bl(N-1) + 9 + Σ_{i≤N}(K(i)+3) bits |
| 6-5 | finite lookup | past 35 inputs the positional walk loops on sixteen labels: each bit advances the pointer to the first row whose 2-adic valuation mark reads zero, and one pass per bit shifts the marks | linear, time n log: at most N characters: two raced orders over canonical subtree IDs | linear: worst L commands: loop-free, each token runs at most once; constant tables run every token | linear: worst 2T + 7n + 9 + bl(n) bits past n = 6: a tape of 2T cells |
| A Painter Ant | parameterized lookup | each embedded bit keeps the ant on a self-painting corridor or lifts it off, and the template walk after it advances the ant by that bit's weight, stopping at the corridor's end, leaving it over the indexed answer cell or the trailing run's first, which answers alike | linear: worst 9T + 3n - 6 characters: corridor weights sum to T | linear: worst 2L commands: one pass to the fixed point, one proving the repeat | T log T: worst 2(n+1)T + 4 + bl(L-1) bits: corridor, answers, ant, cursor |
| ABCDirection | linear lookup | the write row puts the essential inputs' table on the tape, one cell an entry, then each essential input's gadget tests its dequeued bit and a 0 walks the tape pointer left by that bit's weight, leaving it beside the indexed entry; an ignored input is read and never enqueued | linear: worst 10T+85n+40+10⌈d/3⌉+5max(0,8n+35-T) cells: five rows | linear: worst 5T + 97n + 150 + d + 6⌈d/3⌉ + max(0, 8n+35-T) commands: row 0 of AND | linear: at most T + 10n + 56 bits: the tape, one bit a cell |
| AddSubJump | finite lookup | packed `n`-bit cells selected by a self-modified operand | linear: worst P characters past n = 5, at most min(P, R) below | linear: worst (11n+4)⌊T/n⌋ + 11T + 13n - 17 past n = 5, one more from n = 10 | linear: at most Σ_{a<M} bl(a) + C(n + bl(B+13+C)) + 3n + 5bl(n) + Q bits: program cells, T/n packed |
| Algebraic Programming Language | tree | bounded shared frames; base-26 names are unbounded | linear: at most F characters: 10T + 4n + 6, n = 2..14 | linear: at most max(21,ceil(65n/2)-21)+K+2min(K,3n+1) commands: definitions initialize once and execute at most once | poly n: at most 179n+400+V+W if K=0, else A(198+8d+3b)+Q(b+114)+65n+d+bl(2n-1) bits: frame/global state |
| Alight | finite lookup | inputs folded into a row index by Horner's rule; the table is a string literal read with `at`, so the program has no branches | linear: worst T + 16n + 38 + digits(48(T-1)) characters: one literal | poly n: worst 2n + 5 commands, n Horner reads and one `at` | poly n: worst 72n + 762 + bl(6n+12) + bl(n) bits, n in 2..25 |
| ArrowQueue | parameterized lookup | one stage per input doubles the queued markers and adds the bit (Horner), and the count selects one of `2**n` constant-size cascade stages | linear: worst A cells: the least-area cascade or fold, T - 1 leaves | linear: at most 11T + 32n + 92 commands: Horner doubling 8 a marker, a row 1, fold corridors | linear: worst T + 11 + bl(T+6n+8) bits: a queue of T + 6 bits, the row, the column |
| Ascenic | tree | Horner's rule by built `-2` constants makes each row's code `base + 2r`; `LT t`, `ADDS` at every change point adds 1 to codes below `t`, so the parity answers; straight-line code, no jump | lower bound: worst N characters: generated Θ(T**2), N the alternating table's size ([summary](#ascenic-bound)) | linear: worst 2T + 7n + 3 - 2⌊n/2⌋ commands: alternating answers, two lines a change | poly n: worst bl(2T+6n+3+n mod 2) + max(bl(a)+bl(a+2)+n+1, bl((b+2T-2)(b+2T-1))) + bl(2n-1) bits: index, stack, cursor |
| B-tapemark | finite lookup | the blank grid is the table, one mark per row copied by `*`; a stage per input walks the mark pointer by that input's weight and `+` prints the mark it lands on | linear: worst A cells: the least-area of six closed-form layouts | linear: worst E steps: the all-zero row of the least-area layout | T log T: worst W bits to n = 8, at most B after: program cells, marks, pointers |
| Back | parameterized tree | an ignored input's run lands on the cell the next load fills, and a `-` after it leaves the cell empty | linear: worst F cells to n = 8, then at most: H-tree fold | linear: worst max(R,6n-1) + R + 3n + 6 commands to n = 6, then at most; R = 3T/4+1 | poly n: worst n + 5 + bl(max(6n-2,2^n-1)) + bl(3n+4) + bl(n) bits |
| Befunge | exception | six-bit ASCII lookup ships through thirteen inputs; finite source space excludes some sixteen-input tables | linear: worst N cells past n = 6: 80 columns, one header row | unmeasured: worst 5n + 28 steps to n=10, 5n + 67 to 13 | poly n: worst 2n + bl(5n+28) + bl(2n-1) + 10 bits to n = 10, then 2n + bl(2n-1) + 23 |
| BFStack | minterms | — | linear: worst N characters: zero-row walk telescopes to T | poly n: worst 73n + 371 + 13(n mod 2) commands past n = 7 | poly n: at most n + 7 + bl(n) + (d+1)bl(L) bits, d = max(n-7,0) + ⌊(3min(T,128)+1)/5⌋ + 2: brackets |
| Bitdeque | parameterized lookup | head/tail discards leave the indexed entry in the deque | linear: at most B characters: the shared tree's token bound | poly n: worst 7n + 8 commands past n = 2: prelude, load 2n, four a level, leaf n + 6 | poly n: worst n + 1 + bl(U) bits past n = 2: n deque bits, a register bit, the cursor |
| Bitwise Cyclic Tag | parameterized lookup | the table is the program, one four-bit cell per row; each embedded bit appends two walk zeros per unit of its place value, and a cell consumes exactly two, so the zeros carry the program pointer to the indexed cell and the held-back sentinel arrives there to fire it; the cell's second `0` consumes the answer it just appended, without which a 1 would cascade into the rows below | linear: worst 8T+2n+1 characters: four per row, reads four a unit | linear: worst 5T + n commands: input segments, then 3 per walk cell | linear: worst 16T + 8 + bl(8T+n-2) + bl(2T+n+1) bits: a data queue of 2T bits |
| bit~ | linear lookup | one tape cell an entry, and each input's one-shot loop jumps the pointer left by that input's weight, so the reads chain into a Horner index and a self-erasing walk carries the landed bit to one of two print windows | linear: worst 9T/2 + 18n + 75 characters past n = 2: minority | linear: worst 13T/2 + 17n + 93 commands past n = 2: the walk crosses the table once | linear: worst 2T + 49 + bl(2T+41) + bl(5T+18n+74) + bl(n) bits: 2T + 49 tape cells |
| Bleh | tree | a function a shared node matches its input's character; a folded node or constant reads it as a statement | linear: worst F characters, n = 3..9; at most beyond | poly n: worst 8n + 5 steps: a call, a read and a match a level | poly n: worst 64n + 306 + Σ_{0<a<n} bl(a) + bl(n) bits past n = 1: forced thunks, the print block |
| Blindfolded Arithmetic | linear lookup | the table read at its essential inputs is one integer built by Horner's rule in base 8, and each essential bit of the row divides it by 1 or by 2^2^m, squared up from 2, so its low bit is the answer | linear: worst 6T + 6⌈T/3⌉ + 60n + 53 characters: six an instruction | linear: worst T + ⌈T/3⌉ + 10n + 9 commands: all ones but the first row, run once | linear: worst 2T + 6 + bl(T+⌈T/3⌉+10n+6) bits past n = 2: b and its even copy |
| Boolfuck | tree | each input byte's low bit is read onto its own cell and tested in place by a flip-only decision tree, one flag interleaved beside each bit, consuming and emitting complete bytes; repeated residuals use level flags or normalized AND/XOR bodies, affine tables stream through one accumulator, and symmetric tables stream their bytes into a unary population count and decide from the count alone | linear: worst C characters to n = 7, then at most C | poly n: worst 4n^2 + 30n + 8 commands past n = 1: the all-ones row of a symmetric count table | poly n: at most bl(L-1) + max(12, bl(2n-3)+11) + n + Σ_{i<n} bl(i) + bl(2n) + bl(n) bits |
| brainfuck | tree | folded decision tree; residuals defer through level flags; affine tables stream | linear: at most 35T/2 + 55n + 25 characters: the plain tree | poly n: worst 69n + 44 commands, the AND table's all-ones row | poly n: worst 2n + 6 + bl(2n) + bl(n) + bl(L) bits |
| BrainIf | tree | equal cofactors share one layered DAG node, and an ignored input is read by the next layer's nodes; spatial lookup remains a candidate | linear: worst W characters: widest layered DAG | poly n: worst 4n + 50 commands, one DAG path and a tail | poly n: worst 13 + bl(lines) + bl(n) bits: two cells, a line cursor |
| Caballo | tree | the inputs are the initial stack; each node is the wiki's conditional, `d` dropping a 0 bit's branch and the zero test `(1+di-)` cancelling a 1 bit's, so one stack survives; equal halves pop untested and constant subtables fold | linear: worst 21T/2 - 14 characters past n = 1: subtree_ids folding | poly n: worst n(n+1)/2 + 14n - 2 commands: empty groups skip whole | poly n: at most (n+1)(n+2)/2 + 51n + 82 + bl(n) + (3n+3) bl(⌊2L/5⌋) + (n+1) bl(n+3) bits: nested frames |
| Circlefuck | linear lookup | the tape is the program, so the table is its tail past the `@` that stops the run, entry 0 abutting the index digits at the ring's end; `}` deletes the cell under the pointer and slides the digits down into it, so counting the index out against one `}` apiece leaves the entry it names under the pointer | linear: worst N characters: the table, 40n of reads, digit-cell walks | linear: worst (2n+13)T + 94n + 89 + 2S to n = 7, S the codes of program characters 1..n | linear: worst 6L + 12n + 7 + bl(L-1) + bl(L-T-2) + bl(n) bits: the program is the tape |
| Circuit Diagram | tree | complete residual folds or a strictly smaller emitted fallback | linear: at most F cells past n = 8: H-tree pool caps it | poly n: at most 2n + 1 commands: the longest gate path, reached to n = 20 | linear: at most 7T/2 + 2n - 5 bits, n ≤ 7; 7T + 2n - 9 after: latches, pulses |
| Clockwise | linear lookup | the ring is the table: one `!` per entry in a countdown row, and the index in the accumulator picks which one it is zero on, turning the pointer down that entry's own column; seven `.` an input build the index by Horner's rule, doubled between inputs by a two-row gadget that spends the accumulator as distance and buys back two per unit | linear: worst 30T + 48n + 24 cells: six rows, gadgets abreast | linear: worst 16T + 22n + 4 steps: the pointer's path to the last row | poly n: worst 57n + 53 + bl(5*2^n+8n+3) bits: 7n-character queue |
| Codesick | tree | each distinct subtable is one labelled node; it appends its marker to the unread bits, and a substring test for `0` before the marker reads the last bit, deleting it on a hit; a miss deletes `1` and the marker by a self-jump | linear: worst W characters, n = 2..36 | poly n: worst 3n + 1 steps: three a level, the leaf one | poly n: worst 16n + 8 + 8·digits(C+1) + bl(3C+1) bits: the input as key, the unread bits, the ip |
| Collatz Multiverse | finite lookup | an array subscript may name `lineNumber`, so a cell is addressed by the number of the line that writes it | linear: worst N characters past n = 2: one line per four rows | linear: worst T/4 + 3n + 4m + 2K + 10 lines: one step per line, no branching | T log T: worst end-state registers, arrays A and D, ip, input counter bits past n = 2: top code repeated |
| Container | finite lookup | the table is the prefix sum of its own steps, summed against a row counter that is live for one tick | linear: at most the threshold build on 0 0 (1 0)^(T/2-1) characters | poly n: worst 2n + 2 commands, either build | linear: at most Σ (8|name| + bl(peak)) bits over containers + 2bl(2n+2) + bl(EXIT): peak ≤ start + (2n+2)Σ⁺deltas |
| Crement | parameterized tree | each input is the data of one jump in a two-line tester; a node patches the tester's two targets to its children and jumps in, a folded subtree targets the shared self-jump or the line past the end, and a subtree already emitted at its level is targeted, not repeated | linear: worst N lines: subtree ids | poly n: worst 5n + 2 commands, shared self-patching testers | linear: at most 2bl(N) + 32 + bl(2n+3) + 2n(10+bl(N-1)) + P(28+3bl(2n+2)+2bl(N-2)) bits: whole program state |
| CV(N)(C) | tree | the halting goto squares once more whenever the program is not shorter than its reach, so every finite tree halts, and a subtree already emitted at its level is entered by climbing the accumulator to its syllable and `j`, where shorter | linear: at most 14T + 12 characters: 7T tokens of two | linear: at most 17 + 4n + (n-1)(3 + sqrt(2L)) tokens: the path plus shared-subtree climbs | poly n: worst 17 + bl(2n-1) + bl(L) bits, n in 4..13 |
| Cyclic tag | parameterized lookup | weighted zero padding advances the cyclic rule pointer to the indexed answer; the next empty rule deletes it | linear: worst 5T + 2n + 1 characters, weighted padding | linear: worst 2T + n + 1 steps: n input rules, 2 per row, 3 closers | linear: worst 16T + 1 + bl(2T+n) bits: a queue of up to 2T - 1 bits |
| Decleq | tree | the tree branches on every essential input down to single entries; an equal subtree is emitted once, and constant subtrees jump to one of two shared print gadgets | linear: at most B characters: six cells per distinct subtree | poly n: worst 50n + 2 commands past n = 1: 47 a chain, n - 2 copy jumps | linear: worst M + 5n + bl(C) + bl(n) + 1 bits, one more on a constant: memory and registers |
| Dig | tree | finite cell placement, the last six essential inputs left to a painted leaf table, an ignored input among or above them read and dropped | linear: worst A cells past n = 6: the dense table | linear: worst 128 + 46·2^((n-6)/2) for even n, 128 + 64·2^((n-7)/2) for odd, past n = 6 | linear: worst 8RC + bl(R-1) + bl(C-1) + bl(2n-1) + bl(n) + 10 bits past n = 4: the R×C grid |
| Dimensional | linear lookup | a bare `>` takes its dimension from the byte it stands on, so `d>` is a pointer displacement by the bit read: the index is a coordinate, doubled between reads by a two-loop `{`/`}` gadget, and it addresses one painted cell an entry along dimension 1 | linear: worst 2T + 20n + 58 characters: two per entry | linear: worst 11T + ⌊(2T+1)/5⌋ - 4n + 45 commands past n = 3: zero runs of nine loop | T log T: worst Σ_{k≤T} bl(k) + 5T + n(n-1)/2 + 4n + 11 + bl(2T+20n+56) + bl(2n-1) bits |
| EGL | finite lookup | row 1 is painted with the table and each essential input's `(-...)` guard walks the row-0 pointer right by that input's Horner weight, so `v=` prints the indexed cell | linear: worst 3T + 52n + digits(T) + 6 characters: painted row | linear: worst 3T + 52n + 3 commands: paint at most T-1 ones; weights sum to T-1 | linear: worst 2T + 2n + 7 + bl(L-d-3) + bl(L-d-9) + 2bl(n) bits, d the digits of T |
| Eval | linear lookup | fixed reversed stack order selects the indexed row | linear: worst 2T + 13n characters: T literal plus halving `;` runs | linear: worst 2T + 13n + 1 commands: one per program character, then the final frame pop | linear: worst 8L + T + n + 2 + bl(L) bits: frame program text and a stack |
| Fackward | tree | a level is a block whose quiet pass reads the bit; `/ c 49` makes it 0 or 1, that many `~` swap the two child blocks, `!` drops one and `)` runs the other; equal halves fold | linear: worst 45T/2 - 31 characters past n = 1: block per node | poly n: worst 40n - 28 steps: 40 a level, the last printing what it reads | linear: worst 159T - 225 + bl(n) bits past n = 1: the two stacks hold the program's tokens |
| FALSE | tree | — | linear: at most 9T/2+5n-7 characters past n = 3: to n = 15 | linear: at most 9T/2 + 5n - 7 commands past n = 3: expression text executed whole; diagram one path | poly n: at most W bits, b = bl(L), S stores: the build's stack, variables, frames |
| Fargo | tree | finite folded layout | linear: at most F characters past n = 1: inline Davio form | linear: at most 5T + 1 commands past n = 5, else 15T/2 - 4: each token runs once | linear: at most 16(L - 3) + bl(L) + 11 bits past n = 5: one frame's tokens, pending calls |
| Fish | finite lookup | the inputs form a Horner row index and `g` reads that column from the table row | linear: worst F cells: two rows to n = 3, then one row | poly n: worst 9n + 9 commands to n = 3, then 9n + 33 + 2c: Horner reads, one lookup | poly n: worst bl(9n+8) + n + 13 + bl(n) bits to n = 3, then bl(S-1)+bl(s)+bl(n)+71 |
| Flowchart | finite lookup | a pair of answers per deque, and the input walks the deque cursor to the pair it wants | linear: worst 28T+72n+38 cells past n = 1: two rows of 14T+36n+19 | linear: worst 3T + 9n + 3 nodes past n = 1: preload T plus T - 1 runs | T log T: worst F bits past n = 2: 7T + 18n + 5 exit-memory cells, the deques, the counters |
| Forbin | finite lookup | the last seven inputs paint a block of `2**7` table entries as one call's literal argument list, and each of them halves the callee's parameter window with one multi-assignment, so the first parameter ends up holding the addressed entry | linear: worst N characters, n = 2..134: two an entry, distinct nonconstant blocks | poly n: worst 2 max(n - 7, 0) + 2 commands | linear: worst 32n + 71 + 2bl(n) + G bits for n ≤ 48: main's locals in both frame and scope |
| Forþ | tree | the tree tests the essential inputs; an ignored one is read and dropped as `,0*+` | linear: at most S characters: scope counts per level, twins called | linear: at most 6T + 12n - 3 commands: every heap scope defined once, one dispatch path | T log T: at most (2n+364)T + 43n + 2bl(n) bits: frame text and the scope dictionary |
| FRACTRAN | parameterized tree | the bits are the exponents of `n` primes in the starting value, a decision tree gives equal subtables one state prime, and the first-match rule is the else-branch | linear: worst C = 2 + Σ_{d<n} min(2^d,2^2^(n-d)-2^2^(n-d-1)) states, O(log T) digits | poly n: worst n + 2: a step a level or unread set bit, the leaf, the halt | poly n: worst bl(p_{n+1+C}) + n + 2 + Σ_{i≤n} bl(p_{i+1}) bits, p_k the kth prime: all-ones start |
| Freestajlo | linear lookup | the table is one `"` literal, row 0 on top, and Horner's rule over the essential inputs gives the depth `&` copies; past the crossover the literal packs six entries a character and the row splits into that depth and a bit | linear: worst min(T + 4n + 1, ⌈T/6⌉ + 4n + 19) characters | poly n: worst 4n commands to n = 4, then 4n + 17: the literal, the reads and folds, the decode | linear: worst max(P, W) bits: the literal's codes on the stack, plain or packed |
| Grapheme | linear lookup | the whole table is one int-mode literal read in base 10, and each `W` squares an accumulator and doubles it on a 0, which is Horner's rule for the complemented index, so the accumulator is exactly the power of two that `R` shifts the wanted entry down to bit 0 | linear: worst 17n + 20 + digits(2^T) characters: one per read block | linear: worst 17n + 20 + d commands, d the digits of 2^T: one per program character | linear: worst 16d + 136n + 195 + bl(17n+d+5) + max(T+14, 2bl(λ)+2) + bl(2n) + bl(n) bits |
| Home Row | parameterized tree | — | linear: worst 27T/2 + 10n + 6 characters past n = 1: runs | linear: worst 10T + 10n + 88 commands: every guarded leaf run, one equal pair of rows | poly n: worst n + 32 + bl(27T/2+10n+6) bits: index cell and cursor |
| Hot | tree | the table is a tree of Church pairs, equal halves folded to `K`, applied to the bits that one fixed reader stage an input takes from `A` | linear: worst 27T/2 + 73n + 86 characters past n = 1: pairs | poly n: worst 35n + 45 rewrites: a pair a level, then the answer stage | linear: worst max(88T+232n+235, 132T+24n-53) + bl(n) bits past n = 1: two copies early, three at the end |
| Inject | finite lookup | one table block halved by `O(n)` conditional substitutions | linear: worst C characters past n = 4: every n | poly n: worst 8n + 10 commands past n = 4, halving per level | linear: worst 24T + 516n + 169 + A bits for n = 5..16: the program text after n reads |
| INTERCAL | parameterized tree | equal-width constants set each input once; fully grouped mingle, unary logic, and select expressions form a Shannon tree | linear: worst U characters for n = 3..12, at most V after | linear: worst 2n + M statements for n = 5..25, at most it elsewhere: shared nodes | linear: worst 9S - 18 + Σ_{k≤S-2} bl(k) + bl(S) bits for n = 1..25, at most it elsewhere |
| Interprogck8 | tree | a read's 1 arm hops to the far child, short inside a cluster and above it a flight at its own column sharing each window's rung; its 0 arm falls through | linear: at most 226T + 224 characters: 126-line windows, at most T/2 opened | linear: at most R + 11n commands: each line runs once, a called body adds 11 | poly n: at most bl(R) + bl(2n) + 543 bits: accumulator, line cursor, input cursor, slot and frame bodies |
| Kiss | tree | a node is S over its two halves, which S reads a bit to choose; a node whose halves agree reads it through SS(SKK) | linear: worst 7T-5 characters: 5 a node, 2 a leaf | poly n: worst 4n - 1 rewrites: four a skip level, then a read, the output and the halt | linear: worst 24T + 2bl(n) + 17 bits past n = 1: a root skip holds its half twice |
| LaserFuck | finite lookup | weighted arms select one of `2**n` prewritten cells, cleaned in one sweep | linear: worst N cells: a tree to n = 6, then three rows | linear: worst T + 296n + 682 steps for n = 5, 6, then 18T + 56n + 4 | linear: worst 8n + 26 bits at n = 5, 6, then 12T + 2n + 11 + 2bl(n) |
| Line | tree | finite decision trees preserve totality; complete ordered residual folds share every state unless their exact pixel area exceeds the fallback | linear: worst F pixels past n = 5: the full tree's box | poly n: worst 5n commands; complete folds retain this bound | poly n: worst n + 1 + bl(3n-2) + bl(n-1) + bl(2n-1) + Σ_{c<n} (max(1,bl(c)) + 1) bits past n = 4 |
| Malbolge | exception | finite source space rules out some 18-input tables; the shipped build folds the first n - 1 inputs into a positional address, three input bits per two-trit digit, so no row collides, and the answer stub reads the last; below sixteen the unused reads are held at 0; the cap is sixteen, and seventeen is open ([summary](#malbolge-bound)) | measured: worst 59049 characters: the fixed 3^10-cell store, every n <= 16 | unmeasured: worst 6,208 commands at n=1 to 5,686 at n=16: main code through its closing i, then the longest stub, 199 | poly n: at most B + E + 10(P+199) + 49 + bl(n) bits: a bit a step, ten a write |
| Minifuck | parameterized construction | affine or two-residual byte accumulator; budgeted stored residuals; total positional `_mux` fallback | linear: worst 81T/2 + 59 - n characters, n = 3..12 | linear: worst 71T/2 + 50 - n commands to n = 12, at most after: the positional strip | linear: worst 6T + 14 + bl(6T+12) + bl(6T+14) + bl(L) bits past n = 4: a tape bit-integer |
| Minsky Swap | parameterized lookup | every input is one `++`/`**` run; a stage per input adds its weight to the index register, and a `~` cascade routes the index to one of two shared leaves at the head of the program, so every table of one arity whose inputs all matter renders to the same length (an ignored input's stage is a bare `~ ~`) | linear: worst N characters: cascade routes to two shared leaves, one-digit targets | linear: worst 2T + 6n + 4 commands: a unary index add, then the ~ chain down | poly n: worst n + 3 + bl(2^(n+1)+6n+5) bits: two registers and cursor |
| Modulous | linear lookup | the table is one `PSH STR` literal, pushed so that row 0 lands on top, and the inputs add their weights into the counter of how many characters to discard | linear: worst N characters: T-character literal, one read block an input | linear: worst 5T + 5n + 1 commands: a zero push, n reads, then 5 per entry discarded | linear: worst 6T + n + 2 + bl(6n+5) + bl(2n-1) + bl(n) bits: table codes on the stack |
| Object disoriented | tree | a node keeps its input bit in `t` and its negation in `a`, via an object that is a 1 until a 1 bit calls it; each bit object calls its branch only on a 1; constant subtables fold, and a repeated branch is a class written once | linear: worst D characters to n = 8, at most min(38T+20, S) | poly n: worst 67n + 34 commands: one tree path, 67 ops a level | poly n: at most F + M + bl(6n+9) + bl(n) + 14 bits, c code ids, 2n+3 frames |
| Packlang | linear lookup | one 128-row array block, painted inside the `If` that selects it | linear: at most N characters: one write per differing row | linear: worst 19T/2 - n - 4 steps for n = 2..7, then 3T/64 + 1206 - n | poly n: at most min(T,128) + 2n + min(n,7) + 192 + 16[n>7] + bl(L) + 2bl(n) bits: one frame, array |
| Painfuck | tree | decision tree emitted directly in Painfuck's own commands; numeric I/O pays no ASCII offset, and `d` resets the pointer to the answer cell | linear: at most 31T/2+3n-21 characters past n = 3: to n = 15 | poly n: worst 4n^2 + 9n + 5 - 6⌊n/2⌋ commands past n = 2: parity sum's loops; trees ≤ 22n | poly n: at most 2n + 5 + 3bl(n) + (n+1)bl(L) bits: 2n + 2 cells, loop stack ≤ n |
| Piet | finite lookup | each table entry is pushed and an input index selects its output; literal products replace conjunction tables | linear: worst F codels to n = 7, then at most F | linear: worst F steps to n = 7, then at most 5T + 11n + 31: blocks plus turns | linear: worst F bits to n = 7, then at most S: the stack |
| Pointless | tree | each distinct subtable is one function, pasted in where that is shorter; `,=` maps a character to its bit through the cells 48 and 49, and `[` tests the bit's cell; the one `!` seeds the 1s that make `+` an increment | linear: at most F characters: every function declared | poly n: worst 26n + 309 steps past n = 2: setup 6n + 305, 16 a level | poly n: at most (n+1)(2bl(L)+4) + 16n + 430 bits: a frame a level, the tape |
| Polynomial | tree, cap | each finite instruction list has a finite prime-product encoding; every program for a maximal-width table needs Omega(T/log T) distinct real roots ([summary](#polynomial-bound)) | lower bound: coefficient mass is Omega(T**2 / log T), matching the uncapped residual-DAG construction; equal-root blocks force Omega(T/log T) distinct real roots and the slack certificate prices every multiple ([summary](#polynomial-bound)) | unmeasured: at most C commands: ifs only jump forward; a chained level runs 2(s - 1) + 6 | poly n: at most bl(A + 10) + 1 + max(bl(n+3), bl(49(M-1))) + 2bl(n) bits |
| Qoibl | linear lookup | the table is one binary literal, divided by the power of two the reads build | linear: worst T+64n+64 characters: T-1 bit literal, 64 an input | poly n: worst n + 2 commands, one statement per input | linear: worst T + 3 + bl(n) + bl(n+2) bits: variables 0 and 1 |
| Quassaunt | tree | each distinct subtable's code is stored once in a global and run by name; a node tests its character's set {2, c} against {1} with `%%Ifpropersubset`; equal halves and constant chains read their bits unbranched | linear: worst F characters, n = 3..10; at most beyond | linear: worst 5N + 21n + 9 steps: five a stored node, 21 a level | linear: worst 16L - 328D - 8r + 32w + bl(5D+6) + bl(n) + 2490 bits: frames, globals; stack two bodies |
| RAM0 | parameterized tree | the inputs are stored once and each node loads its bit with `L`; a subtree already emitted is reached by `goto`, so only the distinct subtables are laid out, and the straight-line lookup is kept as a candidate | linear: at most C characters: tokens per distinct subtable | poly n: worst n^2 + 8n + 5 commands, one root-to-leaf path | poly n: worst n + bl(S) + 2max(1,bl(n-1)) + Σ_{a<n} max(1,bl(a)) bits, S the token count |
| ROTfuck | finite lookup | every loop's cycle is 0 (mod 8), so its exit rotation is the same whatever its trip count | linear: worst P characters, n = 2..10: a lone zero | linear: worst 8T² + 43T + 15n - 5 commands for n = 2..6: a lone zero second to last | linear: worst W bits to n = 6, at most V after: 2T + 7 cells |
| Rubic | tree | every subtree undoes its `r2` store, so the cube is one of two states and each table expression is checked on both; equal halves read untested and constant subtables fold | linear: worst 155T/2 - 57 characters: parity, no node folds; subtree_ids folding | poly n: worst ⌊39n/2⌋ + 7 commands: a differing node runs 19 or 20, alternating | poly n: worst 3n² + 18n + 118 + bl(n) bits past n = 1: loop frames, the cube's 108 |
| S*bleq | finite lookup | packed chunks decoded after the hoisted read block, against a hoisted tree that lays out each distinct subtable once and jumps to it | linear: worst P characters, n = 11..25; below, at most min(tree, P) | linear: worst 3n + 2 instructions to n = 9, the tree route: n reads, 2n - 1 tests | linear: at most B + 6n + bl(3C) + bl(n) + 1 bits: the self-modified program, decimal cells |
| SendStuff | tree | each distinct subtable is one named node reached by reference; an Input node sends a 1 through `Subtract 49` and a 0 through `Divide 48`, `Subtract 1`; equal halves and constant chains read their bits unbranched | linear: at most C characters: one definition a distinct subtable, longest ids | poly n: worst 4n + 2 steps: four sends a level, root and leaf one each | poly n: worst 10n + 12 + bl(n) + Σ_{d<n} bl(N_d) bits past n = 2, N_d by V_j: pending frames |
| SLOW ACV MAMMALIAN | linear lookup | a read chain banks each bit on array 16 and the dispatch's `DIGEST LEAPFROG` reads that sum as the leaf address; the five lightest weights are CONSUMEd from planted cells, so they never read the sum and need not be multiples of 256, which puts the stride at an eight-token leaf | linear: at most V characters | linear: at most E commands | linear: at most B bits |
| Smallfuck | parameterized tree | each level owns a bit, branch flag, and result cell; a child transfers its result three cells upward, so the depth-first pointer walk crosses each tree edge only a constant number of times | linear: at most Q characters: the shorter plain tree, bands 3 or 5 | poly n: at most 9n^2 + 100n + 20 commands, one tree path | linear: worst L + bl(L) + bl(3n) bits: one tape bit per source character |
| Smu | tree | a node stores its halves under the input bit's own names and pushes the one the bit names as the next run's program, above seven skip runs for the byte's other bits; a node with equal halves is a pad; five macros carry the repeated text, and a subtree two parents reach is one more when that is shorter | linear: worst C characters to n = 16, at most 6T+90 after | poly n: worst 55n + 5 commands, one tree path of eight runs a level | linear: worst 24E - 1214 + bl(E) + bl(n) bits for n ≥ 2: code, stack, variables |
| Sonata | finite lookup | the essential input bits double a unary row index in one rewrite each, and each index unit strips one entry of the table read at them | linear: worst T + 4n + 101 characters: projected table plus reads | linear: worst T + n + 3 steps: a doubling an input, a strip a row | linear: worst 16T + 10 bits: the string at its longest, an index of T - 1 units beside the table |
| SStack | tree | each input byte is compared with stacked '1' and '0', then popped before descent; the empty test stack ends both one-shot loops; a constant subtree reads its remaining inputs and prints; repeated residuals use guarded labels | linear: at most 24T-9 characters: 21 a node, 3 a leaf, 12 prologue | poly n: at most 7n + 3 commands, six a tree node plus guarded dispatch | poly n: worst 6n + 12 + bl(K) + bl(n) bits, K commands: n stacked input bytes |
| Stisp | parameterized tree | the inputs are atoms in n frames, and an equation per edge of the reduced diagram rewrites the head node | linear: worst F characters, n = 3..10; at most beyond | poly n: worst n rewrites: one frame an input | poly n: worst 16n + 8z bits, z the decimal digits of D + 1: the frames and the node atom |
| Streetcode | linear lookup | the street writes one cell per entry, then each essential input's mouth forks on its bit (an ignored one is a lone read) and its side room walks the cell pointer left by that bit's weight, leaving the car over the indexed entry | linear: worst S cells from n = 2: tree, then the flat street | linear: worst 290n + 312 + H + W steps from n = 2 for an H×W tree, else F | T log T: at most nT + 2n + 25 + bl(2T+57+G) + 2bl(n) bits past n = 5, G = Σ_{0<k<n} max(51,2^(k-1)+3) |
| Subleq | finite lookup | shared direct-jump residual DAG or packed decoder with interned chunk payloads | linear: worst min(P, H) characters at n = 9..14, at most elsewhere | linear: worst 8T+(7n+5)(⌊T/n⌋-1)+23n-8 steps past n = 8: the packed decoder | linear: worst I + R + P + bl(n) bits: image, rewritten cells, pc, cursor |
| Suffolk | linear lookup | workspace-limited NOR cofactors share computed values; otherwise a countdown counts rising and falling steps to recover the indexed entry | linear: worst F characters, n >= 4 | linear: worst L + R commands, R the prefix through the first read: one pass, then EOF | poly n: worst bl(L-1) + max(6,n-1) + max(19,4n-1) + bl(n) + 4 bits: bounded NOR cells or eight countdown cells |
| Super SNUSP | tree | each folding pass removes at least one pending unit | linear: worst 2T + 19n + 21 cells: one row, "*" an entry | linear: worst 2T + 19n + 21 commands past n = 4: one straight line, all ones but one row | linear: worst T + 2n + 12 + bl(L) + bl(n) bits past n = 4: the packed-table cell |
| SwitchCase | finite lookup | loops build the row index from the essential inputs, and a switch a hundred rows turns its own rows' index into the bit | linear: worst N characters: one arm a row, jump loops an input | linear: worst 8T + 4⌈T/100⌉ + 7n steps: the index loops, four a block | poly n: worst 2n + bl(7n - 4) + bl(n) + 46 bits past n = 2: the last doubling loop |
| Taglate | tree | — | linear: worst 20·4^⌈n/2⌉+14⌈n/2⌉²+40⌈n/2⌉-5 characters past n = 2: fixed slots | linear: worst 16T + (7n^2+26n-22)/2 for even n > 2, 28T + (7m^2+22m-36)/2 for odd, m = n + 1 | linear: worst 24·2^m + 12m + 12 + bl(m) + bl(L-4·2^m-7m+1) bits, m = n rounded up to even |
| thisthat | tree | inputs go to either end of one bistack row, an ignored one to the column; each end pop drives the next alternating-axis decision node, or goes to the column where the halves agree, in an order the row can pop | linear: worst N cells past n = 2: an H-tree of `O(sqrt(T))` sides | linear: worst 32·2^(n/2) - 29 for even n, 48·2^((n-1)/2) - 29 for odd, past n = 2: about sqrt T | poly n: worst 4n + 89 + 2bl(n) + Σ_{c<n} max(1,bl(c)) bits past n = 2 |
| Thue | linear lookup | the table is the starting state, one character an entry, and the bit read rewrites every adjacent pair to one of its two members, so the state halves per essential input and the last character is the answer; an ignored input's round reads its line and deletes it; the rules never overlap, so the language's random rule choice has nothing to choose | linear: worst T + 187 characters: the plain layout and the table | linear: worst 2T + 3n - 2 rewrites: n rounds, each a marker sweep out and back | linear: worst 8T + 24 + bl(2n) bits: the T + 3 character state string |
| Unary | tree, cap | complemented-byte decision tree; constants, projections and conjunction guards avoid flags | lower bound: worst source length at least 2**T - 1; zero-count encoding | unmeasured: worst max(n, min(n + 4, 8)) commands past n = 2: at most nine commands, the last ] never run | poly n: worst W bits past n = 1: the programs of at most nine commands |
| Underload | parameterized tree | equal-width input programs leave one selector apiece; each node stores both branches as strings and the selector evaluates exactly one, while a constant leaf discards the unused selectors; a repeated subtree is pushed once and carried above the next selector, and the plain tree stays a candidate | linear: at most F characters past n = 3: 241 a five-input half | poly n: worst 12n + 3 + 2⌊(n-1)/2⌋ commands past n = 2: n slots, 11 a level, carries | linear: at most 24L + 120T + 32n - 176 + bl(2L+10T+6n-14) bits: spliced program, stack |
| Unlambda | tree | each half is a `d` promise, forced by the `?` test that selects it, since an argument spelled inline would be evaluated before the application; the shipped node instead returns `s` over its selected promises, so a repeated subtree bound once as a promise reaches every half below, and the plain tree stays a candidate | linear: at most 169T/8 - 21 characters past n = 3: 315-character halves | poly n: at most max(77n + 12, 84n - 9) steps: 77 a split level, 7 a bound node | T log T: at most 16(P + n·S) + (3n+9)bl(3n+9) + 9 + bl(n) bits: a copy of the shared subterm per read |
| Unsquare | linear lookup | the table is one `O`/`I` push per row, reversed, and each read pops its bit's weight in cells off the top of it | linear: worst 2T + 10n + 26 characters: two a row | linear: worst 4T + 79n + 22 commands past n=5: 12- or 14-cell loops, 76 per read, weight pops | linear: worst T + 12 + bl(L) + bl(max(0,L-33)) + 2bl(n) bits: T + 1 table cells on the stack |
| What!? | linear lookup | Horner's rule reads each bit with `??` and doubles by `*`; the index counts down one `-` a row, so at change point `b` it wraps above `2^k` exactly when the row is below `b`, and `[2^k>` writes the answer slot; past 15 inputs `???` puts the high bits in the index slot's string, and a guard per `2^15`-row block reloads the index | linear: worst S characters: a change point costs 12 and a dash | linear: worst E commands: alternating answers, every conditional true, the last row | poly n: worst 256 + k(k-1) + max(20, 2k-2+[n>15]) + 8(n-k) + bl(tokens) + bl(2k+1) + bl(2n-1) bits: the 256-slot tape |

Symbols the formula cells use:

- **1 + i:** W = 51, 61, 64, 70 at n = 2..5; 3n+52+bl(2n-1) to 13; 3n+48+bl(n+2)+bl(2n-1) to 24; 5n-1+bl(n+5)+bl(2n-1) from 25.
- **3x:** K(i) = bits of the ith key's value, exact; G = the program's ( count; N = 1 + n + C + min(G, ⌊T/24⌋), C half the complement snippets.
- **ABCDirection:** d = (2n + 4) mod 5, the rows the read block drops.
- **AddSubJump:** C = ⌈T/n⌉, I = 5n + 54, B = 4I, M = B + 14 + 2C; Q = I·bl(B) + (3I-2)bl(B+13) + 2bl(M-1) + bl(20n+212) + 23.
- **Algebraic Programming Language:** K = shared uppercase definitions, excluding NOT; A = 4n+3, active split and NOT frames; Q = 6n+5, pending nodes across frames; b = bl(2L+2), serial widths for AST nodes and functions; d = bl(L), bounding function-name length and the line cursor; V = Σ_{1≤j≤n-2} (bl(s) + bl(s+1) + bl(s+5)), s = 2n+8+7j, three serials per level; W = bl(2n-1) + bl(2n+3) + bl(2n+13) + bl(F) + 2bl(F+1) + bl(F+2) + bl(F+4), F = 2n+7.
- **Ascenic:** a = 8n - 7 + 2(n mod 2), the last Horner push; b = a + 6.
- **B-tapemark:** B = 8 + coordinate bits per program cell, plus a widest-coordinate mark per * or - cell.
- **Bitdeque:** U = 4n + 25 + Σ_{d<n-1} (2c_d + 2min(c_d, 2c_d - c_{d+1})), c_d = min(2^d, 2^(2^(n-d)) - 2).
- **Codesick:** C = Σ_{d<n} min(2^d, 2^2^(n-d) - 2), the most non-constant nodes; digits counts decimal digits.
- **Collatz Multiverse:** m = min(16, T/4), the distinct four-row cells; K = the constants closure: 29 for n = 6..8, 2n + 13 past n = 8; A = the cell array, an (index, value) pair per entry; D = the decoder array, one entry per set bit of the m cells.
- **Crement:** P = Σ_{k<n} min(2^k, 4^s - 2^s), s = 2^(n-k-1), the shared nodes per level; N = 3P + 2n + 3.
- **Decleq:** M = bits of the program's cells; C = cell count.
- **FALSE:** W = bl(n)+6n+2b constant, 5n-2+2b expression, n+1+2b(S+n+2) diagram.
- **Fish:** c = 3 to n = 20, then 1 + 2bl(column): the packed column literal's characters; S = 9n + 33 + 2c commands run; s = the packed column, 15⌈(9n+39)/15⌉ to n = 20.
- **Flowchart:** F = Σ over exit-memory cells of 4 + bl(column), plus deque keys and counters.
- **Forbin:** G = max(bl(h+1) + 4, max_{j<h} bl(j+1) + max(1, bl(h-1-j)) + 10), h = max(n-7, 0), the loop cursor.
- **Freestajlo:** P = 6t + 7 + bl(t+2) + bl(2n+2m) + bl(2n), m = min(n, 4), t = 2^m; W = 7⌊T/6⌋ + 7 + bl(⌈T/6⌉+4) + max(16, 2n+3) + bl(4n+18) + bl(2n), 0 below n = 5.
- **Grapheme:** λ = the largest lift of d + 1 digits, d those of 2^T.
- **Inject:** A = bl(12n+10) + bl(2n) + bl(n) + Σ_{i≤n+2}(bl(3i) + bl(3i+2)) + Σ_{2n+5≤m≤6n+4} bl(m).
- **INTERCAL:** S = the Execution bound; M = min(T/8+2, T/16+14, T/32+254) to n = 21, T/64+2^16-2 after.
- **Interprogck8:** R = the program's lines.
- **Malbolge:** B = the source's bits; E = the Execution bound; P = the `*` and `p` cells before the main code's closing i.
- **Object disoriented:** c = 3 + the `n` and `d` letters; F = Σ_{j<2n+3} (bl(c) + p_j + 3(bl(6⌈j/2⌉+9)+1)) + 4bl(6n+9) + 5; p_j = 4 even j, else bl(16n+40); M = (n+1)(3bl(c)+6) + 6n + 9.
- **Piet:** S = T + 2n + 12 + 2bl(3T+5n+15) + bl(2n-1) + bl(n).
- **Polynomial:** A = min(10T - 7, 3 + 6(Σ_{k<n} s_k - 1) + 6s_n, 1934), s_k = min(2^k, 2^(2^(n-k))); M = max_k s_k; C = min(A, 6n + 3 + 2Σ_{k=1}^{n} (s_k - 1)).
- **Quassaunt:** N = Σ_h min(2^(n-h), 2^2^h), the most distinct subtables; D = the program's definitions; r = the root name's length; w = the longest name, max(digits(D+1), 1+digits(n)).
- **ROTfuck:** W = 2T + n + 8 + bl(2T+6) + bl(L) + bl(E) + bl(n), E the execution worst; V = 2T + 5n + 35 + bl(2080L) + bl(2T+6) + bl(L) + bl(n).
- **S*bleq:** B = the program cells' bits, a sign one more; C = the program's cell count.
- **SendStuff:** N_d = 1 + Σ_{j>d} V_j + V_d - 4, the node index of the last depth-d Input; V_j = 4b + min(2^j - b, 2^(s/2)), b = min(2^j, 2^s - 2^(s/2)), s = 2^(n-j).
- **SLOW ACV MAMMALIAN:** E = first jump, prologue, per-level prefix, node and arm, tail: each list at its residue maximum; B = 8 bits a cell on arrays 0 and 16, pool zeros, heads, counters.
- **Smu:** E = 95T - 80, the macro-expanded program with no constant subtree.
- **Stisp:** D = Σ_{k<n} min(2^k, 2^(2^(n-k)) - 2), the most nonconstant nodes.
- **Streetcode:** F = 3T + 110n + 106 to n = 7, then 4T + 14n + 650: the flat street.
- **Subleq:** I = the program's cell bits: bl(|v|) plus one per zero or negative cell; R = 6n + 5 on a tree, 4 on a constant; packed, its worst read, advance or halving row; P = the pc: bl(Q-3) on a tree, bl(Q) on a constant, bl(D-3) packed; Q cells, D decoder cells.
- **Unary:** W = max t + bl(n) + bl(n+k): (k,t) = (0,8) (2,8) (3,8) (4,10) (5,17), n+k ≤ 9.
- **Unlambda:** P = the program's leaves, each k and s counted twice; S = the same count for its largest X in an @-node's `N`dX.
- **What!?:** k = min(n, 15), the low inputs a Horner loop reads; E = 6T + 6n + 5 to n = 15, else 2T + 2^17 + n + 143; tokens = 6T + 6n + 5 to n = 15, else 6T + 9·2^(n-15) + n + 134.

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
  [summary](#malbolge-bound) gives the positional build that covers every
  arity with no collisions and shows why seventeen is beyond any build
  spending a cell per row pair.  Whether some 17-input table has no program
  is open.

The former exception, `%^2^-1`, left with its language. Every row outside
these exceptions is `Total`, or theoretically total past the resource
ceiling below.

### Resource-ceiling audit

The remaining `cap` rows do have a uniform lift argument.

- Unary's complemented-byte tree is finite at every arity. Removing the
  raw, work and gzip screens and their nine-input consequence permits every encoding.
- Polynomial's `k == n` candidate is the finite decision tree.  Each of its
  finitely many instructions receives a distinct prime root, and removing the
  interpreter-cost screen does not change that encoding.

### Retired resource ceilings

- Grapheme left this section when its tree did: the table is one int-mode
  literal and the index is an accumulator, so no arity needs a second variable
  and there is nothing left to run out of.

- 6-5 left when its walk stopped
  spending a label per input.
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

<!-- PROOF-TOTALS:START -->

Accordingly, this ledger records 90 theoretical totality arguments and
two exceptions under the source-embedded contract.

<!-- PROOF-TOTALS:END -->

Each exception is a proved obstruction of the language, not an open gap.
Every other row is `Total` or theoretically total past a resource ceiling.

## Ordered reads without retained inputs

Call a layered construction input-forgetting when, just before each read,
its data store and pointer depend only on depth; the control location carries
the residual function. Ordered reads alone do not imply this property:
`,>,>,<<.` reaches one cursor with four stores after two reads.

- BrainIf's residual-DAG candidate satisfies it. Its first input cell is zero;
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

- BrainIf emits four lines per DAG node, three at the root. Destinations have
  `O(n)` digits, so the worst-case source is `O(T)`. Two shared output tails
  add constant text. A run consumes exactly `n` inputs in order and executes
  at most `4n+50` lines. The zero tail moves to a virgin cell only when the
  last byte is 49, then builds 48; the one tail increments 48 if needed and
  prints 49. All gotos go forward, so termination is structural.
  Interning and writing the labels cost `O(T)` in the repository's
  `Theta(n)`-bit table/index word model. This does not assert linear bit work.

  The public generator keeps the shorter source against the tree/spatial
  candidate; width requests retain that older route. Every three-input table
  shrinks: total characters `319576 -> 291524` (8.78%), summed executed
  lines `134984 -> 74440` (44.85%), with no table growing or slowing.
  All 2,120 rows through three inputs execute; constants, parity and four
  seeded tables per arity four through six also execute every row. A separate
  200-table five-input sample gives `573675 -> 360230` characters and
  `1501446 -> 280080` lines. Full-store boundary checks confirm erasure before
  the next read. The controls are in `tests/proofs/test_research_tracks.py`.


## Scaling status

These verdicts describe shipped generators and exemptions from the measured
size regression. Open generator-linearity work lives in the
[roadmap](../roadmap.md#generator-linearity).

<!-- SCALING-STATUS:START -->

| Language | Totality | Generation time | Output size |
| --- | --- | --- | --- |
| Ascenic | Total | Language lower bound | Language lower bound |
| Befunge | Exception | Linear | Linear |
| Malbolge | Exception | Open | Linear |
| Polynomial | Cap | Language lower bound | Language lower bound |
| Unary | Cap | Language lower bound | Language lower bound |

<!-- SCALING-STATUS:END -->
