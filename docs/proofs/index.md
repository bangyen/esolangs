# Boolean-generator coverage proofs

Construction summaries use `T = 2**n` table entries; logarithms have a
fixed base unless specified. Detailed derivations and research history are
archived in Git at `9c4d0b392:docs/proofs/`. Executable proof tests remain.

- FRACTRAN: <a id="fractran-bound"></a> worst-case Boolean source is `Theta(T)`.
  The counting floor is `T/log2(15)-O(1)` characters. A shared decision diagram
  stores `C=sum_d min(2**d, 2**(2**(n-d)))=O(T/log T)` states,
  at most `C+n+1` primes and `2C+n` fractions. Its first-match rule branches
  on an input prime; leaf fractions produce the answer and trailing fractions
  clear unread set inputs. Fractions operate on `O(n log n)`-bit values.
  The [generator ledger](#generator-ledger) gives the command bound.
  Distinct row addresses instead cost
  `Theta(T log T)` text; that is a construction bound, not a language bound.
  Indexed execution and literal scanning have different costs.
  Controls: `src/esolangs/languages/fractran/tests/proofs/test_fractran_bound.py`
  and `src/esolangs/languages/fractran/tests/proof_fractran.py`.
- Malbolge: <a id="malbolge-bound"></a> every truth table through seventeen
  inputs has a program. The [source count](#exceptions-and-walls) excludes
  some eighteen-input tables. Through sixteen, the positional fold stores
  two answers per cell. At seventeen the first fifteen bits select a primary
  word. Suffixes `00`, `01` and `10` read its three slots. Suffix `11`
  replaces one base-nine digit of the address and selects a spill slot.
  The generator derives the spill markers from the slot geometry and
  the decoder's legal jump routes. A Latin rank assigns one point per
  line before the remaining paths and cycles are oriented. The
  131,072 (word, slot) pairs are distinct across 44,224 words.
  Each column marker maps the eight legal source bytes to eight output
  triples. Words shared with navigation have fewer legal bytes. The
  construction fills the decoder's two no-op lookup lanes from relations for
  ordinary permutations and independent navigation patterns. It projects
  color variables in dependency order, retaining the compatible printer
  polarities at each terminal. Inverse encodings map requested answers
  directly to legal operands. The
  [coverage certificate](../../src/esolangs/languages/malbolge/tests/proof_packed_decoder.py)
  projects eight physical right-operand slices. Printer polarity XORs
  the output axes. Their unions cover all 8,388,608 selector assignments.
  Each slice uses at most 400,000 projection nodes and 2,000,000
  witness nodes. Back substitution retains each requested output cofactor
  before the projection discards its bucket. Words 39,391 and 39,394 use the joint rule
  that a left `<` permits any right operand, while other left operands
  require a right operand other than `j` or `v`.
  Word 59,036 excludes `j` because pairing it with byte 67 at 29,530
  halts without output on row 89,100. The packed source occupies all
  59,049 cells. The [native verifier](../../src/esolangs/languages/malbolge/tests/verify_decoder.py)
  checks 3,945,867 payload and marker combinations. Its acyclic instruction
  graph bounds every packed run by 9,101 commands. Replay with
  `uv run python -m esolangs.languages.malbolge.tests.verify_decoder`.
  The native replay derives both allowed glyphs at each lookup tap and
  the prefix seed from the decoder, including three copies of the short
  printer body emitted by the same rule as the active printers. It checks order `012` and
  all three guard paths for rejoining. The guards share an entry that
  jumps through the glyph and walks six cells to its pointer operand.
  Both dispatch guards return via the encrypted all-ones operand and
  the first walked cell that points to the return. The startup fills
  three hub families by walking the low pointer cells in residue order.
  Each used column has a companion glyph that jumps through the short hub.
  The high operand bands derive their return glyphs from the same hub families.
  The reset constants use the encoding period while C and D advance together.
  The startup derives its input folds, hub setup and dispatch routes directly.
  The payload walks can use default no-op glyphs in the reserved shadow lanes.
  Repeated rotations and readout writes derive their walks from pointer distances.
  The spill folds, payload selection and lookup returns use fixed pointer routes.

  Generation takes `O(T)` RAM work for `T` truth-table rows under the
  fixed 59,049-cell machine. Validation and constant detection scan the
  table. The positional route fills one cell per row pair. At seventeen,
  the essential-input analysis is linear and dropping one input copies
  alternate blocks once. The weight-class scan compares fixed-size blocks.
  The packed route reads four answers per prefix and writes each occupied
  payload word once. Its lookup relations and local operand choices have
  fixed machine dimensions and do not rescan the truth table. Layout
  setup and rendering add a machine-bounded cost, including on a cold
  build. The bound uses the fixed machine and word size.

  The source-dependent execution and workspace formulas in the
  [generator ledger](#generator-ledger) also give linear upper bounds
  in `T` at every supported arity.

  - **Execution is at most `2T + 18,198` commands.** The prefix count
    `E` fits within the source length, at most `2T + 13,340` by the
    ledger's size cases. The tail allowance `J` is at most 200 with short
    stubs, 124 with full stubs, and `9,101 − 4,243 = 4,858` with the packed
    decoder. Thus `E + J ≤ 2T + 18,198`.
  - **Workspace is at most `22T + 1,145,016` bits.** The initial store has
    59,049 words of at most 16 bits each, so `B ≤ 944,784`.
    Prefix writes satisfy `W ≤ E`, the stub flag `F` is at most one,
    and `bl(n) ≤ 5` for `n ≤ 17`. The ledger's workspace formula is
    therefore at most `944,784 + 11(E + J) + 54`.

- Ascenic: <a id="ascenic-bound"></a> worst-case source is `Theta(T**2)`
  characters for both the language and generator. Arguments rise strictly
  and are unary, so `L` lines cost at least `L(L+1)/2` characters, and a
  size-`S` program is one of at most 20 opcodes per line over `L <= sqrt(2S)`
  lines with arguments forming a partition of at most `S` into distinct parts:
  `2**O(sqrt(S))` behaviours, so some table needs `S = Omega(T**2)`. Blank
  lines and spaces add no behaviours. The threshold scan has at most
  `2T + 6n + 6` lines with arguments below `4T + 16n + 4`, the matching
  upper bound. Controls: `src/esolangs/languages/ascenic/tests/`.

  <a id="ascenic-execution"></a> Each line executes once. With `m`
  essential inputs and `p = m mod 2`, the forward and mirror prefixes
  have `6m+4p` and `6m+5-8p` lines, plus two per ignored input. Both
  scans add two lines per transition and five for the tail. A scan has
  at most `2**m-2` transitions since a fully alternating table uses
  only its last input. For `n >= 4`, reduced scans, constants and
  parity are below the claimed maximum.

  At even full arity, the mirror can beat the forward command count
  bound only with at most three missing transitions. For endpoint bits
  `a, b`, the mirrored prefix through ADD adds `36n+55+a-b`
  characters and raises every threshold base by `8+a-b`. With `d`
  missing transitions, reversal can reduce the sum of retained indices
  by at most `d(T-2)`, so the threshold lines gain at least
  `14(T-1-d)-2d(T-2)` characters. The tail scale rises by at least
  `7-2d`. The generator selects forward. At odd full arity, the mirror
  is three lines shorter than forward.

  Alternating with the last bit flipped to zero gives full arity and
  `T-2` transitions. For odd `n >= 5` its mirrored prefix saves
  `12n+48` characters, but the threshold bases coincide and every
  retained transition advances one index, adding `4(T-2)` characters
  before the longer tail. The generator selects forward for both
  parities. Exhaustion at arities one through three gives 7, 21 and 37
  commands, attained by `10`, `1101` and `10101000`.

  <a id="ascenic-size"></a> A prefix through ADD costs `P` characters
  including its terminal newline. With base `B` and retained
  transition indices `K`, the source costs
  `P + sum(2B+4k+34 for k in K) + 9(B+2max(K)+3)+36`.
  Summing the forward prefix gives `P = 24n² + (123n-16)/2 + b`
  at even arity and `P = 24n² + (171n+83)/2 + b` at odd arity,
  with `B = 8n-2+4(n mod 2)+b` for last bit `b`.

  At full arity, adding two omitted transitions preserves endpoint
  bits and raises both orientation costs. Thus one or two omissions
  suffice for an upper bound. Even arity selects forward in both
  cases. Its maximum omits index zero and ends in one. Two omissions
  with the same ending bit can at best omit indices zero and one.

  At odd arity, with one omission and both endpoints one, the bases
  coincide and the mirror prefix saves `12n+48`. The two costs cross
  at missing index `(T+3n+10)/2`. The adjacent integers give the same
  minimum, two characters below the mean, with both tails intact.
  The even one gives an odd change-of-phase boundary, making every
  input essential. Using endpoints zero lowers both costs. With two
  omissions, use the mean of the two orientation costs as an upper
  bound. Relative to the all-transition sum with endpoints one, each
  omission lowers that mean by at least `2B+32+2(T-2)`, since the
  two reflected indices sum to `T-2` and a base can fall by one.
  This is already below the single-omission optimum.

  A reduced forward scan has at most `6n` prefix lines,
  `B <= 8n` and `T/2-2` transitions. Strictly increasing arguments
  price its prefix at at most `30n²+117n`; summing the transition
  and tail costs puts it below the full-arity witness. Constants and
  parity have at most `2n+5` lines of argument at most `6n+7`,
  also smaller. Exhaustion at arities one through three gives
  84, 586 and 1457 characters.

- Line: <a id="line-workspace"></a> An inline tree over `m` kept inputs
  has at most `2^(m+1)-1` stroke frames. It writes at most `n` bit
  cells, with address widths summing to `n bl(n-1)-2^bl(n-1)+2`.
  The pointer and input cursor reach `n-1` and `2n-1`. From six
  inputs, a full tree uses at most two ops per stroke. Leaving out
  `r` reads saves `r` frame-index bits. The longest drain uses at most
  `r+4` ops, so its offset fits in `r+2` bits. Loaded trees through
  five inputs use at most `3n-2` ops per stroke. Their two constant
  routes fit the same bound from two inputs. Arity one through three
  is exhaustive. The fold has at most three frames per table row,
  two bit cells and a stroke offset bounded by `3n+3` commands, so
  its peak is smaller from four inputs.

  The full tree reaches each component bound on the all-ones input.
  The finite witness corpus keeps the full layout through fourteen
  inputs. From fifteen, let `B` be the least power of two at least
  `n` and `K=T/(4B)`. Take `K` distinct `B`-row words encoding
  `0..K-1`. Pair identical words in the first half, then pair every
  word with its cyclic successor in the second. The encoding retains
  all inputs. The first half owns all `K` arrivals, so the second
  half's left joins have mutually overlapping spans. The fold has
  width at least `16K-7` and height at least `2K` in layout units.
  The full inline box has upper widths `W1=26, W2=32` and
  `W(d+2)=2W(d)+2` by the alternating arm rotations. Its height
  is at most `W(d-1)` from two inputs. The inline area is below
  `240T`, while `K>=32B` makes the fold larger.

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

A `linear` row is within a constant of the worst-case optimum. A language with `c`
source characters has fewer than `c**(L+1)` programs of length at most `L`,
against `2**T` tables of length `T`, so some table needs
`L >= T / log2(c)` characters -- `T/3` for brainfuck's eight commands.
A row of any other class may exceed that floor by more than a constant.


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
- HQ9+ with headers: Divides one decimal literal by the power of two its
  reads square up.
- Modulous: Pushes the whole table as a string literal and spends the row index
  popping down to the answer.
- Movesum: Constants read and reset each input, then print and halt.
  Otherwise walks one rung per row, each a no-op test against the row index and
  a print, until the test and the print are two no-ops in a row.
- NOR machine: Packs the table into one integer by Horner's rule and halves
  it once per input by a NOR multiplexer; with no literals, even 0 and 1 are
  grown from the first input.
  `essential_inputs` drops ignored inputs; a constant table prints its bit.
- oBrainfuck: Lays the table on the tape and moves the head by each input
  bit across a zero block.
  `essential_inputs` drops ignored inputs; a constant table prints its bit.
- Onecode (Fergusq): A string store writes the essential table into consecutive
  cells. Input builds the address of the cell to print.
- Parenthesys: Constants read unprinted, then print their bit. Otherwise
  indexes a string literal with a nested Horner expression.
- Q-BAL: Shifts the projected table integer by the row index or sums the
  selected inputs for parity. Both return the remainder modulo two.
- Shakespeare: Packs the table into one number by Horner's rule and divides it
  by the power of two its reads build.
- SLOW ACV MAMMALIAN: Its read chain emits one fixed-width leaf slot per row
  whatever the table says.
- Sonata: Doubles a unary row index and strips one table entry per unit.
  `essential_inputs` halves degenerate tables; the fold discriminator in
  `test_schemes.py` records this exception.
- Thue: Makes the table its starting state and rewrites every adjacent pair down
  to one per input.
- Unsquare: Pushes one stack cell per row and pops the row index off the top.
  Pushes only cells the essential inputs address.
  `essential_inputs` halves degenerate tables; the fold discriminator in
  `test_schemes.py` records this exception.
- Whitespace: Pushes the table as one literal and divides it by `2**index`.
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
Each cell is a growth class and its argument: `linear` (size and time O(T)
for every table; the clause names the argument in twelve words or fewer),
`T log T`, `T**2` or `2**T`.  The Evidence column says what backs it:
`proved` (an argument for every table), `measured` (on the supported domain;
no invariant bounds it) or `lower bound` (the language forces it).  Exactly
the rows short of `proved` are open on size or time in the scaling audit.
Where a generator dispatches on table size, the cell describes the wide
route.  `tests/proofs/test_ledger.py` checks the grammar and
`tests/proofs/test_linearity.py` checks the column against the audit.

The Execution column is the generated program's commands to halt, worst
sampled row; the Workspace column is its peak written state in bits, every
top-level part of the VM snapshot the run ever changes, counted whole
(`scripts/benchmark.py`'s `WrittenState`), so read-only code is excluded and
a preallocated tape or a self-modified program counts.  `poly n` grows at
most x1.5 an input, `sqrt T` (an Execution class: `√T` up to a poly n factor)
at most x1.75, `linear` at most x2.15, and `T log T` (T cells of
`log T`-bit values) at most x2.5.  [Locality](#execution-locality) bounds
the commands from below. An `unmeasured` Execution cell marks an
exemption from the growth check. The audit can still report command counts
for these rows, and formula tests check their stated bounds.
`tests/proofs/deep/execution.py`
and `tests/proofs/deep/workspace.py` measure halting rows on parity tables,
and a `poly n` cell on a seeded dense table too: parity has n ANF terms and
can hide a generator's T-dependent work. The dense series runs to n=12; its
increments, which cancel fixed overhead, may grow at most x1.4 an input.
A `poly n` cell also names its mechanism, read from the generator. A cell
that opens `worst` gives a formula derived from the code and reached by some
table; `at most`, one never exceeded. `bl(x)` is the bit length of x, `L`
the program's length and `T` is 2^n. `residuals(n)` sums the distinct
subtable caps across the internal levels. `residuals_without_constants(n)`
excludes the constant subtables. See [ordered reads](#ordered-reads-without-retained-inputs)
for the level counts. `tests/proofs/test_execution_formulas.py` and
`tests/proofs/test_workspace_formulas.py` run the bounds at small n.

- Fargo's T-dependent work was hidden by parity.
- Forþ's T-dependent work was hidden by parity.
- INTERCAL's T-dependent work was hidden by parity.
- 6-5's T-dependent work was hidden by parity.
- Painfuck's `at most` formula is also proved for every n.

<!-- PROOF-STATUS:START -->

| Generator | Proof | Qualification | Scaling | Evidence | Execution | Workspace |
| --- | --- | --- | --- | --- | --- | --- |
| /// | parameterized lookup | binary-to-unary substitutions form the row index; fixed macros expand run sweeps before decoding one answer | linear: worst 76 (n=1), 95 (n=2), 107 (n=3), 5T/2+n+83 (n≥4) characters | proved | linear: worst 28 (n=1), 9T/2+n+21 (n≥2) steps | linear: worst (1-D)*(16n+32)+D*(8(L+max(0,S-15-P-2X,M*(S-bl(S)-P-2X+17K-48)))+56+120M) bits |
| 1 + i | tree | a node pushes its two child functions and B? invokes one; essential-input projection interleaves ignored B$ reads; two-bit tails derive arithmetic, parity uses an exact sum/power, and constants drain remaining inputs | linear: worst 9T/2 - 6 characters past n = 1: six a node | proved | poly n: worst 7 (n=1), 4n+4 (n≥2) steps: four a branch level, twelve in an arithmetic tail | poly n: worst 24 (n=2), 64 (n=3), 112 (n=4), 2n²+34n-61+bl(2n-1) (n≥5) bits: default frame, stack and input position |
| 3x | tree | — | linear: at most 13T+24n+3((n+1)bl(n)-2^bl(n)+1)+3weighted_bit_sum(n)+2 characters: the plain tree under fixed keys | proved | linear: worst L commands: the all-ones row enters every guard, no loop repeats | linear: at most n*bl(L)+bl(2n-1)+3G+2n+2K+6bl(n+min(G,floor(T/24)))+9+S+3(1+n+min(G,floor(T/24))) bits. G counts guards, K is the last key width and S sums the admitted key widths |
| 6-5 | finite lookup | shared trees within the label budget, positional or guarded walks otherwise; AND has one shared zero exit | linear: at most 20 (n=1), min(11T+6n-8,6n+19+(n+4)T/2+(n+6)min(T/2,2n-2)) (n=2..5), max(6T+17n+4,41n+460) (n=6..35), 7T+4n+12 (n≥36) characters: raced layouts | proved | linear: at most L + 6T + 3n commands: the walk's home loop reruns 3 commands a cell; other routes loop-free | linear: worst 2T + 6n + 6 + bl(n) + bl(L) bits past n = 6: a tape of 2T cells |
| A Painter Ant | parameterized lookup | embedded inputs select a corridor or lane and walk by weight; the endpoint clamps a constant run, and all-but-one thresholds build westward from the mirror wall | linear: worst 13T/2 + 3n - 2 characters | proved | linear: worst 2S commands: two passes over the S non-whitespace characters | T log T: worst 25 (n=1), 43 (n=2), 83 (n=3), (3n+7)T/2+2n+13 (n≥4) bits bits |
| AddSubJump | finite lookup | essential raw-byte Horner index; fixed hot data slots; packed cells selected by a self-modified operand | linear: worst min(P,R) characters. P packed, R shared tree, exact n=6..9 | proved | linear: worst C*(n+1)+(1-C)*((11n+4)floor(T/n)+11T+10n-15+min(1,max(0,n-9))) commands. C marks direct constants | linear: worst C*(A+bl(4(n+1))+bl(49n)+1+max(5,bl(4n))+bl(n))+(1-C)*(bit_sum(20n+230+2ceil(T/n))+ceil(T/n)*(n+bl(20n+229+ceil(T/n)))+3n+5bl(n)+(5n+54)*bl(20n+216)+(15n+160)*bl(20n+229)+2bl(20n+229+2ceil(T/n))+bl(20n+212)+23) bits. C marks direct constants and A counts their initial nonzero cells and addresses in bits |
| Algebraic Programming Language | tree | bounded shared frames and arithmetic complement twins; base-26 names are unbounded | linear: at most 10T+4n+6 (n=2..14), 21T/2+4n+6 (n≥15) characters | proved | linear: worst C*(4n+3+4J) + (1-C)*(max(21,ceil(65n/2)-21)+K+2min(K,3n+1)) commands: constant C, negation J, K definitions | poly n: at most C*(179n+400+bit_stride(2n+15,7,max(0,n-2))+bit_stride(2n+16,7,max(0,n-2))+bit_stride(2n+20,7,max(0,n-2))+bl(2n-1)+bl(2n+3)+bl(2n+13)+bl(2n+7)+2bl(2n+8)+bl(2n+9)+bl(2n+11))+(1-C)*((4n+3)*(198+8bl(L)+3bl(2L+2))+(6n+5)*(bl(2L+2)+114)+65n+bl(L)+bl(2n-1)) bits. C marks expressions without shared definitions |
| Alight | finite lookup | inputs folded into a row index by Horner's rule; the table is a string literal read with `at` (two rows to a character from n=6), so the program has no branches | linear: worst T+16n+38+digits(48(T-1)) characters: one literal | proved | poly n: worst 2n + 5 commands, n Horner reads and one `at` | poly n: worst 15n+19+bl(L-4)+2bl(n)+8digits_sum(max(0,n-25)) bits |
| Aprknia | tree | ASCII parity leaves retain quotient24; a fresh zero pair and pop select the zero arm, whose reset is omitted only for a statically exact-zero exit | linear: worst 23 (n=1), 81T/4-19 (n≥2) characters characters | proved | poly n: worst 18n + 5 commands | poly n: worst 39 (n=1), 34n-6+bl(81T/4-19)+bl(n) (n≥2) bits bits |
| ArrowQueue | parameterized lookup | one stage per input doubles the queued markers and adds the bit (Horner), and the count selects one of `2**n` constant-size cascade stages | linear: worst min(6(2T+6n+7),A,B,C,D) cells: cascade and four folds | proved | linear: at most 52 (n=1), 78 (n=2), 124 (n=3), 11T+32n+92 (n≥4) commands commands: exact n≤3 | linear: worst T + 13 + bl(T+6n+8) bits: queue, position, heading, halt and dump flags |
| artppeice | linear lookup | the first pass routes w counter words per set input of weight w into a counter queue closed by P, beside a queue holding the essential inputs' table, a word an entry; each pass dequeues both in step, and only the closing P puts a word ahead of the entry's digit in the printed queue, whose first word is then dropped; an ignored input is a bare read | linear: worst 6T+59n+113ceil(n/4)+208 (n=1..6), 4T+59n+207ceil(n/4)+179+4(26digits_sum(floor(n/26))+(n-26floor(n/26))digits(floor(n/26))-min(n,26)) (n≥7) characters characters; full positional lookup | proved | linear: worst (3n+8)floor(T/ceil(n/4))+6T+3n+8 (n=1..6), (3n+7)floor(T/ceil(n/4))+10T+3n+8 (n≥7) commands commands; full counter followed by the empty dequeue | linear: worst 127 (n=1), 8(4T-4ceil(n/4)+3n+7)+bl(3n+7+6ceil(n/4))+bl(2n) (n=2..6), 8(3T+3n+6)+16(26digits_sum(floor(n/26))+(n-26floor(n/26))digits(floor(n/26))-min(n,26))+bl(3n+6+10ceil(n/4))+bl(2n) (n≥7) bits bits; named queues and cursors |
| Ascenic | tree | Horner's rule by built `-2` constants makes each row's code `base + 2r`; `LT t`, `ADDS` at every change point adds 1 to codes below `t`, so the parity answers; straight-line code, no jump; named parity sums retained bits instead | T**2: worst 84 (n=1), 586 (n=2), 1457 (n=3), 2T²+(16n+44+6(n%2))T+(48n²+203n-98+(36n+95)(n%2))/2 (n≥4) characters characters ([proof](#ascenic-size)) | lower bound | linear: worst 7 (n=1), 21 (n=2), 37 (n=3), 2T+6n+1+4(n-2floor(n/2)) (n≥4) commands commands ([proof](#ascenic-execution)) | poly n: worst C*(bl(2n+1)+1+S)+(1-C)*max(bl(2T+7n+3-2floor(n/2))+max(bl(10n-7-4floor(n/2))+bl(10n-5-4floor(n/2))+n+1,bl((2T+10n-3-4floor(n/2))*(2T+10n-2-4floor(n/2)))),bl(2T+5n+5+2floor(n/2))+max(bl(8n-5)+bl(8n-3)+n+2,bl((2T+8n+1)*(2T+8n+2))))+bl(2n-1)+16(1-C) bits. C marks a constant and S marks the extra LT flag for constant one |
| B-tapemark | finite lookup | the blank grid is the table, one mark per row copied by `*`; a stage per input walks the mark pointer by that input's weight and `+` prints the mark it lands on; the bounds are the default swap_marker dialect's — the old dialect shares the constructions with each stage rebuilt for its own round-trip landing, a constant number of cells and steps per stage apart, and is verified by execution (each dialect over the generated corpus at n=1..4, plus a swap witness distinguishing the readings) rather than re-derived | linear: worst A cells: smallest of four layouts with all inputs essential | proved | linear: worst steps: longest all-zero row after the layout race at each essential arity | T log T: worst W bits through n=8: peak snapshot over rows of the chosen layout. At most B thereafter |
| Back | parameterized tree | last tested bit held in cell n; equal halves pass; pair finishers compute the answer | linear: worst ((25+15(n-2⌊n/2⌋))·2^⌊(n-6)/2⌋-4)((40+10(n-2⌊n/2⌋))·2^⌊(n-6)/2⌋-8) (n≥8) cells: pair comb through n=7 | proved | linear: worst C*(3n+2+B)+(1-C)*13 (n=1), C*(3n+2+B)+(1-C)*27 (n=2), C*(3n+2+B)+(1-C)*(max(T/2,6n+1)+T/2+3n+6) (n=3..7), C*(3n+2+B)+(1-C)*258 (n=8), C*(3n+2+B)+(1-C)*469 (n=9), C*(3n+2+B)+(1-C)*(max(3T/4+1,6n-1)+3T/4+3n+7) (n≥10) commands. C constant B, bounds past n=9 | poly n: at most n+bl(n)+C*(3+bl(3n+B))+(1-C)*(7+max(bl(6n-2),n)+bl(3n+4)) bits: C marks the constant B |
| Balik | tree | nested boxes test one input cell each with a splitter that also merges, since the tested cell is unchanged; a constant subtable is one leaf; two leaf children share the splitter row; a final identity cofactor prints its unchanged input cell | linear: nested boxes, odd inner levels side by side | proved | sqrt T: worst 19 (n=1), 40 (n=2), 69 (n=3), (34+10(n-2⌊n/2⌋))·2^⌊n/2⌋+7n-40+2(n-2⌊n/2⌋) (n≥4) commands | poly n: worst 12 (n=1), n+3+bl(n)+bl(2n-1)+bl(28*2^(floor(n/2)-1)+3n-16+6(n%2))+bl((10*2^(floor(n/2)-1)-4)(1+n%2)-1) (n≥2) bits bits |
| Befunge | exception | one-row nibbles through eight essential inputs, six-bit ASCII above; ships through thirteen inputs; finite source space excludes some sixteen-input tables | linear: worst 80(⌈(5n+64)/78⌉+⌈T/480⌉) (n≥9) cells; six-bit packed | proved | unmeasured: worst max(2n+23,4n+10) (n=2..8), 5n+67 (n≥9) steps; packed through n = 13 | poly n: worst 18+bl(max(2n+18,4n+10))+bl(2n-1) (n=2..8), 2n+bl(2n-1)+23 (n≥9) bits |
| BFStack | minterms | zero-based byte index; a guarded decrement ladder applies answer differences on unwind | linear: worst 7T + 54n + 46 (n=3..8), 2333T/256 - 62 (n≥9) characters | proved | poly n: at most 64n+2300 | poly n: at most 2n+32+bl(n)+(n+258)bl(L) |
| Bifunge | tree | folds each ASCII digit to one bit, then walks an alternating-axis tree in reverse input order; every leaf emits one byte and halts | linear: worst 8*2^⌊n/2⌋*(15n+18*2^⌈n/2⌉) text cells; one rectangular tree and an input strip | proved | sqrt T: worst 15n+2*2^⌊n/2⌋+18*2^⌈n/2⌉-1; the same distance to each leaf | poly n: worst 2n+34+bl(n) bits; coordinate, heading, stack and byte buffers |
| Bitdeque | parameterized lookup | head/tail discards leave the indexed entry in the deque | linear: at most 98 (n=1), 155 (n=2), 266 (n=3), 372 (n=4), 93+20n+digits(4n+26+2S)+2max(37,23+2digits(4n+26+2S))+(13+digits(4n+26+2S))S (n≥5) characters, exact n≤4: shared-tree token bound | proved | poly n: worst 7n + 10 commands past n = 2: prelude, load 2n, four a level, leaf n + 8 | poly n: worst n+2+bl(C*(3n+2+I)+(1-C)*(4n+27+2S)) bits. C marks constants, I marks their inversion and S is the shared tree count |
| Bitwise Cyclic Tag | parameterized lookup | the table is the program, one seven-bit cell per two rows; each embedded bit above the lowest appends three walk zeros per unit of its pair index, the lowest two, and a cell consumes exactly three whichever of its row bits is a delete or an operand, so the zeros carry the program pointer to the indexed cell and the held-back sentinel arrives there to fire its first or second row; the trailing `00` consumes the answer it just appended, without which a 1 would cascade into the cells below | linear: worst 13T/2+2n+3 characters: seven per two-row cell, reads six a unit | proved | linear: worst 19T/4 + n + 2 commands past n = 2: input segments, then the walk | linear: worst 12T + 17 + bl(13T/2+n) bits: live queue of 3T/2 + 1 bits, answer, head and completion latch |
| bit~ | linear lookup | the first input partitions planting, then weighted jumps and one selector address a three-cell pair | linear: worst 3T+19n+115 characters past n = 3: minority planting | proved | linear: worst 19T/4+18n+123 commands past n = 3: planting and two walks | linear: worst 3T/2+50+bl(3T/2+42)+bl(3T+19n+115)+bl(n) bits past n = 3: tape and cursors |
| Bleh | tree | shared-node functions match their input; short nullary reads validate both Boolean bytes before returning; constants use a flat read/print block | linear: worst B-A-P-R characters, n=3..23; at most beyond | proved | poly n: worst 17n+5 - C*(5n-1) steps: C marks statement reads | poly n: worst 128n+1+bit_sum(2n)+max(128,8max(floor((n+5)/5),1+digits(n-1))+max(16,bl(2n)+1))+max(105,8max(floor((n+5)/5),1+digits(n-1))+max(17,2bl(2n)+1))+bl(2n)+bl(n) bits: heap, control, continuation and cursors |
| Blindfolded Arithmetic | linear lookup | the table read at its essential inputs is one integer built by Horner in base8 (parity: base16), and each essential bit of the row divides it by 1 or by 2^2^m, squared up from 2, so its low bit is the answer | linear: worst 3T + 6⌈T/3⌉ + 48n + 47 characters: six an instruction | proved | linear: worst ⌊T/2⌋ + ⌈T/3⌉ + 8n + 8 commands: half the rows set, run once | linear: worst 2T + 6 + bl(⌊T/2⌋+⌈T/3⌉+8n+5) bits past n = 2: b and its even copy |
| Boolfuck | tree | complete bytes feed a flip-only tree, normalized AND/XOR gates, an affine accumulator or unary population count; zero subtrees omit dead flags | linear: worst 162 (n=3), 35T/2+2n²+12n-23 (n=4..7), 35T/2+2n²+12n-11 (n=8), 85T/8+2n²+10n+39 (n≥9) characters (n=3 attained) | proved | poly n: worst 4n^2 + 30n + 8 commands past n = 1: the all-ones row of a symmetric count table | poly n: worst bl(L-1)+bl(n)+(1-C)*bit_sum(n)+S*(12+bl(n))+13C+(1-S-C)*(max(12,bl(2n-3)+11)+n+bl(2n)) bits: C drains, S counts symmetrically |
| BracketOnly | tree | a lazy if selects its arm from the input character modulo two; the tree returns a bit to one output call | linear: worst 126T-84; parity reaches a full tree | proved | poly n: worst 90n+33; all-zero parity visits n tests and a zero leaf | poly n: worst (n+4)(n+5)+7n+26+bl(n) bits; parity reaches the last remainder with every test live |
| brainfuck | tree | zero-pruned decision tree; residuals defer through level flags; affine tables stream; literal conjunctions/disjunctions share ASCII normalization | linear: at most 35T/2 + 55n + 25 characters: the plain tree | proved | poly n: worst 75n + 49 commands past n = 2: OR all-zeros | poly n: at most max(7n,2n+7) + bl(2n) + bl(n) + bl(L) bits |
| BrainIf | tree | equal cofactors share a layered DAG; OR uses a known-zero entry and holds its answer beside trailing input; width requests retain tree/spatial readers | linear: at most 885 (n=1), 983 (n=2), 1166 (n=3), 1361 (n=4), max(28n+770,52N+840+A+2digits(4N+54)) (n≥5) characters, exact n≤4: layered DAG before fall-through | proved | poly n: worst 55 (n=1), 58 (n=2), 62 (n=3), 4n+49 (n≥4) commands commands for the default layout | poly n: worst C + bl(R) + bl(n) bits: cell storage C and R lines |
| Bruijndejx | tree | decision tree of ? reads through a two-way read combinator Q and an ignoring read I; multi-parent residuals are named once, raced arithmetically against the inline tree | linear: at most 5T + 23 characters | proved | poly n: worst 10n+3+max(0,n-2) commands | poly n: at most 9*bl(2L) + bl(n) + 5 bits |
| Bytemap | linear lookup | answer bytes are paged 128 rows by 16 columns. A one-column strip prints down. Wider strips patch the selected row's print with the left offset to its answer byte. Page headers decrement and carry the counters. A short-hop binary tree covers headers wider than eight bytes | linear: at most 13T/2 + 100n + 520 (n=1..59), 20000T (n≥60) characters | proved | linear: at most 4n + T/200 + 30 (n=1..59), 4n+T/200+40+8*2^⌈n/2⌉+10n+16 (n≥60) commands | poly n: at most 60n + 40 (n=1..59), 60n+40+16(n+2)^2+1024 (n≥60) bits |
| Caballo | tree | the inputs are the initial stack; selectors `dp` (keeps a 1 and pops it), `(p+dp-)` (keeps a 0 and pops it) build a tree leaving an empty stack of weight 1 on each 1 row, a 0 subtable no branch and a constant 1 its pops; `(i+-)` beside n pops makes that `[1]` and the 0 rows `[]`; more ones than zeros builds the complement; equal halves pop untested | linear: worst 33T/4 + n - 4 characters past n = 1: parity | proved | poly n: worst n^2 + 12n + 6 commands past n = 2: a skipped dp chain, 2 a level | poly n: at most (n+1)(n+2)/2 + 51n + 82 + bl(n) + (3n+3) bl(⌊2L/5⌋) + (n+1) bl(n+3) bits: nested frames |
| Chicken | finite lookup | the essential input bits fold into a row number from a pushed base, and a load reads that row's chicken count back out of the program's own lines | linear: worst 366n-2+4n(n-1)+ceil((20n+8)/T)(8+T/2)+T+7min(T-1,T/2+8) (n=1..5), 2769 (n=6), 366n-2+4n(n-1)+ceil((20n+8)/T)(8+T/2)+T+7min(T-1,T/2+8) (n≥7) characters characters | proved | poly n: worst 9n+1 (n=1..4), 9n+3 (n≥5) commands commands | linear: worst 19n+T+bit_stride(10,1,n)+T/2*ceil((20n+8)/T)+bl(10+ceil((20n+8)/T))+116+bl(T/2*ceil((20n+8)/T)+T-2)+bl(10n+4) (n=1..4), 19n+T+bit_stride(10,1,n)+T/2*ceil((20n+12)/T)+bl(10+ceil((20n+12)/T))+121+bl(T/2*ceil((20n+12)/T)+T-2)+bl(10n+6) (n=5..7), 19n+3T/2+bit_stride(10,1,n)+5+max(120,bl(n-1))+bl(3T/2-2)+bl(10n+6) (n≥8) bits bits |
| Circlefuck | linear lookup | the tape is the program, so the table is its tail past the `@` that stops the run, entry 0 abutting the index digits at the ring's end; `}` deletes the cell under the pointer and slides the digits down into it, so counting the index out against one `}` apiece leaves the entry it names under the pointer | linear: worst T+52n+10 (n=1..2), T+34n+27+(⌈n/7⌉-1)(149(⌈n/7⌉-2)+4(n-7⌈n/7⌉+79))/2 (n≥3) characters: table, clamped reads, digit-cell walks | proved | linear: worst (2n+13)T + 68n + 232 + 2U + min(1,max(0,3-n))*(26n-143) commands to n=7, with U the reader tally | linear: worst B+bl(R-1)+bl(A)+bl(n)+1 bits. B is initial tape bits, R its extent and A the data origin |
| Circuit Diagram | tree | complete residual folds with counted atomic definitions or the primitive pool cap | linear: at most ((1176-408(n-2⌊n/2⌋))·2^(n-4-⌊n/2⌋)-8n-64)^2 cells past n = 8: H-tree pool caps it | proved | poly n: at most 2n + 1 commands: atomic muxes only shorten paths | linear: worst C*(n+2)+(1-C)*(7T/2+2n-5+min(1,max(0,n-7))*(7T/2-4)) bits. C marks direct constants |
| Clockwise | linear lookup | the ring is the table: one `!` per entry in a countdown row, and the index in the accumulator picks which one it is zero on, turning the pointer down that entry's own column; seven `.` an input build the index by Horner's rule, doubled between inputs by a two-row gadget that spends the accumulator as distance and buys back two per unit | linear: worst 25T + 40n + 20 cells past n = 1 | proved | linear: worst 16T + 22n + 2 steps past n = 1: the pointer's path to the last row | poly n: worst 57n + 54 + bl(5*2^n+8n+3) bits: 7n-character queue |
| Codesick | tree | shared nodes append non-bit ASCII names; a bit-name substring test deletes the last unread bit; frequency buckets assign short names to frequent references | linear: at most (69+10digits(residuals_without_constants(n)+1))residuals_without_constants(n)+45 characters for n>=2: bounded label widths | proved | poly n: worst 3n - 1 steps: three a level, two at the last | poly n: at most 26 (n=1), 17n+9 (n=2..6), 17n+8 (n=7..8), 17n+16 (n=9..11), 17n+15 (n=12..15), 17n+23 (n=16..19), 16n+8+8digits(residuals_without_constants(n)+1)+bl(3residuals_without_constants(n)+1) (n≥20) bits bits, exact n≤19 |
| Collatz Multiverse | finite lookup | an array subscript may name `lineNumber`, so a cell is addressed by the number of the line that writes it | linear: at most 411+31(T/4)+((T/4)-3)min(1,max(0,(T/4)-3))+76min(16,(T/4))+13(min(1,(T/4))+min(5,(T/4))+min(11,(T/4))+min(15,(T/4)))+23n+digits_sum(n)+Q+39max(0,n-3)+2digits_sum(max(0,n-3))+power2_digits_sum(max(1,n-2))-1+2(digits(max(0,n-3))+max(0,3-n)+digits(n-2)+digits(n-1)) characters past n = 2: one line per cell | proved | linear: worst C*(n+10)+(1-C)*(T/4+3n+4min(16,T/4)+2K+10) lines past n = 2: constant C, one step per line | T log T: worst bl(2n-1)+C*(132+bl(n+11))+(1-C)*(R+A+D+bl(T/4+3n+4min(16,T/4)+2K+11)) bits past n = 2: R registers, A and D arrays |
| Container | finite lookup | the table is the prefix sum of its own steps, summed against a row counter that is live for one tick | linear: at most 75+63n+7T+digits_sum(2n+1)+digits_sum(2n)+digits_sum(2n+2)/2+digits(2n-1)+4digits(2n)+power2_digits_sum(n)+digits_sum(T) (n=1), 72+59n+13T/2+digits_sum(2n+1)+digits_sum(2n)+digits_sum(2n+2)/2+digits(2n-1)+4digits(2n)+power2_digits_sum(n)+digits_sum(T) (n≥2) characters: threshold build | proved | poly n: worst 2n+2-2C commands. C marks the threshold route in default layouts | linear: at most C*(145+3bl(n))+(1-C)*(V+max(bl(E),1)+2bl(2n+2)) bits. C marks the threshold route, V counts stored bits and E is the exit value ceiling |
| Crement | parameterized tree | each input is the data of one jump in a two-line tester; a node patches the tester's two targets to its children and jumps in, a folded subtree targets the shared self-jump or the line past the end, and a subtree already emitted at its level is targeted, not repeated; parity and thresholds reuse initial tester targets without revisiting a level | linear: worst 5+8min(1,n-1)+min(1,max(0,n-2))(3P+2n-10) lines: subtree ids | proved | poly n: worst 4 (n=1), 5n+2 (n≥2) commands over halting rows, shared self-patching testers | linear: worst C*O*(11n+10+2bl(n+1))+(1-C)*(2bl(N)+32+bl(2n+3)+2n(10+bl(N-1))+P*(28+3bl(2n+2)+2bl(N-2))) bits. C selects native constants, O their output |
| CV(N)(C) | tree | the shared exit loads the last syllable address in binary, and a subtree already emitted at its level is entered by climbing the accumulator to its syllable and `j`, where shorter | linear: at most 86 (n=1), 102 (n=2), 134 (n=3), 17T/2+5+8(bl(17T/2+59)+1) (n≥4) characters characters: exact through n=3 | proved | sqrt T: at most 77 (n=1), 80 (n=2), 83 (n=3), 17+4n+3(n-1)+isqrt(2L*(n-1)^2)+8(bl(17T/2+59)+1) (n≥4) commands commands: exact through n=3 | poly n: worst bl(K)+bl(2n-1)+C+(1-C)(24+bl(S-1)) bits: K commands, S syllables, C constant |
| Cyclic tag | parameterized lookup | weighted zero padding advances the cyclic rule pointer to the indexed answer; the next empty rule deletes it; AND/NOR use a two-bit marker and a single one continuation | linear: worst 3T + 2n + 1 characters, weighted padding | proved | linear: worst T+n+2 (n=1..2), T+n+3 (n≥3) steps: indexed marker and at most one named continuation | linear: worst 8T+9+bl(T+n) (n=1), 8T+17+bl(T+n) (n≥2) bits: queue, production pointer and output latch |
| Decleq | tree | zero edges enter fixed print gadgets directly; admitted symmetric thresholds use fall-through chains | linear: at most 2(3⌈(n+18)/3⌉)+17n+12residuals_without_constants(n)+16+digits(3⌈(n+18)/3⌉)+2digits(n+17)+(2residuals_without_constants(n)+5)max(2,digits(3⌈(n+18)/3⌉+6n+6residuals_without_constants(n)+9))+3max(2,digits(3⌈(n+18)/3⌉+6n+6residuals_without_constants(n)+12))+3 characters: six cells per distinct subtree | proved | poly n: worst 50n + 96 commands past n = 1: 47 passes, n - 2 copy jumps | linear: worst B+bl(R)+bl(n)+5n+5-C*(5n-1) bits. B is program bits, R is memory extent and C marks direct constants |
| Dimensional | linear lookup | a bare `>` takes its dimension from the byte it stands on, so `d>` is a pointer displacement by the bit read: the index is a coordinate, doubled between reads by a two-loop `{`/`}` gadget, and it addresses one painted cell an entry along dimension 1 | linear: worst 2T + 20n + 42 characters: two per entry | proved | linear: worst 11T + ⌊(2T+1)/5⌋ - 4n + 43 commands past n = 3: zero runs of nine loop | T log T: worst (n+4)T+n(n-1)/2+5n+13+bl(2T+20n+40)+bl(2n-1) bits |
| EGL | finite lookup | a boustrophedon table has three rows per block; binary weights walk horizontally or down whole blocks; symmetric tables retain the count reader | linear: worst 3T+25n+digits(T)+8 (n=1..3), 2T+2^⌊(n+3)/2⌋+5·2^(n-⌊(n+3)/2⌋)+25n+digits(2^⌊(n+3)/2⌋)+digits(3·2^(n-⌊(n+3)/2⌋))+1 (n≥4) characters: T-1 painted ones | proved | linear: worst (1+R)*(3T+85n+5+min(1,max(0,n-3))*(-T+2^min(n,floor((n+3)/2))+5T/2^min(n,floor((n+3)/2))-6))+R commands. R marks wrapping with additional no-ops | linear: worst (1-G)*(3T+2n+10+bl(L-digits(T)-3)+bl(L-digits(T)-9))+G*(W*H+7+2max(1,bl(W-1))+2max(1,bl(H-1))+2max(1,bl(B)))+2bl(n) bits. G marks the grid route, W and H are its dimensions, and B counts body characters |
| Eval | linear lookup | fixed reversed stack order selects the indexed row | linear: worst 2T+7n (n=4..5), 7T/4+9n+1 (n≥6) characters, unwrapped | proved | linear: worst L+1 commands past n=3, unwrapped source with all-one setters | linear: worst 8L+T+n+1+bl(L) (n=4..5), 8L+T+2n+1+bl(L) (n≥6) bits, frame and staged Boolean cells |
| Fackward | tree | a level is a block whose quiet pass reads the bit; `/ c 49` makes it 0 or 1, that many `~` swap the two child blocks, `!` drops one and `)` runs the other; equal halves fold | linear: worst 43T/2 - 29 characters past n = 1: block per node | proved | poly n: worst 38n - 26 steps: 38 a level, the last printing what it reads | linear: worst 159T - 225 + bl(n) bits past n = 1: the two stacks hold the program's tokens |
| FALSE | tree | shared trees and formulas split in input order; a conditional packet tree uses a signed 32-bit multiplication to extract the answer | linear: at most 9T/2+5n-7 characters past n = 3: to n = 15 | proved | linear: at most 9T/2 + 5n - 7 commands past n = 3: formula budget or diagram path | poly n: worst A*(34n+67+2bl(L)*(n+2))+B*(5n+6+2bl(L)*(S+2n+2))+C*(n+1+2bl(L)*(S+n+2))+(1-A-B-C)*(6n+1+2bl(L))+bl(n) bits. A/B lookup routes, C cached lambda, S non-input stores |
| Fargo | tree | finite folded layout | linear: at most 15T/2-1+weighted_bit_sum(n-1) (n≥2) characters: inline Davio form | proved | linear: at most 9T - 5 commands: each expanded token runs once, plus 2 per executed shared-name reference | linear: at most 18D + (1-D)*(16(L-3)+bl(L)+11) bits: D marks the false literal |
| Fish | finite lookup | the inputs form a Horner index and g fetches its table bit; six-bit packing is used only while float coordinates remain exact | linear: worst 18n+18 (n=2), 15⌈(4n+43)/15⌉+6+⌈T/6⌉ (n=3..45), 2^bl(4n+39+4bl(4n+43))+6+⌈T/6⌉ (n=46..55), 2T (n≥56) cells | proved | poly n: worst 9n+9 (n=2), max(6n+9,4n+43) (n=3..55), 9n+9 (n≥56) commands | poly n: worst 15 (n=1), bl(9n+8)+n+13+bl(n) (n=2), bl(4n+42)+bl(n)+1+max(2max(7,n)+3,bl(15ceil((4n+43)/15))+71) (n=3..45), bl(4n+38+4bl(4n+39+4bl(4n+43)))+bl(n)+2n+4 (n=46..55), 123+bl(n) (n=56..100), n+13+bl(9n+8)+bl(n) (n≥101) bits bits |
| Flipscript | tree | the quasi-reduced decision diagram, root level first; a node reads one input line and jumps X*A+B lines down to its zero or one child; a constant child lands in a run of reads ending in its output | linear: at most 17T + 64 characters | proved | poly n: worst 2n + 3 commands: one read and one computed jump a level | poly n: worst 96+bl(R)+bl(2n) bits for R source lines |
| Flowchart | finite lookup | a pair of answers per deque, and the input walks the deque cursor to the pair it wants | linear: worst 20T+16·2^⌊n/2⌋+12·2^⌈n/2⌉+72n+14 cells past n = 1: two rows | proved | linear: worst 2T+2·2^⌊n/2⌋+2^⌈n/2⌉+9n+1 nodes past n = 1: preload T plus T - 1 runs | T log T: worst 4E+C+31+⌊n/2⌋+T+(⌊n/2⌋-1)·2^⌊n/2⌋+2bl(n) bits past n = 2: exit memory, deques and counters |
| Forþ | tree | the tree tests the essential inputs; an ignored one is read and dropped as `,0*+` | linear: at most characters: scope and distance costs over essential arities | proved | linear: at most 6T + 12n - 3 commands: define each scope once; dispatch ends in literals or bit arithmetic | T log T: at most (2n+364)T + 43n + 2bl(n) bits: frame text and the scope dictionary |
| FRACTRAN | parameterized tree | the bits are the exponents of `n` primes in the starting value, a decision tree gives equal subtables one state prime, and the first-match rule is the else-branch | linear: worst C = Σ_{d<n} min(2^d,2^2^(n-d)-2^2^(n-d-1)) states, O(log T) digits | proved | poly n: worst n+1 commands, one per level or unread set bit plus the halt | poly n: worst B+P+n+2+C*(3V-1) bits. B sums input prime widths, P is state prime width, C selects constants, V their value |
| Freestajlo | linear lookup | the table is one `"` literal, row 0 on top, and Horner's rule over the essential inputs gives the depth `&` copies; past the crossover the literal packs six entries a character and the row splits into that depth and a bit | linear: worst min(T + 4n + 1, ⌈T/6⌉ + 4n + 19) characters | proved | poly n: worst 4n (n=1..4), 4n + 17 (n≥5) commands; includes decode | linear: worst 6T+7+bl(T+2)+bl(4n)+bl(2n) (n=1..4), bl(2n)+max(108+bl(2n+8),7+7⌊T/6⌋+bl(⌈T/6⌉+4)+max(16,2n+3)+bl(4n+18)) (n≥5) bits: literal stack |
| Grapheme | linear lookup | the whole table is one int-mode literal read in base 10, and after the seeded first factor each `W` squares an accumulator and doubles it on a 0 (or a 1), which is Horner's rule for the complemented (or direct) index, so the accumulator is exactly the power of two that `R` shifts the wanted entry down to bit 0 | linear: worst 17n+15+digits(2^T) characters from n=2 | proved | linear: worst 17n+15+digits(2^T) commands from n=2: one per program character | linear: worst 16D+136n+155+bl(17n+D)+max(T+14,2B+2)+bl(2n)+bl(n) bits from n=2 |
| GridScript | linear lookup | one pass over collocated nodes: the table read at its essential inputs is split onto the buffer as decimal chunks of 2^m bits (m <= 4, shortest among safe indexes); the high inputs double an index in the dataspace, REMOVE THIS POSITION loads its chunk, each low input divides it by 1 + bit(2^w - 1), and v - 2floor(v/2) is printed; wide indexes use a pairwise buffer reduction on Boolean leaves. For parity, sum essential inputs and print the remainder modulo two | linear: worst 3T/8 + 55n + 185 (n=1..4), 3T/8 + 55n + 171 (n=5..31), 160T+(55+bl(n))n+64 (n≥32) characters, n=4..8 | proved | linear: worst 9 (n=1), 4n+7 (n=2..4), 3n+10 (n=5..35), 7T+n-2 (n≥36) commands commands including both tracer moves | T log T: worst 184 (n=1), 153+2bit_sum(4n+6)+2T+bl(2n) (n=2..4), 168+max(17,n-4)+2bit_sum(3n+9)+5T/2+bl(2n) (n=5..35), 156+n+2bit_sum(7T+n-3)+V+bl(2n) (n≥36) bits bits, with V pricing the wide tree's input variables |
| Home Row | parameterized tree | — | linear: worst 6T + 10n + 61 characters past n = 1: pairs | proved | linear: worst 9T/2 + 10n + 284 commands past n = 1: every leaf run, all weights set | poly n: worst n + 49 + bl(6T+10n+61) bits past n = 1: index cell, four flags, cursor, a -1 setter cell |
| Hot | tree | the table is a tree of Church pairs, equal halves folded to `K`, applied to the bits that one fixed reader stage an input takes from `A` | linear: worst 27T/2 + 73n + 86 characters past n = 1: pairs | proved | poly n: worst 35n+45 - C*(31n+42) rewrites: C marks the constant spine | linear: worst C*(32n+27)+(1-C)*max(88T+232n+235,132T+24n-53)+bl(n) bits. C marks the constant spine |
| HQ9+ with headers | linear lookup | constant tables consume every input and print directly in n+2 commands; otherwise the table is one decimal literal, divided by the power of two the reads square up, and `[~::]` tests the quotient's parity | linear: worst 317+2n+digits_sum(n+1)+digits((114n+111)%1024+43)+digits(2^T-2) characters | proved | poly n: worst 4n + 9 commands | linear: worst 3T + 4 + bl(4n+10) + bl(2n) bits: variables, op index and reads |
| Inject | finite lookup | one table block halved by `O(n)` conditional substitutions | linear: worst T+71n+29+2R+3(max(0,n-49)+max(0,n-2753)+max(0,n-143361))+2(max(0,3n-49)+max(0,3n-2753)+max(0,3n-143361)) characters past n = 4 | proved | poly n: worst 9n+10 - C*(8n+3) commands: C marks the literal tail | linear: worst C*(64n+144+bl(n+7)+bl(n+1)+bl(n+3)+bl(n+4)+bl(n+6))+(1-C)*(8T+512n+184+16R+bl(12n+10)+bit_stride(n+1,2,4n)+bl(9n+1)+bl(9n+3)+bl(9n+4)+bl(9n+6)+bl(9n+7)+bl(9n+9)+bit_stride(9n+10,3,n)+bit_stride(9n+12,3,n))+bl(2n)+bl(n) bits. C marks the literal tail and R counts halving regex characters |
| INTERCAL | parameterized tree | equal-width inputs feed a reduced diagram; actual folded expressions and coupled selector/mask aliases are shared where shorter | linear: at most 24T+2weighted_decimal_sum(n)+11n+digits_sum(n+1)+2digits(n+1)+4⌊(n+7)/5⌋+13 (n=1..5), F (n≥6) characters: F the all-named diagram | proved | linear: exact S commands. S counts statements including GIVE UP | linear: exact B+bl(S) bits. B counts the final write set and S counts statements |
| Kiss | tree | a node is S over its two halves, which S reads a bit to choose; a node whose halves agree reads it through SS(SKK) | linear: worst 7T-5 characters: 5 a node, 2 a leaf | proved | poly n: worst 4n - 1 rewrites: four a skip level, then a read, the output and the halt | linear: worst 24T + 2bl(n) + 17 bits past n = 1: a root skip holds its half twice |
| LaserFuck | finite lookup | weighted arms select one of `2**n` prewritten cells, cleaned in one sweep | linear: worst max(T,3)(12n+32) (n=1..6), 3(11T+52n+3) (n≥7) cells; tree then lookup | proved | linear: worst C*(n+491+X) + (1-C)*(T+296n+682 + min(1,max(0,n-6))*(10T-240n-680)) steps seed 2. C constant, X +x. Other headings add at most 2 | linear: worst 8n+27 (n=5..6), 12T+n+7+2bl(n) (n≥7) bits |
| Line | tree | small loaded trees and projected inline readers preserve totality and physical input order; complete ordered residual folds share every state unless their exact pixel area exceeds the fallback | linear: at most pixels from n=6: Pareto boxes over projected input sets | proved | poly n: worst 5n (n=1..5), 3n+3 (n≥6) commands by default, with balanced layouts retaining the first bound | poly n: worst 10 (n=1), 2n+1+bl(3n-2)+bl(n-1)+bl(2n-1)+(n*bl(n-1)-2^bl(n-1)+2) (n=2..5), 2n+3+bl(n-1)+bl(2n-1)+(n*bl(n-1)-2^bl(n-1)+2) (n≥6) bits bits by default ([proof](#line-workspace)) |
| Malbolge | exception | positional two-answer cells through sixteen inputs; at seventeen, each 15-bit prefix has a three-answer word and one shared spill slot; finite source space excludes some eighteen-input tables ([construction](#malbolge-bound)) | linear: worst 13340 (n=1..11), 15260 (n=12..13), 21831 (n=14), 52480 (n=15), 59049 (n≥16) characters | proved | unmeasured: at most E+J commands. E is the executed main prefix and J bounds the remaining commands | poly n: at most B+E+10W+J*(1+10F)+49+bl(n) bits. W prefix writes, F marks a following stub |
| moar cheese :3 | parameterized lookup | the queue holds pairs of answers; doubling calls count dequeues while each input keeps one half, then the last bit decodes the remaining pair; a symmetric table drops one popcount entry per 1 | linear: worst 2T+20n+104 characters, n=3..10; at most at n=1, 2 | proved | linear: worst 12 (n=1), 2n^2+11n+17 (n=2..3), 3T+13n-4 (n≥4) commands | linear: at most 8max(T/2+1,n+3)+(n+7)(8+bl(n+20))+(n+3)(bl(n+20)+3)+bl(max(T/2+6n+4,4n+10)) bits |
| Modulous | linear lookup | pair literal for asymmetric inputs; O(n)-source symmetric count reader retained; default exact maxima, split literals pay extra pushes/cursor bits | linear: worst 68 (n=1), 6T+28n+21 (n=2..4), 3T+28n+144 (n=5), T/2+48n+157+power2_digits_sum(n-1) (n≥6) characters | proved | linear: worst 4D+7J+P*(2n+3)+(1-D-J-P)*(T+3n+2+min(1,max(0,n-4))*(4-T/2)+min(1,max(0,n-5))*(2T+2n-37)+min(1,n-1)*max(0,S-1)) commands. D, J and P mark the direct, branch and discard readers. S counts literal pushes | linear: worst A*(9+bl(M))+P*(7+bl(2n+3)+bl(2n-1)+bl(n))+(1-A-P)*(13max(0,2-n)+min(1,n-1)*(6T+2-3T*min(1,max(0,n-4))+(n-1)*min(1,max(0,n-5))+bl(max(M,T+3n+2+min(1,max(0,n-4))*(12-T/2)+min(1,max(0,n-5))*(3n+3-T/2)))+bl(2n-1)+bl(n))) bits. A selects the one-input integer reader, P the discard reader and M counts tokens |
| Monotonic Boolfuck | tree | — | linear: worst 53T/2 - 21 characters past n = 1 | proved | poly n: worst 21n + 13 commands | poly n: worst 25 (n=1), 31 (n=2), 39 (n=3), 48 (n=4), bit_sum(2n+1)+n+15+bl(2n+2)+bl(n) (n≥5) bits bits |
| Movesum | linear lookup | constants read and reset n inputs, then print and halt in 2n + 3 commands; otherwise Horner-reads V = 44T + v, then each rung sums and preserves the counter, prints, and copies V into the sum slot; that copy is a second no-op exactly at the selected row | linear: 4T + 6n + 4 commands, 32 characters a row | proved | linear: worst 4T + 6n + 4 commands | poly n: worst 5n+56+bl(4T+6n+2)+bl(2n-1) bits |
| Nandypants | tree | the first bit of each input byte is read into b and branched on, the other seven are discarded at the head of the next block; equal subtables share one block, laid out in topological chains so every jump is a forward odd label, and a constant subtable reads its remaining bits and prints the answer byte | linear: Θ(T / log T) blocks of O(log T) digits | proved | poly n: worst 29 (n=1), 40 (n=2), 52 (n=3), 12n + 16 (n≥4) commands commands | poly n: worst bl(R-1) + bl(n) + 16 - C bits: R tokens, C marks the constant prefix |
| NOR machine | linear lookup | Horner builds the projected table above packed inputs in one accumulator; four NORs select each cofactor, whole right shifts consume its input, and large levels rebuild -2 only from the sole live accumulator | linear: 6T + 8r + O(n^2) characters for r runs of 1s | proved | linear: worst C*L + (1-C)*(15T + 12n^2 + 93n - 20) commands, with C set for a direct constant | linear: at most C*(max(3n,9)+bl(L-1)+1+bl(2n))+(1-C)*(3T+4n+bl(L)+24) bits. C marks the direct constant |
| NQ | tree | a lexical guard selects the true child; every leaf halts before its sibling, and folded suffixes consume all remaining inputs in order; grouped internal guards and complete parity-leaf enqueue targets work under both binding readings | linear: worst max(9T-6,10T-14) characters | proved | poly n: worst 3n + 4 commands: one extra guard for compact parity leaves | poly n: worst 9 (n=1), bl(n)+max(n+8,n+4+bl(n+2)) (n≥2) bits bits |
| Nybbleist | linear lookup | packs four answers per deque element, trims halves to one element and shifts by the last two essential inputs; affine tables XOR selected inputs | linear: worst 14 (n=1), 3T/4+9n+13+(4n-1)ceil(bl(2n-2)/4)-2(16^ceil(bl(2n-2)/4)-16)/15-max(1,ceil(bl(2n-4)/4))+2ceil(bl(2n)/4) (n≥2) characters characters; exact hex widths for packed selectors | proved | linear: worst T/4+4n+6 steps; the all-zero row of conjunction reaches it | linear: worst 9 (n=1), 14 (n=2), 19 (n=3), T/2+10+bl(T/2+4n+5)+bl(n) (n≥4) bits bits; packed deque, registers and cursors |
| Object disoriented | tree | a node keeps its input bit in `t` and its negation in `a`, via reader B and a negation object that is a 1 until a 1 bit calls it; each bit object calls its branch only on a 1; constant subtables fold, and a repeated branch is a class written once | linear: worst min(24T+56,H) (n=1), H (n=2..8), min(24T+56,H) (n≥9) characters, exact n=2..8 | proved | poly n: worst 76n + 34 commands: one tree path, 76 ops a level | poly n: at most (6n+8)bl(C)+(n+2)bl(16n+40)+8bl(6n+9)+6bit_stride(15,6,n+1)+24n+68+bl(n) bits. C counts built-ins and each object or class form |
| oBrainfuck | linear lookup | table laid on the tape loop-free; each input bit moves the head 2^(n-1-i) cells across a zero block inside one flat loop; the head steps back T and prints | linear: worst 4T + 52n + 47 characters | proved | linear: worst 4T + 52n + 47 commands: all-ones row, one zero in the table | linear: worst max(2T + n + 6, 13) + bl(L) + bl(n) bits |
| Onecode (Fergusq) | linear lookup | a Horner expression forms the projected row index; a string stores four answers per cell and a divisor table extracts the selected bit | linear: worst ceil(T/4)+11n+digits(48(T-1))+58 characters; one packed lookup literal | proved | poly n: worst 4n+34 steps; all inputs essential | T log T: worst 74+14ceil(T/4)+bit_sum(ceil(T/4)+4)+bl(4n+34)+bl(n) (n=1..2), 80+2n+14ceil(T/4)+bit_sum(ceil(T/4)+4)+bl(4n+34)+bl(n) (n≥3) bits, including packed cells, addresses and decoder state |
| Painfuck | tree | native numeric reads feed a flag-dispatched tree; known-zero children omit their dead flag, and one result cell is printed | linear: at most 31T/2+3n-21 characters past n = 3: to n = 15 | proved | poly n: worst 5 (n=1), 32 (n=2), 62 (n=3), 91 (n=4), 4n²+8n+5-6floor(n/2) (n≥5) commands commands; affine transfer loops above four inputs | poly n: at most 2n + 5 + 3bl(n) + (n+1)bl(L) bits: 2n + 2 cells, loop stack ≤ n |
| Parenthesys | linear lookup | constants read n inputs unprinted, then print the bit in n + 3 commands and characters; otherwise the table is one string literal; from n = 4 a character packs eight rows and `ind` indexes it with decimal groups of at most three reads modulo 8, joined in radix 8 (below, one row a character) | linear: worst ⌊T/8⌋+n+51+17⌊(n-4)/3⌋+6min(1,n-4-3⌊(n-4)/3⌋) characters past n = 3 | proved | poly n: worst n+22+9⌊(n-4)/3⌋+4min(1,n-4-3⌊(n-4)/3⌋) commands past n = 3: grouped reads, lookup, bit test | linear: worst 65 (n=1), 82 (n=2), 115 (n=3), T+112+8digits(T/8-1)+bl(2n)+bl(n+22+9floor((n-4)/3)+4min(1,n-4-3floor((n-4)/3))) (n≥4) bits bits; stack at the packed lookup |
| Piet | finite lookup | triple stacks from four essential inputs; smaller lookups, literal products, majority counts | linear: worst A (n=2..3), 3(3ceil(T/3)+5n+49+3T/2+n-2floor(n/2)) (n≥4) codels. Small-layout A, exact n=3..7 | proved | linear: worst P (n=2..3), 2ceil(T/3)+4n+40 (n≥4) steps. small-layout walk P. Exact at n=3..7 | linear: worst B (n=2..3), floor((11ceil(T/3)-5+2(n-2floor(n/2)))/4)+3n+bl(3ceil(T/3)+5n+48+3T/2+n-2floor(n/2))+bl(2n-1)+bl(n)+3 (n≥4) bits. small-layout stack and cursor B. Exact at n=3..7 |
| Pilas | tree | — | linear: worst 20 (n=1), 20T-22 (n≥2) characters characters | proved | poly n: worst 29 (n=1), 46n - 21 (n≥2) commands | poly n: worst 25 (n=1), 29 (n=2), 32 (n=3), bl(n)+max(2n+25,6K+12+P) (n≥4) bits bits, K retained constant bytes and P peak pointer bits |
| Pointless | tree | each distinct subtable is one function, pasted in where that is shorter; `,=` maps a character to its bit through the cells 48 and 49, and `[` tests the bit's cell; the one `!` seeds the 1s that make `+` an increment | linear: at most 329+14n+digits(P)+2digits(n)+A characters: every function declared | proved | poly n: worst C*L + (1-C)*(26n+309) steps: C marks a straight-line constant | poly n: worst C*(408+bl(L)+bl(n)) + (1-C)*((n+1)*(2bl(L)+4)+16n+430) bits: C marks a straight-line constant |
| Q-BAL | linear lookup | one attachment shifts the projected table integer by the row or sums the essential inputs for parity, then returns the remainder modulo two | linear: worst 13 (n=1), digits(2^T-1)+power2_digits_sum(n)+4n+9 (n≥2) characters, attained by OR from n=2 | proved | poly n: worst 1 commands | poly n: worst bl(n) + 4 bits |
| Qrain | tree | each input byte is read onto its own queue and tested in place by a flag-dispatched decision tree; repeated residuals defer through level flags; the first byte splits into a test bit and a fixed seven-bit tail that completes the answer byte | linear: at most 53 (n=1), 97 (n=2), 175 (n=3), 29T + 10n + 25 (n≥4) characters characters, exact n≤3 | proved | poly n: at most 43 (n=1), 74 (n=2), 103 (n=3), 36n + 60 (n≥4) commands commands, exact n≤3 | poly n: at most 26 (n=1), 42 (n=2), 54 (n=3), bl(L)+(2n+4)bl(2n+2)+9n+bl(n)+10 (n≥4) bits bits, exact n≤3 |
| Quassaunt | tree | shared residuals read every input depth; a fixed helper stores all code before the root runs | linear: at most (residuals(n)+2)(170+4W)+400+W+6n characters: bounded names and nodes | proved | linear: worst C*(26(residuals(n)+2)+15n+66)+(1-C)*(n+2)+2Q steps. C marks shared stores and Q counts concatenations | linear: worst 8R+(1-C)*(8(n+1)+bl(n+1)+1)+C*(8(26+2B+3A+2H+K)+10+bl(W-1))+bl(n) bits. C shared stores, R characters, W words, A names, B bodies, H helper, K longest key |
| REFRACTRAN | parameterized tree | reduced DAG with constant-controlled swaps pruned; parity shares complementary residuals by signed rails; every input has one ordered exponent embed | linear: O(T/log T) shared nodes, O(log T) digits per node | proved | linear: at most 17 (n=1), 39 (n=2), 83 (n=3), 157 (n=4), 2L+1 (n≥5) commands commands: exact through n=4 | linear: at most 18 (n=1), 27 (n=2), 49 (n=3), 81 (n=4), 8L+bl(L)+16 (n≥5) bits bits: exact through n=4 |
| Retrograde | parameterized tree | a single turn chooses one emitted child in either direction when its two functions match the siblings; backward ids are interned bottom-up; input bits and entry direction are restored, ordered setters precede the tree and the final cell carries the answer | linear: worst 9 (n=1), 9T+4n-15 (n≥2) characters characters | proved | poly n: worst 12n - 2 commands: native decisions and one final dump | poly n: worst 10 (n=1), 13 (n=2), 2n+8+bl(n) (n≥3) bits bits |
| ROTfuck | finite lookup | every loop's cycle is 0 (mod 8), so its exit rotation is the same whatever its trip count | linear: worst 3T+79n+43 (n=2..6), 3T+48+31n+(97⌊n/5⌋+16floor((⌊n/5⌋+(n%5)%2)/2))/3-5min(1,(n%5))+min((48(2^(n%5)-1)%256),256-(48(2^(n%5)-1)%256))+32(T-2^(n%5))/93 (n≥7) characters: lone-zero witness n=2..10 | proved | linear: worst E commands for the selected rotation and layout, including comments and constant loops | linear: worst C*(16+F+bl(S+80))+(1-C)*(2T+n+8+bl(2T+6)+bl(X))+bl(L)+bl(n) (n=2..6), C*(16+F+bl(S+80))+(1-C)*(2T+5n+35+bl(2080L)+bl(2T+6))+bl(L)+bl(n) (n≥7) bits. C selects constants, F selects forward, S counts commands, X bounds lookup execution |
| Rubic | tree | the last literal prints its byte or stores it and prints 49-P before undoing; every subtree preserves the opening cube, expressions are checked on X/Y, equal halves read untested and constants fold | linear: worst max(63,47T-44) characters: distinct maximal children, seeded by constant/NOT pairs | proved | poly n: worst 16n + 5 commands: the negated last bit costs 19, earlier differing nodes add 16 | poly n: worst 3n²+15n+118+bl(n) (n=1..2), 3n²+15n+117+bl(n) (n≥3) bits: n frames, n+4-bit positions |
| S*bleq | finite lookup | packed chunks decoded after the hoisted read block, against a hoisted tree that lays out each distinct subtable once and jumps to it | linear: worst 175n+717+2(digits(n)-1)+A+⌊T/n⌋(2+digits(T-1))+min(1,T%n)(2+digits(2^(T%n)-1)) (n≥11) characters; through n=28 | proved | linear: worst E+(1-K)*(3n+3) instructions through n=9, at most beyond. Packed route K costs E | linear: at most B+6n+bl(3R)+bl(n)+1 bits. B counts signed memory bits and R counts cells |
| SendStuff | tree | distinct subtables share named nodes, with an anonymous single-use root; an Input node sends a 1 through `Subtract 49` and a 0 through `Divide 48`, `Subtract 1`; equal halves and constant chains read their bits unbranched; last-input identity/negation share the constant reader with a unary tail | linear: at most 113+2digits(n)+digits(H)+A+J characters: distinct subtables and references | proved | poly n: worst U*(n+1+R) + (1-U)*(4n+2) steps: unary U adds R sends | poly n: worst U*(10+bl(n+R))+(1-U)*(10n+12+W)+bl(n) bits. U marks unary readers, R counts their extra sends and W sums frame index widths |
| Shakespeare | linear lookup | parity sums retained inputs modulo two; otherwise the table is one number packed by Horner's rule; each input multiplies a running power of two by 1 + bit * (2^w - 1), and the answer is the number divided by that power, mod 2 | linear: at most 16T + 7n^2 + 180n + 300 characters | proved | linear: worst 6 (n=1), 2n+⌈T/64⌉+6 (n≥2) commands, reads, multiplies and packing assignments | linear: at most 2T + bl(2n+ceil(T/64)+6) + bl(2n-1) + 4 bits |
| SLOW ACV MAMMALIAN | linear lookup | a read chain banks each bit on array 16 and the dispatch's `DIGEST LEAPFROG` reads that sum as the leaf address; up to four pooled weights are CONSUMEd from planted cells, so they never read the sum and need not be multiples of 256, which puts the stride at an eight-token leaf | linear: at most 12(2(W+P+Q)+8194) characters | proved | linear: at most N commands | linear: at most C*(6n+K+9+bl(n+S+3))+(1-C)*(8N+256+bl(N)+bl(512N))+bl(n) bits |
| Smallfuck | parameterized tree | a five-level banded prefix writes four Davio coefficients; three spare cells hold the suffix weights, then two destructive input loops update the answer; deferred definitions advance in depth | linear: at most P (n=1), P+20n+100 (n≥2) characters: coefficient prefix and Davio tail | proved | poly n: at most 9n^2 + 100n + 20 commands, one prefix path, forward guards and a two-input tail | linear: worst L + bl(L) + bl(3n) + 1 bits: one tape bit per source character and one native output-phase bit |
| Smu | tree | a node stores its halves under the input bit's own names and pushes the one the bit names as the next run's program, above seven skip runs except at the final byte, where the leaf takes the last bit; a node with equal halves is a pad; macros carry the repeated text, and a subtree two parents reach is one more when that is shorter | linear: at most 7T+150 | proved | poly n: worst 55n - 1 commands, eight runs per input byte | linear: worst 1490 (n=1), 24(177T/2-80)-1214+bl(177T/2-80)+bl(n) (n≥2) bits bits; expanded code, stack and bindings |
| Sonata | finite lookup | one rule a row answers through three inputs; beyond, the essential input bits double a unary row index in one rewrite each, and each index unit strips one entry of the table read at them. At the Unicode name boundary, a fixed-name mask reads the same bits | linear: worst T+4n+80 (n=1), (n+5)T-1 (n=2..3), T+4n+80 (n≥4) characters: exact n=1..6, upper bound thereafter | proved | linear: worst T+n+2 (n=1), 2 (n=2..3), T+n+2+min(1,floor(n/55041)) (n≥4) steps: row rules to n=3, then index, strips, halt | linear: worst 16T+10 (n=1), 8n+2 (n=2..3), 16T+10+16min(1,floor(n/55041)) (n≥4) bits: the input, or an index beside the table |
| SStack | tree | each input byte is compared with stacked '1' and '0', then popped before descent; the empty test stack ends both one-shot loops; a constant subtree reads its remaining inputs and prints; repeated residuals use guarded labels | linear: at most 24T-9 characters: 21 a node, 3 a leaf, 12 prologue | proved | poly n: at most 7n + 3 commands, six a tree node plus guarded dispatch | poly n: worst 6n+12+bl(K)+bl(n) bits: K parsed commands |
| Stisp | parameterized tree | n input frames consume once each; heads are named atoms or bounded literal pairs selected by native pattern equations | linear: at most F+28 characters past n = 2: named-diagram ceiling plus selectors | proved | poly n: worst n rewrites: one frame an input | poly n: worst 32n+1-C*(24n-8) bits. C marks direct constants. Exact through n=7 |
| Streetcode | linear lookup | the street writes one cell per entry, then each essential input's mouth forks on its bit (an ignored one is a lone read) and its side room walks the cell pointer left by that bit's weight, leaving the car over the indexed entry | linear: worst (32n+80)T (n=2..3), 7(3T/2+108+51min(n-1,6)+max(0,T/2-64)+3max(0,n-7)) (n≥4) cells: tree, then the flat street | proved | linear: worst C*(n+4+Q)+U*(290n+312+H+W+96max(0,2-n))+(1-C-U)*(5T/2+110n+108+min(1,max(0,n-7))*(T-96n+544)) steps for n≥2. C constant with Q carets. U selects the H×W tree | T log T: at most C*(27+bl(n+4+Q))+(1-C)*(nT+2n+25+bl(2T+57+51(n-1)+min(1,max(0,n-7))*(T/2+272-48n)))+2bl(n) bits. C marks direct constants and Q counts carets in their fill row |
| Subleq | finite lookup | shared direct-jump residual DAG or packed-table decoder; unused byte-I/O targets are zero | linear: worst min(A,H) characters. A packed, H shared tree, exact n=9..14 | proved | linear: worst 8T+(7n+5)(⌊T/n⌋-1)+23n-8 steps past n = 8: the packed decoder | linear: worst B+bl(P)+bl(n)+G*(6n+5)+4C+(1-G-C)*max(2M-2,M+4,1+5I+min(1,max(0,M-1))*(bl(2^M-1-M)+2bl(M)-3),5I+min(1,max(0,M-1))*(3M-7-bl(M)+A+D)) bits |
| Suffolk | linear lookup | workspace-limited NOR cofactors share computed values; fallback stores inputs through n=10 and uses a countdown beyond; a flag from the last byte suppresses incomplete records | linear: at most 9T+52n+289+(2n²-max(2,n)(max(2,n)+1))/2+62max(17,4n-3)+77 (n=4..6), 289T/32+n²+56n+241+62max(17,4n-3)+77 (n=7..10), (17T+316n+482)/2+37+62max(17,4n-3)+77 (n=11..12), (17T+316n+482)/2+29+62max(17,4n-3)+77 (n≥13) characters | proved | linear: worst L + R commands: R is the prefix through the first read: one pass, then EOF | poly n: at most bl(L-1)+max(6,n-1)+max(19,4n-1)+bl(n)+7+max(0,n-6)+bl(max(7,n+1))+8+bl(max(19,4n-1)) (n=3..10), bl(L-1)+max(6,n-1)+max(19,4n-1)+bl(n)+12+bl(max(19,4n-1)) (n≥11) bits: input storage and countdown |
| Super SNUSP | linear lookup | all reads precede a finite literal/shift lookup; persistent stack operands survive the read and chunk phases | linear: worst digits(2^(T-1))+8n+19 cells: one row | proved | linear: worst digits(2^(T-1))+8n+19 commands: straight line | linear: worst T+2n+14+bl(L)+bl(n) bits past n = 4: flat lookup |
| Taglate | tree | — | linear: worst 3T+12n²+17n+12 characters past n = 2: nibble leaves | proved | linear: worst 5T/2+12n^2+7n+69-4max(0,3-n)-75max(0,2-n)+B commands past n = 2, with B bootstrap commands before the first read | linear: worst max(floor(7T/4)+17n+20-6max(0,2-n),7B)+bl((1-C)*(5T/2+12n^2+7n+13-27max(0,2-n))+C*R)+bl(n) bits. C marks bootstrap layouts, B counts setup commands and R counts their tokens |
| thisthat | tree | inputs go to either end of one bistack row, an ignored one to the column; each end pop drives the next alternating-axis decision node, or goes to the column where the halves agree, in an order the row can pop; repeated identical straight transit strips contract to one | linear: at most (16(2^⌈n/2⌉-1)+1)(16(2^⌊n/2⌋-1)+3) cells past n = 2: H-tree `O(sqrt(T))` sides | proved | sqrt T: worst C*(2n+5) + (1-C)*((32+16*(n-2floor(n/2)))*2^floor(n/2)-29) commands: C marks the constant layout | poly n: at most 4n+89+2bl(n)+(n·bl(n-1)-2^bl(n-1)+2) bits past n = 2 |
| Thue | linear lookup | the table is the starting state, one character an entry, and the bit read rewrites every adjacent pair to one of its two members, so the state halves per essential input and the last character is the answer; an ignored input's round reads its line and deletes it; the rules never overlap, so the language's random rule choice has nothing to choose | linear: worst T + 187 (n=1..6), T/2 + 223 (n≥7) characters; pairs pack from n = 7 | proved | linear: worst 2T+3n-2 (n=1..6), 5T/2+3n-1 (n≥7) rewrites rewrites; full lookup with pair expansion from seven inputs | linear: worst 8T + 24 + bl(2n) bits: the T + 3 character state string |
| Trml | tree | root rules select a prefix-tree child or carry parity while consuming each bound input, then unwrap the output bit | linear: worst 150 (n=1), 156 (n=2), 146+2T+2n (n≥3) characters for the largest emitted tree | proved | poly n: worst n+2 steps; one rewrite per bit, one wrapper removal and one final output step | linear: worst 41 (n=1), 89 (n=2), 16T+16n+9 (n≥3) bits bits; initial object and halt flag |
| Tubes | linear lookup | row 0 writes a cell per table entry. The double splitter exit starts the memory walk for a 1, with w - 1 double cells completing its weight w. Both arms set the cell to 1 before merging. An ignored input is a bare read | linear: worst 3max(2T, T + 3n + 4) cells | proved | linear: worst 3T + 5n + 5 commands | T log T: worst 19 (n=1), 33 (n=2), 62 (n=3), (n+1)T+n²+4n+5+bl(2n-1) (n≥4) bits bits; table and index cells |
| Unary | tree, cap | complemented-byte decision tree; constants decrement the final byte before a fixed loop; projections and conjunction guards avoid flags | 2**T: worst source length at least 2**T - 1; zero-count encoding | lower bound | unmeasured: worst max(n, min(n + 4, 8)) commands past n = 2: at most nine commands, the last ] never run | poly n: worst bits past n=1: tape and cursor peaks among admitted nine-command shapes |
| Underload | parameterized tree | equal-width input programs leave one selector apiece; each node stores both branches as strings and the selector evaluates exactly one, while a constant leaf discards unused selectors except in named AND/OR and threshold-2 tails; a repeated subtree is pushed once and carried above the next selector, and the plain tree stays a candidate | linear: at most 153 (n=4), 5n+31T/4-3 (n≥5) characters: 241 a five-input half | proved | poly n: worst 10n + 3 + 2⌊(n-1)/2⌋ commands past n = 2: n slots, 9 a level, carries | linear: at most 24L + 168T + 32n - 168 + bl(2L+14T+6n-14) bits: spliced program, stack |
| Unlambda | tree | each half is a `d` promise, forced by the `?` test that selects it, since an argument spelled inline would be evaluated before the application; the shipped node instead returns `s` over its selected promises, so a repeated subtree bound once as a promise reaches every half below, and the plain tree stays a candidate | linear: at most 169T/8 - 21 characters past n = 3: pre-shortcut composition | proved | poly n: at most 77 (n=1), 152 (n=2), 229 (n=3), max(77n + 12, 84n - 9) (n≥4) steps steps, exact n≤3 | T log T: worst C*(32n+17)+(1-C)*(16(P+n*S)+(3n+9)bl(3n+9)+9)+bl(n) bits. C marks direct constants, P is the weighted term size and S the largest bound share |
| Unsquare | linear lookup | the first (n-3)//2 essential reads branch on a half of the table, each branch pushes one O/I per row, reversed, and the remaining reads pop their bit's weight in cells off the top of it | linear: worst T+T/2^max(0,⌊(n-3)/2⌋)+16·2^max(0,⌊(n-3)/2⌋)+10(n-max(0,⌊(n-3)/2⌋))+10 characters | proved | sqrt T: worst 4T/2^max(0,⌊(n-3)/2⌋)+79n+3max(0,⌊(n-3)/2⌋)+26 commands past n=7: 12- or 14-cell loops, one half pushed and popped | linear: worst 25 (n=1), 31 (n=2), 37 (n=3), 48 (n=4), 53 (n=5), 71 (n=6), 82 (n=7), 2^(n-floor((n-3)/2))+n-floor((n-3)/2)+8+(floor((n-3)/2)+2)n+2(n%2)+2bl(n) (n≥8) bits bits |
| Whitespace | linear lookup | inputs build 2**index; dividing one packed literal exposes its answer bit | linear: worst 65 (n=1), T+4n+70 (n≥2) characters, one literal and shared step | proved | poly n: worst 16 (n=1), 12n+7 (n≥2) commands, calls never nest | linear: worst 15 (n=1), 5T-3+bl(n+17)+bl(n+2)+bl(2n) (n≥2) bits, stack, heap and cursors |

Symbols the formula cells use:

- **///:** D = decoder flag; S = table size; P = ignore preamble; X = ignored inputs; M = macro flag; K = macro sweep count.
- **3x:** K(i) = bits of the ith key's value, exact; G = the program's ( count.
- **Algebraic Programming Language:** K = shared uppercase definitions, excluding NOT.
- **B-tapemark:** B = 8 + coordinate bits per program cell, plus a widest-coordinate mark per * or - cell.
- **Bitdeque:** S = nodes and repeated zero-edge pointers before the final level.
- **Bleh:** B = per-level alias-price ceiling; A = forced-cover loss; P = parent loss; R = ordered-pair loss.
- **Circlefuck:** U = parsed byte n+1 from n=3, otherwise the sum of parsed bytes 1 through n; B = sum of initial tape-byte bit widths; h = halt @ offset.
- **Collatz Multiverse:** K = the constants closure; A = the cell array, an (index, value) pair per entry; D = the decoder array, one entry per set bit of a cell.
- **Crement:** P = Σ_{k<n} min(2^k, 4^s - 2^s), s = 2^(n-k-1), the shared nodes per level; N = 5 at n=1, 13 at n=2, otherwise 3P+2n+3.
- **Flowchart:** E = number of exit-memory entries; C = sum of their column bit widths.
- **Grapheme:** B = bit width of the largest minimal leading-one lift modulo 2^T; D = digits(2^T).
- **INTERCAL:** S = emitted DO/PLEASE statements, including GIVE UP, independent of wrapping.
- **Malbolge:** B = the initial memory bits, source cells and fill; E = executed main-prefix commands; J = a bound on commands after the main prefix.
- **ROTfuck:** E = selected rotation and layout command bound, including raw digit walks and comment or constant loop allowances.
- **S*bleq:** B = the program cells' bits, a sign one more; A = extra decimal address widths of the packed decoder.
- **SendStuff:** H = largest residual label id; A = definition characters by layer; J = reference characters by layer.
- **SLOW ACV MAMMALIAN:** C = constant layout flag; K = constant reader head bits; N = emitted tokens; S = constant reader seeds; W = first window tokens; P = prologue token bound; Q = read level token bound.
- **Smallfuck:** P = band-five prefix ceiling over continuation cells.
- **Subleq:** B = program image bits; P = cursor ceiling; G = tree flag; C = constant flag; M = essential inputs; I = ignored last read flag; D = chunk-pointer growth; A = offset-copy width in workspace, packed cells in scaling.
- **Unlambda:** P = the program's leaves, each k and s counted twice; S = the same count for its largest X in an @-node's `N`dX.

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
  six-bit printable-ASCII lookup meets the byte-source arity bound given in
  the [generator ledger](#generator-ledger). For row `r`, it reads cell `r//6`,
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
  construction is described in the [Malbolge summary](#malbolge-bound),
  which gives the collision-free packed address map.

The former exception, `%^2^-1`, left with its language. Every row outside
these exceptions is `Total`, or theoretically total past the resource
ceiling below.

### Resource-ceiling audit

The remaining `cap` rows do have a uniform lift argument.

- Unary's complemented-byte tree is finite at every arity. Removing the
  raw, work and gzip screens and this construction’s nine-input guard
  permits every encoding.

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

Accordingly, this ledger records 108 theoretical totality arguments and
two exceptions under the source-embedded contract.

<!-- PROOF-TOTALS:END -->

Each exception is a proved obstruction of the language, not an open gap.
Every other row is `Total` or theoretically total past a resource ceiling.

## Ordered reads without retained inputs

Call a layered construction input-forgetting when, just before each read,
its data store and pointer depend only on depth; the control location carries
the residual function. Ordered reads alone do not imply this property:
`,>,>,<<.` reaches one cursor with four stores after two reads.

- BrainIf's ordinary residual DAG satisfies it. Its first input cell is zero;
  before each later read, `if 48 increment` maps the prior Boolean byte to 49.
  The next input overwrites it. OR with trailing ignored inputs instead keeps
  its answer beside a scratch input cell, outside this input-forgetting model.

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

- BrainIf's full-input DAG emits at most four lines per node, three at the
  root; placing a node before a child removes one goto. Destinations have
  `O(n)` digits, so the worst-case source is `O(T)`. Shared output tails add
  constant text. The ordinary zero tail builds 48 on a zero cell; OR prints
  its known zero byte directly. All gotos go forward.
  Interning and writing the labels cost `O(T)` in the repository's
  `Theta(n)`-bit table/index word model. This does not assert linear bit work.

  The public generator uses a read chain for constants and the DAG otherwise;
  width requests use the tree/spatial construction. The
  [research tests](../../src/esolangs/languages/brainif/tests/test_brainif_research.py)
  pin the three-input savings in source characters and executed lines against
  the tree. They exhaust every row through three inputs and check constants,
  parity and seeded tables through six inputs. Full-store boundary checks
  confirm erasure before ordinary input-cell reuse. Every default run consumes
  `n` inputs. The [generator ledger](#generator-ledger) gives the command
  bound, and the [Boolean tests](../../src/esolangs/languages/brainif/tests/test_boolean_brainif.py)
  also check trailing ignored-input layouts.


## Execution locality

Let `B(k)` hold every source symbol a run of at most `k` commands can read,
on any input and any program. If `B(k)` is fixed by geometry, not content,
then the symbols outside `B(K)` never change an output, `K` being the most
commands any generated program takes. Each of the `2**T` tables then needs
its own contents in `B(K)`, so `|B(K)| log2(c) >= T` for `c` symbols.
Each language's own tests check its generator against its floor.

- Bitwise Cyclic Tag runs its program cyclically from the first bit, one or
  two bits a command, and deletes at most one data bit: `3K >= T`.
- Blindfolded Arithmetic and NOR machine run their instructions cyclically
  from the first, one a command, without literals. That is 864 forms
  (`v0 = v1 op v2`) and six letters: `K >= T/9.76` and `K >= T/2.59`.
- Balik and Bifunge start at the top-left corner and move one cell a command.
  `K` commands reach `(K+1)(K+2)/2` cells, so `K >= sqrt(2T/3) - 2` with eight
  symbols and `K >= sqrt(T/2) - 2` with sixteen.

- A Painter Ant runs its instructions cyclically, one of ten letters a
  command: `K >= T/log2(10)`.
- Cyclic tag halts only on an empty queue, so every bit a run appends is
  deleted within it. A `K`-command run appends only productions `0..K-1` of
  length at most `K`, and its queue holds at most `K` bits: `(K+1)**2 >= T`.

Their ledger bounds match these up to a constant factor, except cyclic tag's
`T+n+2`, open against `sqrt T`. Clockwise, Tubes, Streetcode and ArrowQueue
move one cell a command from one start, a ball of `2K(K+1)+1` cells of at
most `2**21` symbols: `K >= sqrt(T/42) - 1`. Back's beam wraps and `+` moves
two cells, halving that. These floors are `sqrt T`; their generators are
linear. The bound does not cover a far jump (matched brackets, goto, calls),
a command that reads an unbounded token, data the source seeds without a
command (Movesum, Taglate), or several start points (thisthat). Rewriting
has no such floor: one Sonata rule per row, `row->=answer`, answers in two
steps from `(n+5)T - 1` characters, so its linear steps buy linear source.
The generator ships these rules through n = 3. Thue
and /// are unchecked.

## Scaling status

These verdicts describe shipped generators and exemptions from the measured
size regression. Open generator-linearity work lives in the
[roadmap](../roadmap.md#generator-linearity).

<!-- SCALING-STATUS:START -->

| Language | Totality | Generation time | Output size |
| --- | --- | --- | --- |
| Ascenic | Total | Language lower bound | Language lower bound |
| Befunge | Exception | Linear | Linear |
| Malbolge | Exception | Linear | Linear |
| Unary | Cap | Language lower bound | Language lower bound |

<!-- SCALING-STATUS:END -->
