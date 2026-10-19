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
- Malbolge: <a id="malbolge-bound"></a> the shipped hashed cascade reaches
  fourteen inputs, positional addressing reaches fifteen and sixteen, and
  seventeen remains open. Finite source space excludes some eighteen-input
  tables, so mathematical totality is impossible. The load law allows at most
  two final rows per answer cell; a one-cell-per-row-pair construction cannot
  cover seventeen in the 59,049-cell store. This is not a universal seventeen-input
  obstruction. Table-free memoized planning and one-pass fill are separate:
  fill is `Theta(T+59049)`, with exactly half a cell assignment per row in the
  positional build. Prefix sharing makes generation `Theta(T+59049)` through
  ten inputs. Wider cold planners are separate searches; their finite-domain
  measurements do not prove an asymptotic generation bound.
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
- Vandevelo: <a id="vandevelo-sparse-bound"></a> the shipped fixed-candidate
  sparse construction has worst-case `Omega(T log n)` characters, not `O(T)`.
  For `n>=100`, take `m` as the largest odd integer at most `T/n` and output
  one exactly on unsigned inputs below `m`. Both affine shortcuts reject the
  odd cardinalities, and the sparse route is selected. Each cube has dimension
  at most 48, so at least `T/(2n*2**48)` disjoint cubes are required. Every
  guard retains at least `n/2` independent equations and distinct identifiers;
  the 66-character identifier alphabet forces
  `L_n >= (T/2**51)*floor(log_66(n/4))`. Writing the source also forces
  super-linear character work. This does not bound every legal program,
  executed command count, or a construction with a growing candidate limit;
  universal linear source and generation remain open. A read inside a guard
  multiplexes later reads: `a ~> Inp?`, `a? :: Inp?`, `b ~> Inp?` binds
  `b = a ? x3 : x2`, so values need not be affine and coset-cover arguments
  bound only programs without such reads. The finite odd-prefix
  controls at eight and nine inputs executed 768 rows, using five/nine ones,
  cube dimensions `(2,0)`/`(3,0)` and 204/221 characters. Those measurements
  check the route, not the asymptotic bound. Controls remain in
  `src/esolangs/languages/vandevelo/tests/`.
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

- Container uses a folded tree through `n <= 6`.
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
- Vandevelo's T-dependent work was hidden by parity. It is exempt from the
  increments: registers grow ~sqrt(T) until an n*n cap binds at n=14, past
  what the band can step.
- S*bleq's T-dependent work was hidden by parity.
- 6-5's T-dependent work was hidden by parity.
- SLOW ACV MAMMALIAN read x1.43 on the increments.
- Painfuck's `at most` formula is also proved for every n.

<!-- PROOF-STATUS:START -->

| Generator | Proof | Qualification | Scaling | Execution | Workspace |
| --- | --- | --- | --- | --- | --- |
| /// | parameterized lookup | binary-to-unary substitutions form the row index; T escaped sweeps consume indexed entries before decoding one answer and deleting the suffix | linear: T fixed-size sweeps and 2T table characters | linear: worst 6T + n + 19 steps: rule parses, failed searches and substitutions | linear: worst 8L + 56 + 8max(0,T-15) bits: the program string, rewritten in place |
| 1 + i | tree | a node pushes its two children as function literals, reads its bit with `B` and `?` invokes one; constant subtables read their remaining bits unbranched | linear: at most 21T/2 - 10 characters, ten a node | poly n: worst 6n + 5 steps: six a level, eleven to print 1 - b | poly n: at most 4bl(L) + 40 bits: two functions, a decider and a frame |
| 3x | tree | — | linear: O(1) constant-span tests over canonical residual IDs | linear: worst L commands: the all-ones row enters every guard, no loop repeats | linear: at most n·bl(L) + 3T/2 + 2n + 16 + bl(2n-1) + 2K(2n+1) + Σ_{i≤2n+1}(K(i)+3) bits: guard residues, keys |
| 6-5 | finite lookup | past 35 inputs the positional walk loops on sixteen labels: each bit advances the pointer to the first row whose 2-adic valuation mark reads zero, and one pass per bit shifts the marks | linear, time n log: greedy order scoring, capped at n <= 10 | linear: worst L commands: loop-free, each token runs at most once; constant tables run every token | linear: worst 2T + 7n + 9 + bl(n) bits past n = 6: a tape of 2T cells |
| A Painter Ant | parameterized lookup | each embedded bit keeps the ant on a self-painting corridor or lifts it off, and the template walk after it advances the ant by that bit's weight, stopping at the corridor's end, leaving it over the indexed answer cell or the trailing run's first, which answers alike | linear: table walk; corridor weights sum to T | linear: worst 2L commands: one pass to the fixed point, one proving the repeat | T log T: worst 2(n+1)T + 4 + bl(L-1) bits: corridor, answers, ant, cursor |
| ABCDirection | linear lookup | the write row puts the essential inputs' table on the tape, one cell an entry, then each essential input's gadget tests its dequeued bit and a 0 walks the tape pointer left by that bit's weight, leaving it beside the indexed entry; an ignored input is read and never enqueued | linear: five rows of about T + zeros + 9n columns | linear: at most 5T + 80n + 210 commands: the write row, each unary move out and back, the band | linear: at most T + 10n + 56 bits: the tape, one bit a cell |
| AddSubJump | finite lookup | packed `n`-bit cells selected by a self-modified operand | linear: T/n packed cells of O(n) digits, O(n) decoder | linear: worst (11n+4)⌊T/n⌋ + 11T + 13n - 17 past n = 5, one more from n = 10 | linear: at most Σ_{a<M} bl(a) + C(n + bl(B+13+C)) + 3n + 5bl(n) + Q bits: program cells, T/n packed |
| Algebraic Programming Language | tree | bounded shared frames; base-26 names are unbounded | linear: bounded dependency scan and canonical residual IDs | linear: at most max(21,ceil(65n/2)-21)+K+2min(K,3n+1) commands: definitions initialize once and execute at most once | poly n: at most 179n+400+V+W if K=0, else A(198+8d+3b)+Q(b+114)+65n+d+bl(2n-1) bits: frame/global state |
| Alight | finite lookup | inputs folded into a row index by Horner's rule; the table is a string literal read with `at`, so the program has no branches | linear: one T-character literal, O(n) Horner reads | poly n: worst 2n + 5 commands, n Horner reads and one `at` | poly n: worst 72n + 762 + bl(6n+12) + bl(n) bits, n in 2..25 |
| ArrowQueue | parameterized lookup | one stage per input doubles the queued markers and adds the bit (Horner), and the count selects one of `2**n` constant-size cascade stages | linear: at most 2T + 6n + 7 rows, the constant tail folded | linear: worst 10T + 6n + 26 commands: Horner doubling 8 a marker, then at most 2 a row | linear: worst T + 11 + bl(3T+6n+5) bits: a queue of T markers |
| Ascenic | tree | Horner's rule by built `-2` constants makes each row's code `base + 2r`; `LT t`, `ADDS` at every change point adds 1 to codes below `t`, so the parity answers; straight-line code, no jump | lower bound: tight language and generated Theta(T**2) ([summary](#ascenic-bound)) | linear: worst 2T + 7n + 3 - 2⌊n/2⌋ commands: alternating answers, two lines a change | poly n: at most 3n + bl(n) + 15 bits: line index, scale times code, input cursor |
| B-tapemark | finite lookup | the blank grid is the table, one mark per row copied by `*`; a stage per input walks the mark pointer by that input's weight and `+` prints the mark it lands on | linear: 3T copy cells, T pointer steps, one stage per input | linear: worst 4T + 42n + 5 steps: 2T copy, stages 32 or 2w + 37 | T log T: at most (4T+31n+5)(8+bl(3T+n+3)+bl(9n+3)) + (T+4n)(10+2bl(8T+50n)) + 4bl(8T+50n) + bl(n) + 12 bits: program cells, data marks |
| Back | parameterized tree | an ignored input's run lands on the cell the next load fills, and a `-` after it leaves the cell empty | linear: leaf moves sum geometrically, sparse row render | linear: worst max(R,6n-1) + R + 3n + 6 commands, R = 3T/4+1 rows: load column, then all-ones path | poly n: worst n + 5 + bl(max(6n-2,2^n-1)) + bl(3n+4) + bl(n) bits |
| Befunge | exception | six-bit ASCII lookup ships through thirteen inputs; finite source space excludes some sixteen-input tables | linear: T table cells, one g at the index | unmeasured: worst 5n + 16 + 4⌈n/2⌉ steps to n=8, 5n + 29 to 10, 5n + 67 to 13 | poly n: at most six stack items; the grid is never written |
| BFStack | minterms | — | linear: zero-row walk telescopes to T | poly n: worst 73n + 371 + 13(n mod 2) commands past n = 7 | poly n: at most n + 7 + bl(n) + (d+1)bl(L) bits, d = max(n-7,0) + ⌊(3min(T,128)+1)/5⌋ + 2: brackets |
| Bitdeque | parameterized lookup | head/tail discards leave the indexed entry in the deque | linear: shorter of the shared tree and the 2T-command discard lookup | linear: at most 3T + 9n - 3 commands past n=4: load 2T, stage walk; unreached, n=5 worst 47 | linear: at most T + 2 + bl(4T+10n-5) bits past n=4: a deque of T + 1 bits; unreached |
| Bitwise Cyclic Tag | parameterized lookup | the table is the program, one four-bit cell per row; each embedded bit appends two walk zeros per unit of its place value, and a cell consumes exactly two, so the zeros carry the program pointer to the indexed cell and the held-back sentinel arrives there to fire it; the cell's second `0` consumes the answer it just appended, without which a 1 would cascade into the rows below | linear: 4T table cells, 4T walk appends, 5T + n steps | linear: worst 5T + n commands: input segments, then 3 per walk cell | linear: worst 16T + 8 + bl(8T+n-2) + bl(2T+n+1) bits: a data queue of 2T bits |
| bit~ | linear lookup | one tape cell an entry, and each input's one-shot loop jumps the pointer left by that input's weight, so the reads chain into a Horner index and a self-erasing walk carries the landed bit to one of two print windows | linear: bounded dependency scan and canonical residual IDs | linear: worst 7T + 17n + 92 commands past n = 1: row 0 walks the odd lane | linear: worst 2T + 49 + bl(2T+41) + bl(5T+18n+74) + bl(n) bits: 2T + 49 tape cells |
| Blindfolded Arithmetic | linear lookup | the table read at its essential inputs is one integer built by Horner's rule in base 8, and each essential bit of the row divides it by 1 or by 2^2^m, squared up from 2, so its low bit is the answer | linear: at most four instructions an octal digit, 10n of lookup | linear: worst T + ⌈(T-1)/3⌉ + 10n + 9 commands: all ones but the last row, run once | linear: at most 2T + n + 13 bits: the table, and Q in two registers |
| Boolfuck | tree | each input byte's low bit is read onto its own cell and tested in place by a flip-only decision tree, one flag interleaved beside each bit, consuming and emitting complete bytes; repeated residuals use level flags or normalized AND/XOR bodies, and affine tables stream through one accumulator | linear: geometric tree walk; affine tables use O(n) characters | poly n: worst 2n^2 + 27n + 8 commands; reads shuttle to scratch | poly n: at most bl(L-1) + max(12, bl(2n-2)+10) + n + Σ_{i<n} bl(i) + bl(2n) + bl(n) bits |
| brainfuck | tree | folded decision tree; residuals defer through level flags or binary words; affine tables stream | linear: decision_tree_program, span walk, leaf moves geometric | poly n: worst 69n + 44 commands, the AND table's all-ones row | poly n: worst 2n + 6 + bl(2n) + bl(n) + bl(L) bits |
| BrainIf | tree | equal cofactors share one layered DAG node, and an ignored input is read by the next layer's nodes; spatial lookup remains a candidate | linear: O(T/n) nodes with O(n)-digit addresses | poly n: worst 4n + 50 commands, one DAG path and a tail | poly n: worst 13 + bl(lines) + bl(n) bits: two cells, a line cursor |
| Caballo | tree | the inputs are the initial stack; each node is the wiki's conditional, `d` dropping a 0 bit's branch and the zero test `(1+di-)` cancelling a 1 bit's, so one stack survives; equal halves pop untested and constant subtables fold | linear: at most 15T - 14 characters, subtree_ids folding | poly n: worst n(n+1)/2 + 14n + 1 commands: empty groups skip whole | poly n: at most 4n² + 16n·bl(L) + 96 bits: a sum frame's base a level |
| Circlefuck | linear lookup | the tape is the program, so the table is its tail past the `@` that stops the run, entry 0 abutting the index digits at the ring's end; `}` deletes the cell under the pointer and slides the digits down into it, so counting the index out against one `}` apiece leaves the entry it names under the pointer | linear: bounded dependency scan and canonical residual IDs | linear: worst (2n+13)T + 94n + 89 + 2S to n = 7, S the codes of program characters 1..n | linear: worst 6L + 12n + 7 + bl(L-1) + bl(L-T-2) + bl(n) bits: the program is the tape |
| Circuit Diagram | tree | complete residual folds or a strictly smaller emitted fallback | linear: emitted text; fixed-order residual DAGs costed before rendering | poly n: worst 2n + 1 commands; at most 2n + 2 past n = 8 | linear: at most 7T/2 + 2n - 5 bits, n ≤ 7; 7T + 2n - 9 after: latches, pulses |
| Clockwise | linear lookup | the ring is the table: one `!` per entry in a countdown row, and the index in the accumulator picks which one it is zero on, turning the pointer down that entry's own column; seven `.` an input build the index by Horner's rule, doubled between inputs by a two-row gadget that spends the accumulator as distance and buys back two per unit | linear: five table rows of 2T columns, doubling gadgets whose widths halve downward | linear: worst 10T + 20n + 30 steps: the pointer's path to the last row | poly n: worst 57n + 50 + bl(2n+14) + bl(2^(n+1)+9n+1) bits: 7n-character queue |
| Codesick | tree | each distinct subtable is one labelled node; it appends its marker to the unread bits, and a substring test for `0` before the marker reads the last bit, deleting it on a hit; a miss deletes `1` and the marker by a self-jump | linear: O(T/n) nodes with O(n)-digit names | poly n: worst 3n + 1 steps: three a level, the leaf one | poly n: at most 24n + 16 bits: the unread bits and one marker |
| Collatz Multiverse | finite lookup | an array subscript may name `lineNumber`, so a cell is addressed by the number of the line that writes it | linear: one line per four rows, a 64-cell decoder, 3n index lines | linear: at most T/4 + 3n + 130 lines to n = 8: one step per line, no branching | T log T: at most ⌈T/4⌉(bl(⌊L/17⌋)+6) + 64(bl(⌊L/17⌋)+1) + (n²+168)(8n+bl(L)+9)/2 + 2bl(L) + 115 bits: arrays, registers |
| Container | finite lookup | the table is the prefix sum of its own steps, summed against a row counter that is live for one tick | linear: one line per step in the table, halting in 2n+2 ticks | poly n: worst 2n + 2 commands, a threshold build past n = 6 | poly n: worst 25n + 154 + bl(2n+2) + 2bl(n) bits, n in 7..24 |
| Crement | parameterized tree | each input is the data of one jump in a two-line tester; a node patches the tester's two targets to its children and jumps in, a folded subtree targets the shared self-jump or the line past the end, and a subtree already emitted at its level is targeted, not repeated | linear: at most 3(T - 1) + 2n + 3 lines, subtree ids | poly n: worst 5n + 2 commands, shared self-patching testers | linear: at most 2bl(N) + 32 + bl(2n+3) + 2n(10+bl(N-1)) + P(28+3bl(2n+2)+2bl(N-2)) bits: whole program state |
| CV(N)(C) | tree | the halting goto squares once more whenever the program is not shorter than its reach, so every finite tree halts, and a subtree already emitted at its level is entered by climbing the accumulator to its syllable and `j`, where shorter | linear: built in input order, no order search | linear: at most 17 + 4n + (n-1)(3 + sqrt(2L)) tokens: the path plus shared-subtree climbs | poly n: worst 17 + bl(2n-1) + bl(L) bits, n in 4..13 |
| Cyclic tag | parameterized lookup | weighted zero padding advances the cyclic rule pointer to the indexed answer; the next empty rule deletes it | linear: at most 5T + 2n + 1 characters, weighted padding | linear: worst 2T + n + 1 steps: n input rules, 2 per row, 3 closers | linear: worst 16T + 1 + bl(2T+n) bits: a queue of up to 2T - 1 bits |
| Decleq | tree | the tree stops `k` levels short, `2**k >= 2n`, and each leaf is a `2**k`-cell table indexed by an unrolled counter, since `T - 1` absolute jump targets would be `Theta(T log T)` digits; an equal subtree is emitted once | linear: bounded dependency scan and canonical residual IDs | poly n: at most 49n + 3*2^k + (n-k) + 2 commands, k = bitlen(2n-1) | linear: worst 55n + 11S + 95B + D + E + F + R bits: the memory tuple and registers |
| Dig | tree | finite cell placement, the last six essential inputs left to a painted leaf table, an ignored input among or above them read and dropped | linear: leaves are ≤64-cell rectangles two `$` counts index, area O(T) | linear: worst 128 + 46·2^((n-6)/2) for even n, 128 + 64·2^((n-7)/2) for odd, past n = 6 | linear: worst 8RC + bl(R-1) + bl(C-1) + bl(2n-1) + bl(n) + 10 bits past n = 4: the R×C grid |
| Dimensional | linear lookup | a bare `>` takes its dimension from the byte it stands on, so `d>` is a pointer displacement by the bit read: the index is a coordinate, doubled between reads by a two-loop `{`/`}` gadget, and it addresses one painted cell an entry along dimension 1 | linear: 2T table characters plus at most a fixed gadget per input | linear: at most 15T - 8n + 37 commands: paint 2T + 2, then 13 per index unit doubled | T log T: worst Σ_{k<T} bl(k) + 5T + n(n-1)/2 + 4n + 6 + bl(2T+20n+56) + bl(2n-1) bits |
| EGL | finite lookup | row 1 is painted with the table and each essential input's `(-...)` guard walks the row-0 pointer right by that input's Horner weight, so `v=` prints the indexed cell | linear: T painted cells, guard weights sum to T - 1 | linear: worst 3T + 52n + 3 commands: paint at most T-1 ones; weights sum to T-1 | linear: worst 2T + 2n + 7 + bl(L-d-3) + bl(L-d-9) + 2bl(n) bits, d the digits of T |
| Eval | linear lookup | fixed reversed stack order selects the indexed row | linear: T literal plus halving `;` runs under T | linear: worst 2T + 13n + 1 commands: one per program character, then the final frame pop | linear: worst 8L + T + n + 2 + bl(L) bits: frame program text and a stack |
| Fackward | tree | a level is a block whose quiet pass reads the bit; `/ c 49` makes it 0 or 1, that many `~` swap the two child blocks, `!` drops one and `)` runs the other; equal halves fold | linear: one block a node; a subtable repeated under two parents is copied | poly n: worst 40n + 4 steps: 40 a level, then print and halt | linear: at most 8L bits: the two stacks hold the program's tokens |
| FALSE | tree | — | linear: 12 characters an internal node, two a leaf | poly n: at most min(12n + 69, 10n + 99) commands, 26 stored lambdas | poly n: at most (2n+56)(n+4) + n + 1 + bl(n) bits: 26 lambdas |
| Fargo | tree | finite folded layout | linear: word-packed transform and emission | linear: at most 5T + 1 commands past n = 5, else 15T/2 - 4: each token runs once | linear: at most 16(L - 3) + bl(L) + 11 bits past n = 5: one frame's tokens, pending calls |
| Fish | finite lookup | the inputs form a Horner row index and `g` reads that column from the table row | linear: T table cells, one g at the index | poly n: worst 9n + 9 commands, n Horner reads and one `g` | poly n: worst n + 13 + bl(9n+8) + bl(n) bits: one stack, x |
| Flowchart | finite lookup | a pair of answers per deque, and the input walks the deque cursor to the pair it wants | linear: T pushes, `T/2 - 1` cursor steps, two rows | linear: at most 3T + 9n + 4 nodes: preload T plus runs, then 8n of selection reads | T log T: at most (7T+20n+100)(bl(L)+4) + Σ_{j<T/2}(bl(j)+2) + 2bl(L) + n + 2bl(n) + 32 bits: exit-memory keys, deques |
| Forbin | finite lookup | the last seven inputs paint a block of `2**7` table entries as one call's literal argument list, and each of them halves the callee's parameter window with one multi-assignment, so the first parameter ends up holding the addressed entry | linear: two characters an entry, halvings sum to `2 * 128` | poly n: worst 2 max(n - 7, 0) + 2 commands | linear: worst 32n + 71 + 2bl(n) + G bits for n ≤ 48: main's locals in both frame and scope |
| Forþ | tree | the tree tests the essential inputs; an ignored one is read and dropped as `,0*+` | linear: span walk, constant dispatch, step literals geometric | linear: at most 6T + 12n - 3 commands: every heap scope defined once, one dispatch path | T log T: at most (2n+364)T + 43n + 2bl(n) bits: frame text and the scope dictionary |
| FRACTRAN | parameterized tree | the bits are the exponents of `n` primes in the starting value, a decision tree gives equal subtables one state prime, and the first-match rule is the else-branch | linear: at most C = Σ_d min(2^d, 2^2^(n-d)) states, O(log T) digits each | poly n: worst n + 2: a step a level or unread set bit, the leaf, the halt | poly n: at most bl(p_{n+1+C}) + n + 2 + Σ_{i≤n} bl(p_{i+1}) bits, p_k the kth prime: all-ones start |
| Grapheme | linear lookup | the whole table is one int-mode literal read in base 10, and each `W` squares an accumulator and doubles it on a 0, which is Horner's rule for the complemented index, so the accumulator is exactly the power of two that `R` shifts the wanted entry down to bit 0 | linear: bounded dependency scan, one table literal, n read blocks | linear: worst 14n + 32 + d commands, d the digits of 2^T: one per program character | linear: worst 16d + 112n + 312 + bl(14n+d+17) + 2bl(10^(d+1)+2^T-1) + bl(2n) + bl(n) bits, d the digits of 2^T |
| Home Row | parameterized tree | — | linear: bounded dependency scan and canonical residual IDs | linear: worst 10T + 10n + 88 commands: every guarded leaf run, one equal pair of rows | poly n: worst n + 32 + bl(27T/2+10n+6) bits: index cell and cursor |
| Hot | tree | the table is a tree of Church pairs, equal halves folded to `K`, applied to the bits that one fixed reader stage an input takes from `A` | linear: 14 characters a pair, 75 a reader stage | poly n: worst 35n + 45 rewrites: a pair a level, then the answer stage | linear: at most 24L bits: at most three live copies of the term, 8 bits a combinator |
| Inject | finite lookup | one table block halved by `O(n)` conditional substitutions | linear: T literal, `.` halvings sum to 2T | poly n: worst 8n + 10 commands past n = 4, halving per level | linear: worst 24T + 516n + 169 + A bits for n = 5..16: the program text after n reads |
| INTERCAL | parameterized tree | equal-width constants set each input once; fully grouped mingle, unary logic, and select expressions form a Shannon tree | linear: reverse-depth numbering confines long names near the root | linear: at most 2n + 3 + Σ_{0<l<n} min(2^l, 2^(2^(n-l)) - 2) statements, one per named node | linear: at most 9S - 18 + Σ_{k≤S-2} bl(k) + bl(S) bits, S the Execution bound: one keyed bit per variable |
| Interprogck8 | tree | a one-line compare read either flies its 1 child down a residue mod 82 through shared rungs or dismounts 85 lines onto its 0 child; a lane is any residue not in the air | linear: each node's scans and dismount span a bounded number of lines | linear: at most L commands: every jump lands past its rung | poly n: at most 8 + bl(L) + bl(n) bits: the accumulator, a line cursor, the input cursor |
| LaserFuck | finite lookup | weighted arms select one of `2**n` prewritten cells, cleaned in one sweep | linear: three rows of linear appends, ~15T | linear: at most T + 297n + 687 steps for n = 5, 6, then 18T + 56n + 5 | linear: at most 12T + 2n + 11 + 2bl(n) bits past n = 4: 3T + 1 tape cells |
| Line | tree | finite decision trees preserve totality; complete ordered residual folds share every state unless their exact pixel area exceeds the fallback | linear: complete residual models and area-admitted rasters cost O(T) | poly n: worst 5n commands; complete folds retain this bound | poly n: worst n + 1 + bl(3n-2) + bl(n-1) + bl(2n-1) + Σ_{c<n} (max(1,bl(c)) + 1) bits past n = 4 |
| Malbolge | exception | finite source space rules out some 18-input tables; the shipped branch-free five-cell mixer covers every table through ten inputs, a two-level pointer cascade covers eleven, a selector that splits the last input off that cascade covers twelve, answer stubs that read the last input cover thirteen, and four copies of that table selected by inputs twelve and thirteen cover fourteen; fifteen and sixteen replace the hash with a positional address, three input bits per two-trit digit, so no row collides; the cap is sixteen, and seventeen is open ([summary](#malbolge-bound)) | measured: fixed 59049-cell store through n <= 16 | unmeasured: worst 478n + 1459 steps for n ≤ 10; eleven to sixteen are separate builds | poly n: at most 16·3^10 + 49 + bl(n) bits: ten-trit words, three registers, halt flag |
| Minifuck | parameterized construction | affine or two-residual byte accumulator; budgeted stored residuals; total positional `_mux` fallback | linear: shared tape text admitted within the positional mux budget | linear: at most L commands: straight-line, the cursor never moves back | linear: worst 6T + 14 + bl(6T+12) + bl(6T+14) + bl(L) bits past n = 4: a tape bit-integer |
| Minsky Swap | parameterized lookup | every input is one `++`/`**` run; a stage per input adds its weight to the index register, and a `~` cascade routes the index to one of two shared leaves at the head of the program, so every table of one arity whose inputs all matter renders to the same length (an ignored input's stage is a bare `~ ~`) | linear: cascade routes to two shared leaves, one-digit targets | linear: worst 2T + 6n + 4 commands: a unary index add, then the ~ chain down | poly n: worst n + 3 + bl(2^(n+1)+6n+5) bits: two registers and cursor |
| Modulous | linear lookup | the table is one `PSH STR` literal, pushed so that row 0 lands on top, and the inputs add their weights into the counter of how many characters to discard | linear: T-character literal, one read block an input | linear: worst 5T + 5n + 1 commands: a zero push, n reads, then 5 per entry discarded | linear: worst 6T + n + 2 + bl(6n+5) + bl(2n-1) + bl(n) bits: table codes on the stack |
| Object disoriented | tree | a node keeps its input bit in `t` and its negation in `a`, via an object that is a 1 until a 1 bit calls it; each bit object calls its branch only on a 1; equal halves drop the bit untested, constant subtables fold, and a repeated branch is a class written once | linear: at most 39T + 21 characters: 35 a node, 4 a leaf | poly n: worst 67n + 34 commands: one tree path, 67 ops a level | poly n: at most (2n+3)(bl(L)+bl(2L)+3bl(6n+8)+5) + (6n+9)(2bl(L)+3) + 2bl(L)+bl(6n+8)+bl(6n+9)+bl(n)+19 bits: two frames and six cells a level |
| Packlang | linear lookup | one 128-row array block, painted inside the `If` that selects it | linear: one write per differing row, block-bounded index digits | linear: worst 19T/2 - n - 4 steps for n = 2..7, then 3T/64 + 1206 - n | poly n: at most min(T,128) + 2n + min(n,7) + 192 + 16[n>7] + bl(L) + 2bl(n) bits: one frame, array |
| Painfuck | tree | decision tree emitted directly in Painfuck's own commands; numeric I/O pays no ASCII offset, and `d` resets the pointer to the answer cell | linear: brainfuck-shaped decision tree; `d` reset keeps leaf returns O(1) | poly n: at most ceil(3n^2 / 4) + 20n + 4 commands, one path | poly n: at most 2n + 5 + 3bl(n) + (n+1)bl(L) bits: 2n + 2 cells, loop stack ≤ n |
| Piet | finite lookup | each table entry is pushed and an input index selects its output; literal products replace conjunction tables | linear: one bounded-width strip with O(T) codels | linear: worst 2T + 4n + 14 steps past n = 1: one colour block per operation | linear: worst T + 2n + 7 + bl(3T+5n+15) + bl(2n-1) + bl(n) bits past n = 2: the stack |
| Pointless | tree | each distinct subtable is one function, pasted in where that is shorter; `,=` maps a character to its bit through the cells 48 and 49, and `[` tests the bit's cell; the one `!` seeds the 1s that make `+` an increment | linear: O(T/n) nodes with O(n)-digit names | poly n: at most 26n + 311 steps: setup, then 26 a level; a pasted call saves one | poly n: at most (n+1)(2bl(L)+4) + 16n + 430 bits: a frame a level, the tape |
| Polynomial | tree, cap | each finite instruction list has a finite prime-product encoding; every program for a maximal-width table needs Omega(T/log T) distinct real roots ([summary](#polynomial-bound)) | lower bound: coefficient mass is Omega(T**2 / log T), matching the uncapped residual-DAG construction; equal-root blocks force Omega(T/log T) distinct real roots and the slack certificate prices every multiple ([summary](#polynomial-bound)) | unmeasured: exempt as a cap row | poly n: at most bl(min(10T-7,1934) + 10) + 1 + max(bl(n+3), bl(49(M-1))) + 2bl(n) bits, M = max_k min(2^k, 2^(2^(n-k))) |
| Qoibl | linear lookup | the table is one binary literal, divided by the power of two the reads build | linear: T-bit literal, one squaring statement per input | poly n: worst n + 2 commands, one statement per input | linear: worst T + 3 + bl(n) + bl(n+2) bits: variables 0 and 1 |
| Quassaunt | tree | each distinct subtable's code is stored once in a global and run by name; a node tests its character's set {2, c} against {1} with `%%Ifpropersubset`; equal halves and constant chains read their bits unbranched | linear: O(T/n) nodes with O(n)-digit names | linear: at most 5⌊L/57⌋ + 21n + 9 steps: five a stored node, 21 a level | linear: at most 24L bits: the running code, the stored code and the stack, each within the source |
| RAM0 | parameterized tree | the inputs are stored once and each node loads its bit with `L`; a subtree already emitted is reached by `goto`, so only the distinct subtables are laid out, and the straight-line lookup is kept as a candidate | linear: O(T/n) distinct subtables, O(n) commands each | poly n: worst n^2 + 8n + 5 commands, one root-to-leaf path | poly n: worst n + bl(S) + 2max(1,bl(n-1)) + Σ_{a<n} max(1,bl(a)) bits, S the token count |
| ROTfuck | finite lookup | every loop's cycle is 0 (mod 8), so its exit rotation is the same whatever its trip count | linear: bounded dependency scan and canonical residual IDs | linear: worst 8T² + 43T + 15n - 5 commands for n = 2..6: NAND's all-ones row, walks quadratic per digit | linear: at most 2T + 5n + 35 + bl(2080L) + bl(2T+6) + bl(L) + bl(n) bits: 2T + 7 cells |
| Rubic | tree | every subtree undoes its `r2` store, so the cube is one of two states and each table expression is checked on both; equal halves read untested and constant subtables fold | linear: at most 94T characters, subtree_ids folding | poly n: at most 20n + 7 commands: a node runs 20 at most | poly n: at most (3n+4)·bl(L) + 3n + 175 bits: n+1 loop frames, the cube |
| S*bleq | finite lookup | packed chunks decoded after the hoisted read block, against a hoisted tree that lays out each distinct subtable once and jumps to it | linear: T/n packed chunks of n bits, O(n) decoder | linear: worst 3n + 2 instructions to n = 9, the tree route: n reads, 2n - 1 tests | linear: at most 3L bits: the self-modified program, decimal cells |
| SendStuff | tree | each distinct subtable is one named node reached by reference; an Input node sends a 1 through `Subtract 49` and a 0 through `Divide 48`, `Subtract 1`; equal halves and constant chains read their bits unbranched | linear: O(T/n) nodes with O(n)-digit names | poly n: worst 4n + 2 steps: four sends a level, root and leaf one each | poly n: at most (n+1)(bl(L)+10) + bl(n) bits: a pending frame for each 1 taken, one sending frame |
| SLOW ACV MAMMALIAN | linear lookup | a read chain banks each bit on array 16 and the dispatch's `DIGEST LEAPFROG` reads that sum as the leaf address; the five lightest weights are CONSUMEd from planted cells, so they never read the sum and need not be multiples of 256, which puts the stride at an eight-token leaf | linear: every address solved in closed form, the leaf table first | poly n: n read nodes after a fixed dispatch and leaf | poly n: each command adds at most one byte; commands are poly n |
| Smallfuck | parameterized tree | each level owns a bit, branch flag, and result cell; a child transfers its result three cells upward, so the depth-first pointer walk crosses each tree edge only a constant number of times | linear: six characters an input, approaching 48.5T characters | poly n: at most 9n^2 + 100n + 20 commands, one tree path | linear: worst L + bl(L) + bl(3n) bits: one tape bit per source character |
| Smu | tree | a node stores its halves under the input bit's own names and pushes the one the bit names as the next run's program, above seven skip runs for the byte's other bits; a node with equal halves is a pad; five macros carry the repeated text, and a subtree two parents reach is one more when that is shorter | linear: at most 6T + 90 characters: five a node, one a leaf | poly n: worst 55n + 5 commands, one tree path of eight runs a level | linear: worst 24E - 1214 + bl(E) + bl(n) bits for n ≥ 2: code, stack, variables |
| SStack | tree | each input byte is compared with stacked '1' and '0', then popped before descent; the empty test stack ends both one-shot loops; a constant subtree reads its remaining inputs and prints; repeated residuals use guarded labels | linear: 21 characters an internal node, three a leaf | poly n: at most 7n + 3 commands, six a tree node plus guarded dispatch | poly n: worst 6n + 12 + bl(K) + bl(n) bits, K commands: n stacked input bytes |
| Streetcode | linear lookup | the street writes one cell per entry, then each essential input's mouth forks on its bit (an ignored one is a lone read) and its side room walks the cell pointer left by that bit's weight, leaving the car over the indexed entry | linear: nine rows of street, ~1.8T columns | linear: worst 3T + 110n + 106 steps for n = 6, 7, then 4T + 14n + 650: one zero | T log T: worst nT + 2n + 25 + bl(2T+57+G) + 2bl(n) bits past n = 5, G = Σ_{0<k<n} max(51,2^(k-1)+3) |
| Subleq | finite lookup | shared direct-jump residual DAG or packed decoder with interned chunk payloads | linear: O(T/n) residuals or packed chunks, O(n)-digit addresses or payloads | linear: at most 8T + (7n+5)(⌊T/n⌋-1) + 23n - 6 steps: bank selection adds two | linear: at most max(T+2C+(C+2)bl(B+17+2C)+I·bl(B)+(2I-1)bl(B+17)+R, M·max(7,bl(M))+bl(M)+bl(n)) bits: decoder or tree, M=19+10n+6D |
| Suffolk | linear lookup | workspace-limited NOR cofactors share computed values; otherwise a countdown counts rising and falling steps to recover the indexed entry | linear: residual interning, bounded NOR circuit, countdown fallback | linear: worst L + R commands, R the prefix through the first read: one pass, then EOF | poly n: worst bl(L-1) + max(6,n-1) + max(19,4n-1) + bl(n) + 4 bits: bounded NOR cells or eight countdown cells |
| Super SNUSP | tree | each folding pass removes at least one pending unit | linear: one `*` per entry | linear: worst 2T + 19n + 21 commands past n = 4: one straight line, all ones but one row | linear: worst T + 2n + 12 + bl(L) + bl(n) bits past n = 4: the packed-table cell |
| Taglate | tree | — | linear: bounded dependency scan and canonical residual IDs | linear: worst 16T + (7n^2+26n-22)/2 for even n > 2, 28T + (7m^2+22m-36)/2 for odd, m = n + 1 | linear: worst 24·2^m + 12m + 12 + bl(m) + bl(L-4·2^m-7m+1) bits, m = n rounded up to even |
| thisthat | tree | inputs go to either end of one bistack row, an ignored one to the column; each end pop drives the next alternating-axis decision node, or goes to the column where the halves agree, in an order the row can pop | linear: the planar H-tree has `O(sqrt(T))` width and height | linear: worst 32·2^(n/2) - 29 for even n, 48·2^((n-1)/2) - 29 for odd, past n = 2: about sqrt T | poly n: worst 4n + 89 + 2bl(n) + Σ_{c<n} max(1,bl(c)) bits past n = 2 |
| Thue | linear lookup | the table is the starting state, one character an entry, and the bit read rewrites every adjacent pair to one of its two members, so the state halves per essential input and the last character is the answer; an ignored input's round reads its line and deletes it; the rules never overlap, so the language's random rule choice has nothing to choose | linear: T state characters, at most 23 fixed rules plus expansions | linear: worst 2T + 3n - 2 rewrites: n rounds, each a marker sweep out and back | linear: worst 8T + 24 + bl(2n) bits: the T + 3 character state string |
| Unary | tree, cap | complemented-byte decision tree; constants, projections and conjunction guards avoid flags | lower bound: worst source length at least 2**T - 1; zero-count encoding | unmeasured: exempt as a cap row | unmeasured: exempt as a cap row |
| Underload | parameterized tree | equal-width input programs leave one selector apiece; each node stores both branches as strings and the selector evaluates exactly one, while a constant leaf discards the unused selectors; a repeated subtree is pushed once and carried above the next selector, and the plain tree stays a candidate | linear: at most 7n + 11T - 4 characters: 7 an input | poly n: at most 14n - 1 commands, one path of n selections | linear: at most 24L + 120T + 32n - 176 + bl(2L+10T+6n-14) bits: spliced program, stack |
| Unlambda | tree | each half is a `d` promise, forced by the `?` test that selects it, since an argument spelled inline would be evaluated before the application; the shipped node instead returns `s` over its selected promises, so a repeated subtree bound once as a promise reaches every half below, and the plain tree stays a candidate | linear: 29 characters an internal node, four a leaf | poly n: at most max(77n + 12, 84n - 9) steps: 77 a split level, 7 a bound node | T log T: at most 12L + 69 + (3n+6)(8L + 24 + bl(3n+6)) + bl(n) bits: a shared subterm per frame |
| Unsquare | linear lookup | the table is one `O`/`I` push per row, reversed, and each read pops its bit's weight in cells off the top of it | linear: `2**n` cells and `2**n - 1` pops, two bytes a row | linear: worst 4T + 79n + 22 commands past n=5: 12- or 14-cell loops, 76 per read, weight pops | linear: worst T + 12 + bl(L) + bl(max(0,L-33)) + 2bl(n) bits: T + 1 table cells on the stack |
| Vandevelo | minterms | an affine-cube peel emits one guard line per coset of an affine cover of the 1-set | open: O(T) lines and commands for every table, O(T log n) identifier text; the build is measured flat, but child-rebuild scans are bounded only by q**2 a node and core work by O(T*sqrt(n)) | linear: at most Q - G + 3C steps: Q ? reads, C comparisons, G guards' final loop? skipped | poly n: at most n * n registers; sqrt T below the cap |
| What!? | linear lookup | Horner's rule reads each bit with `??` and doubles by `*`; the index counts down one `-` a row, so at change point `b` it wraps above `2^k` exactly when the row is below `b`, and `[2^k>` writes the answer slot; past 15 inputs `???` puts the high bits in the index slot's string, and a guard per `2^15`-row block reloads the index | linear: one `-` a row and one test a change point | linear: worst 6T + 6n + 5 commands: alternating answers, every conditional true | poly n: at most n^2 - n + 276 + bl(2n+1) + bl(2n-1) + bl(L) bits: the 256-slot tape |

Symbols the formula cells use:

- **3x:** K(i) = 2bl(2^(i-1)·3^(2i-1)) + 1, a bound on the ith key's bits.
- **AddSubJump:** C = ⌈T/n⌉, I = 5n + 54, B = 4I, M = B + 14 + 2C; Q = I·bl(B) + (3I-2)bl(B+13) + 2bl(M-1) + bl(20n+212) + 23.
- **Algebraic Programming Language:** K = shared uppercase definitions, excluding NOT; A = 4n+3, active split and NOT frames; Q = 6n+5, pending nodes across frames; b = bl(2L+2), serial widths for AST nodes and functions; d = bl(L), bounding function-name length and the line cursor; V = Σ_{1≤j≤n-2} (bl(s) + bl(s+1) + bl(s+5)), s = 2n+8+7j, three serials per level; W = bl(2n-1) + bl(2n+3) + bl(2n+13) + bl(F) + 2bl(F+1) + bl(F+2) + bl(F+4), F = 2n+7.
- **Crement:** P = Σ_{k<n} min(2^k, 4^s - 2^s), s = 2^(n-k-1), the shared nodes per level; N = 3P + 2n + 3.
- **Decleq:** S = 2^k, m = n-k, c = 3⌈(n+18)/3⌉, P = c + 144n + 3k + 3S - 3; B = Σ_{i<n} bl(18+i); D = Σ_{j<k} (2bl(18+m+j) + bl(P + 3(j-k+2) - 3·2^(k-1-j))); E = Σ_{l<m, u<2^l} (2bl(18+l) + bl(P + 3l + (2u+1)2^(m-l-1)(S+18) - 3ν(u))), ν = ones in binary; F = Σ_{j<2^m} (22 + 6S + bl(x) + bl(x+9) + 2bl(x+10) + bl(x+14+S)), x = P+3m+j(S+18)-3ν(j); R = 3bl(P - 3 + 2^m(S+18)) + bl(n) + bl(c) + c + k + 8.
- **Forbin:** G = max(bl(h+1) + 4, max_{j<h} bl(j+1) + max(1, bl(h-1-j)) + 10), h = max(n-7, 0), the loop cursor.
- **Inject:** A = bl(12n+10) + bl(2n) + bl(n) + Σ_{i≤n+2}(bl(3i) + bl(3i+2)) + Σ_{2n+5≤m≤6n+4} bl(m).
- **Smu:** E = 95T - 80, the macro-expanded program with no constant subtree.
- **Subleq:** D = Σ[k=0..n-1] min(2^k, 2^(2^(n-k))-2), the nonconstant residual cap; M = 19 + 10n + 6D, the shared-tree memory-cell cap; I = 8n + 47, B = 3I, C = ⌈T/n⌉; R = bl(3I-3) + 5bl(n) + 2n + 33 + max(n, bl(n)+1) + max(1, n-1), the registers.

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
  [summary](#malbolge-bound) measures why the hashed cascade stopped at
  fourteen (the depth a truth table forces climbs past any decoder pass count as the
  answer-cell load rises), gives the positional build that covers fifteen and sixteen with
  no collisions, and shows why seventeen is beyond any build spending a cell per row
  pair.  Whether some 17-input table has no program is open.

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

Accordingly, this ledger records 85 theoretical totality arguments and
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


## Identifier and fallback audit

- Vandevelo: <a id="vandevelo-identifier-and-fallback-audit"></a>

  The construction bounds register upkeep by `O(T)` lines, but identifiers
  cost `O(log n)` characters per occurrence. Command count is proved linear
  below. The build's charge leaves child rebuilds unbounded, and
  dual-basis core work has only a super-linear aggregate bound. The
  audit marks size `Measured`, keeping its regression gate without claiming
  an asymptotic proof.

  The audit counts identifier characters. The default corpus executes 66
  tables through six inputs and 2,772 rows across original and renamed
  programs. The seeded pair-sampling fallback it once counted is gone:
  dropping it changed 0 of 200 random tables at each n=6..10. Through five
  inputs an exact scan of all directions replaces it: no three-input table
  grows, and the four-input tables total 0.05% less.

  The tested naming rule assigns the shortest existing names to the most
  frequent identifiers, replacing tokens simultaneously. On `Random(0)`'s
  12-input dense table, source shrinks from 32,269 to 31,942 characters
  (1.01%); its 4,414 identifier occurrences occupy 5,273 characters before
  renaming. Sixteen evenly spaced input rows, including both endpoints,
  execute under both spellings and match the table. The Vandevelo profiler that
  measured it was removed; it ran with `--min-inputs 12 --max-inputs 12
  --random-cases 1 --sample-rows 16`.
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
  never computed, so output is byte-identical. With candidates disabled,
  it alone keeps n=8 and n=10 random tables under
  `T/n` clauses (`tests/generators/test_boolean_vandevelo.py`).

  Commands per row are therefore linear. A halting row fails one part of
  each guard, and every value is a strict boolean. So a register toggle
  costs five commands, a part at most five, and an input read one. Upkeep
  is at most the constraints' total weight, `4*n*C + 4*T` with `C` clauses,
  and parts are at most `n*C`. With `C <= 17*2**n/n`, a row runs under
  `25*n*C + 20*T + n + 1 = O(T)` commands, so the execution-time cell is
  Linear. The affine, coset and complement paths emit at most `n` parts
  in all.

  Generation time is measured flat but not proved linear. A node holds one
  representative per coset of its span, so its work is its coset count,
  which at least halves a level. That retires the near-full wall: with `k`
  zeros the first chain keeps two cosets for `n - log2(k) - 1` levels, and
  nodes that held points paid at least `T*(n - log2(k) - 2)`. Output is
  byte-identical. Element visits per entry at n=10..14: three zeros
  2,700--3,200 (was 16,800--23,600), eight zeros 3,400--3,800 (was
  19,000--28,400), density 0.9 2,400--2,700 (was 7,700--8,700), dense
  500--900 (was 940--1,920), quadratic forms 110--120 (was 220--320).
  Best-of-three time, three zeros, n=11..15: 290--332 us a row, against
  1,237--1,696 at n=11..14 before; dense 76--108.

  Generation time cannot be linear before output size is. It includes
  writing the result, and the result is only `O(T log n)` characters, the
  identifier gap above. Even counted in word operations, four build terms
  escape the charge. A child rebuilt after it empties scans its parent's
  `q` cosets, and a rebuild need follow only one parent coset's removal,
  so these scans are bounded only by `q**2` a node. `certify` rebuilds the
  same way, and the clause bound needs it to. The children built under one
  node total at most its cosets, so cosets built cost at most the level
  above a level, `O(T*n)` a chain. Halving needs both halves of each child
  coset to leave together, and a cube harvested across the chain's span
  removes one. Measured, the levels do halve: three zeros at n=14 build
  12.96, 6.47, 3.23 and 1.61 `T` cosets at levels one to four. Rebuilding
  in `extend` only after a node loses three quarters would make the bound
  geometric. Over a 433-table corpus through n=13 that costs 2.5% of
  emitted size, and 4--6% at n=11..13. Certification now discards pairless
  candidates on every call but refills a pool only when removals reach a
  quarter of the current size. If `r` cosets left since the last refill,
  its representative scan costs `q <= 4*r`; summing over disjoint refresh
  epochs charges those scans to removals. `_assure` still runs at every
  level, preserving the half-average guarantee. Across 354 tables through
  n=9, refresh calls fell from 14,298 to 13,992; their summed node sizes
  fell from 110,943 to 108,907 cosets. No program grew and both builds
  matched all 3,590 executed rows. The exact `_assure` fallback sorts its
  representatives, costing `O(q log q)` per call; repeated assurance and
  child rebuilding remain uncharged. A separate untried fix keeps a
  level while its direction holds half the average, rebuilding only on a
  crossing. Historically, `certify`
  inclusive is 0.003s of a 0.53s build at n=13 and 0.184s of 6.27s at n=16,
  under 3%, so the fix moves no gate: the axis is proof-shaped, and the
  refresh cost it would trim is mostly `extend` and `run` -- 17% at n=16.
  `_nearest`'s sparse fallback lists points. Listing
  representatives costs cosets but moves sizes from -9% to +14% a table,
  +0.9% in total. The fourth term, the core build, is below.

  The dual-basis completion's other terms charge to the output. Column
  extraction costs `n*dim` a clause and the echelon reduction at most `n` a
  dual, while the clause's guard alone writes `n - dim` parts of `O(log n)`
  characters. Cubes of dimension above `2*log2(n)` pay from their own
  `2**dim` points. So these terms are linear in `T` plus the output, and the
  character-level time gap coincides with the identifier gap. Measured on
  seed 0, n=12..16: 2.0--2.5 `T` for columns and 0.75--0.91 `T` for
  reduction.

  The core build stores distinct pair sums and queries each distinct nonzero
  column against the core, preserving the old triple cache's first witness.
  A later core input cannot precede that witness, so repeated columns reuse
  it. With `u <= min(n, 2**dim - 1)` distinct columns and core size `c`,
  work is `O(n + u*c)` and cache entries are `O(u + c**2)`. Since
  `c <= 1 + sqrt(2*2**dim)`, the disjoint cubes and `C <= 17*T/n` give
  `sum(n*c) <= 17*T + sqrt(34)*T*sqrt(n)` by Cauchy--Schwarz. Cache
  insertions and witness-cache upkeep total `O(T)`. Core queries stop once
  the ascending core passes the current witness's last input: later triples
  cannot precede it. On all 276 tables through three inputs and 24 seeded
  tables per arity at n=4..8, this reduces pair lookups from 3,744 to 3,615
  with byte-identical emitted programs. The queries still have only an
  `O(T*sqrt(n))` bound. The former triple cache cost `c**3/3` a clause. A core with no relation of weight four or less can hold all `n`
  inputs: the extended-BCH columns `(1, x, x**3)` over GF(16) do, with
  `dim = 9`. Half the cosets of that subspace at n=16 reach a 16-input core,
  but the peel merges coset pairs into cubes of dimension 10--12. That gives
  12 clauses and `0.13*T` work in the former triple cache. Any two cosets of a subspace form a
  cube of one dimension more. Blocking that merge leaves a Sidon set of
  cosets, too sparse to matter, and globally popular directions do not see
  planted cubes. On random tables the greedy core stops at about
  `(6*2**dim)**(1/3)` inputs: at most 6 to n=16, and a flat `0.43*T` in
  the former cache. No executed table exceeds a constant; the new query
  bound is still super-linear.

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
| Vandevelo | Total | Open | Measured |

<!-- SCALING-STATUS:END -->
