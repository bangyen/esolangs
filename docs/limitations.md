# Limitations

Known limits, by question. Find your language by name: each language's facts
sit in bullets that start with its name.

| You want to know | Go to |
| --- | --- |
| How an interpreter treats input, errors and I/O | [Interpreter conventions](#interpreter-conventions) |
| Why a language differs from its wiki page | [Specification decisions](#specification-decisions) |
| Why a generator stops at some number of inputs | [Largest input counts](#largest-input-counts) |
| How big a generated program gets | [Scaling](#scaling) and [Source-count bound](#source-count-bound) |
| Why a language is (not) in the collection | [Curation](#curation) |
| Which languages use images as source | [Image-based languages](#image-based-languages) |

- Polynomial has a [size lower bound](proofs/index.md#polynomial-bound).

The measurement screens and profilers were removed once their
findings were recorded here. Numbers attributed to them are evidence, not a
command to rerun.

## Interpreter conventions

Unless a language says otherwise:

- Empty input is a no-op, except where a language requires a seed or grid.
- Exhausted input raises `EOFError`; malformed programs raise `ValueError`;
  runtime failure raises `HaltError`.
- Character input consumes Unicode characters, including newlines. Integer
  input consumes whitespace-delimited signed decimal tokens.
- Explicit frame stacks are uncapped.

Exceptions and per-language notes:

- Unsquare uses Unicode character codes where input framing is unspecified.
- Decleq uses Unicode character codes where input framing is unspecified;
  optional memory-mapped I/O is enabled.
- AddSubJump uses Unicode character codes where input framing is unspecified.
- Minifuck uses Unicode character codes where input framing is unspecified.
- Forbin expression calls retain their documented host-recursion limit.
- Streetcode's four-way junction is an implementation convention: the source
  specifies only a two-road choice.

### Image-based languages

<!-- RASTER-SOURCES:START -->

Line and Piet carry a raster source: `generate` returns an
`esolangs.raster.Raster`, `run` takes it or a PNG path through the shared
codec, and `describe` reports `source_kind="raster"`.

<!-- RASTER-SOURCES:END -->

Text and image-based languages share the same VM and step rules; `RUNNERS`
describes text bundling only.

- Line retains its graph for repeated generated rows; stepping parses pixels.
- Piet emits and executes pixels. Its packer tries up to 9 start-colour
  phases per lane (18 for duplicate lanes), averaging 1.9 tries on duplicates;
  no lane-level rule picks the phase: the winner is the least phase no
  aligned column forbids (n=2 `0110` and `1001` win phases 1 and 3 at lane 2
  of 6, the same end colour and direction). A spacer row needs no retry but
  costs 32-64% area.

## Source positions

VM instruction positions declare `ip_shape`: `offset`, `grid`, `line`, or
`opaque`. `tests/test_vm_protocol.py` checks every language and rejects
undeclared or misspelled values. Opaque positions have no source coordinate.

- Line extraction accepts anti-aliased PNGs only when strokes retain a
  connected dark core: the 3px scan fixture executes addition, and a
  one-third-pixel shift of a 1px stroke is rejected with 921 unaccounted
  pixels rather than silently changing the program.

## Boolean generators

### Input order

Every path reads all n inputs in order; an ignored input is read and
discarded, never left unread. Leaving a trailing ignored input unread would
make input consumption depend on the table. The measured savings were 9-29%
at n=7..8 across these generators:

- Unlambda was included in the trailing-input measurement.
- brainfuck was included in the trailing-input measurement.

Input reordering counts toward generation cost: at most four named candidates,
with the generic greedy scorer stopping at n=10. Generators may not use BFS or
DFS; test-only oracles may.

The removed screen script recorded permuted tables, not admissible reorders
under a fixed template and fill mapping.

- Dig must read in order.
- Flowchart must read in order.
- BrainIf must read in order.
- SLOW ACV MAMMALIAN must read in order.
- Minifuck has no derived instruction-only wire.

### Parameterized generators

Parameterized generators embed each input exactly once. Every emitted
character is build work. The input text must have:

- one ordered, constant-width run per input;
- one embed with no padded spaces;
- one uniform `(zero, one)` pair.

The template constructor enforces the shape. `tests/proofs/test_conventions.py`
checks filled programs at n=2, 3, 5.

Add a relaxed-width option only if it produces a smaller, executed build.
A space option has no remaining use.

### Optimizations not shipped

Each missed the 10% bar:

- ArrowQueue's rotations cost 19, 39, and 63 characters at k=1, 2, 3. Their
  2.1% gain misses the 10% bar, so plain order ships (d5bac32).
- Circuit Diagram's default path builds the identity order: four orders save
  8.48% of area at n=7, under the 10% bar. Width requests still try four.
- brainfuck lacks a cheaper jump, call, or label.
- Forbin's block size as a rule of n (`(n+2)//2`, at most 7) saves 50.4% at
  n=7 and 37.3% at n=8 but 10.3% at n=10 and 0% from n=12: it trims the
  register's fixed prologue, a share in decline. Uncapped it returns only
  1.1% at n=14 and 4.0% at n=16, toward a 7% limit.
- EGL spelling the ASCII-zero subtraction as a loop (21 characters for 48)
  saves a fixed 27 an input: 27.2% at n=7, 20.3% at n=8, 8.7% at n=10.
- Container's threshold path writing deltas unsigned saves a flat 4.7-5.4%.
- Object Disoriented's last-level short forms save 2.9% at n=7 and 0.6% at
  n=10; parity 7.8% at n=8.
- Cheapest names to the most-used nodes: `subtree_ids` already numbers
  bottom-up, so reordering can save at most 0.08-0.40% in Bleh, Stisp,
  SendStuff and Codesick; re-laying BitDeque's jump targets at most 5.8%.
- Defaulting to the smaller-area balance layout (2026-10-22; shipped for
  Piet, ArrowQueue and B-tapemark):
  - Clockwise's narrow route and banded strips (49-58T cells at n=10..12)
    lose to the flat default's 30T + 48n + 24; the strips also grow
    superlinearly in time (2.9 s at n=14).
  - LaserFuck's balance widths save 35.5% at n=6, 21.5% at n=7 and 11.9%
    at n=8.
  - Circuit Diagram's balance saves 12.4% at n=7 and 15.2% at n=8 but
    searches: 1.3 s at n=10, 24 s at n=12, 524 s at n=14.

### Searches kept

Malbolge's generator keeps one table-independent search, run once per
process; no rule reproduces it:

- Navigation (`emitter.py` `goto`, breadth-first shortest paths). The main
  line ends at cell 6,013 at n=1 (5,487 at n=16), over 5,089 path cells;
  the code must end below 6,561, where the hubs and stubs start. Closed-form
  navigation -- a forward walk, a `j` through the cell at `d`, or a walk to
  the next unwritten cell with `g = t - 1`, then one more hop -- ends at
  13,501 at n=1 (12,816 at n=16). The label priming alone takes 2,653 path
  cells against 609: its `p p` returns to the cell it just wrote 74 times,
  a forward-only pass leaves `A` equal to the cell just written, and no row
  of `crazy` is constant, so it cannot bring the next cell to the same value.

### Largest input counts

- Malbolge:
  Malbolge's source-embedded generator covers sixteen inputs with one
  positional build: the first `n - 1` inputs fill a readout word three bits
  per two-trit digit, one cell per row pair, and the answer stub reads the
  last; below sixteen the unused reads are held at `0`, so every arity's
  cells are a subset of sixteen's. Boundary rows execute at every arity and
  every row at ten. Construction details and measurements are in
  [construction summary](proofs/index.md#malbolge-bound).

  Seventeen remains open. Native capture, semantic readout, footer dispatch and
  terminal-output components execute separately; no source computes an arbitrary
  full 17-input truth table. Raw record addresses can overlap executing code,
  so relocation must precede capture. The reduced LAST-only layout is short by
  8,432 cells before adding the remaining query, selector and metadata. This is
  a deficit for that construction, not an impossibility bound.
  The shipped cap remains sixteen.

  The seven-meaning integration was re-measured end to end (2026-10-21,
  `notes/malbolge17-refund/`, tooling from `09ab2fad:scripts/malbolge17/`).
  Navigation (`o`/`j`) is 93-94% of its emitted cells; a walked cell holding
  `target - 1` lets one `j` land `D` on a hot cell, which cut the address
  fold from 10,420 to 7,234 cells and the integrated decoder from 13,177 to
  12,303, every control passing (16,384 address rows, 5,488 decoder cases).
  Fold and decoder together, code and data, occupy 19,549 cells against the
  9,897-cell table complement: a 9,652-cell deficit. It is a navigation
  deficit, not a design one: pricing every `goto` to a cell at or above 34
  at one cell leaves fold 1,404 and decoder 4,015 (+956 data), a 6,375-cell
  union under the complement (the earlier 13,228 figure teleported only
  targets at or above 128). The slack is in the window 34..127: the fold
  spends 5,355 of its 7,234 cells on 630 gotos there (8.5 a hit; targets
  45, 34, 37, 38 and 97 cost 2,256), and its greedy pointer selection
  stops after twelve: with the tail moved out of the parity-reducer's way
  (C2190 to C40096) every further candidate builds but none shrinks the
  fold, since a pointer takes a window cell the labels and reducer used and
  the reducer grows by more than the pointer saves. The pointer mechanism
  is saturated at 7,234 (`notes/malbolge17-refund/`, 2026-10-21). Nor
  can the window's contents be rechosen to approach one cell a hit: `D`
  moves only to `D + 1` or `mem[D] + 1`, so routing is a walk on a
  94-node out-degree-2 graph, and annealing all 94 contents over their
  eight admissible characters for the fold's 628 low gotos alone floors
  at 3.6 cells a hit (2,254 model cells against 3,725 for the shipped
  contents, which the planner prices at 5,355); over the 31 unpinned
  cells, 4.8. That floor is tight and optimistic: 63 million moves over
  four seeds in a C port of the same model reach 2,231-2,253 (3.55-3.59
  a hit), and the planner's `goto` is already an exact breadth-first
  search, its 1.44x gap to the model being operated cells that hold
  accumulators rather than their startup characters, so the pinned 4.8
  is the honest figure. The fold's low navigation can lose at most about a
  thousand cells. Priced together: the teleport oracles leave 2,743
  non-navigation cells in the decoder and 682 in the fold, so the
  complement affords 5,516 cells for their 1,994 gotos, 2.77 a hit, under
  the 3.6 floor (unions 11,559 at 3.6 a hit, 13,953 at 4.8; a target
  above 127 costs a window walk plus one `j` besides). The three-cell,
  seven-meaning family is closed unless a layout needs a quarter fewer
  gotos at the floor cost. Low pointer cells in
  the decoder's window are blocked: every window cell is a
  neighbour-escape landing, so a freed cell needs a chain-built pointer
  whose probe cell names an N cell, and the chain vocabulary reaches too
  few values.

  A seventeen-input layout needs more than two table bits in almost every
  cell, and the cell's character is the only per-row freedom: at address `h`
  the loader admits the eight characters `33 + (k - h) % 94`, and `j` lands
  the data pointer on window cell `T + 1`. Everything a decoder does after
  that is a function of that cell, so eight distinct meanings per address
  need the 94 window cells coloured so that no address's eight cells share a
  class. That conflict graph (42 of the 93 offset differences) has
  independence number 8 (`test_window_classes.py`, a 0.02 s bitset search):
  at most eight cells per class, so eight classes reach 64 cells, not 94,
  and a proper colouring needs twelve (SAT: twelve suffice, scratch). With
  eight classes the best annealed assignment leaves about 1.2 duplicate
  characters per address, 2.7 bits per cell where 2.67 are needed for
  131,072 table bits in at most 49,152 addressable cells. The two earlier
  layouts (2026-10-13/14, three cells per fourteen-bit prefix, and the
  seven-class label window) assumed eight or seven clean meanings per cell;
  the first also needs three pairwise disjoint 16,384-cell digit maps, and
  any aligned four-trit window of three such maps carries at least 96 of
  its 81 values, so no three are disjoint.

  Reading adjacent cells does not escape the window (2026-10-21, exhaustive):
  `v[h+1] - v[h]` is phase-free, but a decoder reaches it only through
  back-to-back `*`/`p` reads, since `D` advances once per instruction.
  Over all 730 such chains (`*` then `p`; `p` after each of the 729
  constants that touch a character's di-trits, then `p`), the best
  three-cell read lands on 110 distinct cells at its worst phase against the
  256 a byte needs (two cells: 38 of 64), no triple lands phase-free, and
  every chain's state space is at most 243 cells, since `crazy` acts per
  di-trit (`notes/malbolge17-refund/scripts/chain_sep.py`, 9.7 s; the
  identity control scores 512). Mixing a per-window-cell constant instead is
  the measured landing decoder above.

  Shared cells do not rescue the count (2026-10-20, model): the holes of the
  sixteen-input map are reached by forcing one digit to its missing value,
  so a hole cell is shared by eight prefixes and must be combined by XOR
  across prefixes. That is a linear system only when each cell's eight
  characters map to an affine flat of classes, which with twelve or more
  classes means every address's eight classes form a 3-flat; annealing over
  5- to 7-bit class words never got below 110 violated addresses of 94. The
  one address-independent combination, the window-position difference of a
  prefix's own and shared characters (a code run whose length is linear in
  the landing cell), only exposes the parity of the op index, because
  `Z_94` has a single character to `GF(2)`.

  Navigation, not ops, is sixteen's cost: of 3,618 code cells, 427 are `p`,
  `*`, `/` or `i`, and 3,191 are `o` or `j` (`o` 2,558, `j` 633).
  Sweeps cannot cut the label window's share (2026-10-16, model): every
  sequence of up to five chained `p`/`*` sweeps over cells 34..127 leaves at
  least 61 distinct values, so a class's pointers still need priming: `p`
  twice per cell from `A` = all-1, and the walk back (prime 799 cells for
  72, seeds 554 for 68) stays. Contiguous class runs would shorten seeding,
  but a run must be 22 cells long to meet every table address's eight
  pointers, and seven classes need 154 > 94.

  Counting bounds each family independently of mixer quality:

  - stubs need three gap-3 cells per row: `3 * 2**n <= 59049`, hence `n <= 14`;
  - cascades need one cell per row per level above ~9k code cells: `n <= 15`;
  - last-input cells need `2**(n-1) <= 59049`: `n <= 16`.

  The positional build meets the last bound. A cell answering the final two
  inputs would need sixteen labels, but its address admits eight characters.
  Seventeen inputs need more than two table bits per cell across almost the
  whole store.

  The language itself has a separate limit. Malbolge has 59,049 cells and
  eight valid decoded instructions at each occupied source cell -- the
  decipherment cycles with the cell index, and `_XLAT1` holds each instruction
  character exactly once -- hence fewer than `sum(8**k for k in range(59050)) <
  2**177148` programs against `2**262144` truth tables on 18 inputs, one
  table per program: some 18-input tables have no Malbolge program.
  Malbolge is therefore a language exception, not merely a ceiling.

  Seventeen -- the registry target -- needs the count under `2**131072`, a
  factor `2**46076` below it, and counting does not get there. A length cut
  needs every answer inside the first 43,690 cells, but cell 58,967 alone
  flips row 299 at ten inputs (`0` against `1`, both executed). An alphabet
  cut buys `log2(8/k)` bits in all -- one bit at `k = 4` -- against single
  cells realising 5 to 8 distinct behaviours (12 of 20 sampled walked-code
  cells at 5 or more). A dependence cut (answers resting on at most 24,434
  cells, the largest `K` with `C(59049, K) * 8**K < 2**131072`) is false per
  program: `'o'*59046 + '/<v'` computes the one-input identity and every
  cell flips it, so only a cut over one normal-form program per table
  remains open.

  Malbolge without `i`/`j` cannot express NOT. Straight-line `c == d` from
  the reset state gives a `p` its own cell's instruction character, one of 94
  values in 33..126, and the input pair `(49, 48)` is unreachable, so NOT is
  not expressible at any length.


Shipped limits, in inputs:

| Generator | Dense | Parity | Limit |
| --- | ---: | ---: | --- |
| Malbolge | 16 | 16 | Every arity addresses positionally, three bits per two-trit digit, so no row collides; that readout needs 65,536 row-pair cells at seventeen in a 59,049-cell store. Three-cell, seven-meaning packing is closed at the routing floor (above; [scaling](proofs/index.md#malbolge-bound)). |
| Polynomial | 10 | ≥11 | 1,934-instruction guard; dense n=11 is priced at 267 s and >100 MB. Parity is routed through the state machine (two states per input, ~11 instructions per level), so the guard does not bind it at ten. |

### Size lower bounds

- Polynomial's block-incidence lemma forces `Omega(T/log T)` distinct real
  instruction-root values even when roots repeat, and the slack certificate
  prices every multiple of their distinct-root product. The routing lemma that
  forces those values holds for every read count, so the language bound is
  `Theta(T**2 / log T)` for every cofactor and operand sign. See
  [polynomial](proofs/index.md#polynomial-bound).

### Scaling

Size is measured from rendered output, and correctness claims require running
the generated program. A generator guarantees its size class, not its
constant; constant-factor tweaks beyond the canonical set ship only at 10% or
more where they run (`docs/CONTRIBUTING.md`). Execution measurements exclude
loading and use the worst sampled parity row. A sub-10 ms run does not
establish an exponent.

- Circuit Diagram loading is dominated by parsing super-linear area (the
  default's area is bounded by the H-tree pool, `~5.4k T` cells, at every n >= 9).

- FRACTRAN's row-addressing tree costs `Theta(T log T)`, but that is not a
  language floor. The shipped generator gives equal subtables one state, so
  it names `O(T / log T)` primes of `O(log T)` digits: `Theta(T)` text, at
  most `n + 1` fractions fire a run, and at n=12 it emits 3.81 characters
  per entry versus 23.6 for the tree. The construction and the counting
  floor are in [fractran](proofs/index.md#fractran-bound) and
  `src/esolangs/languages/fractran/tests/proof_fractran.py`.

#### Sharing repeated subtables

The canonical sharing piece is applied or exempt by measurement. Potential
before a generator's own share is bounded per piece: repeated nodes,
constant folding and ignored-input growth. Above-gate repeated-node potential
requires a construction exemption rather than a sub-gate bound.

- SStack has 24.6% repeated-node potential at n=5; 82% is in size-2
  subtables, below the two-unread-input depth a deferral needs. Its constructs
  reach size >= 4 repeats and save 4.8% of the plain tree
  (`tests/generators/test_boolean_sstack.py`).
- thisthat has 26.4% repeated-node potential at n=5; its admission tests
  support its construction exemption. Residual-duplicating fallbacks
  (`_strip_tree`, `_stream_tree`) are gated to at most three essential inputs
  (seven nodes) or two inputs, where a fold cannot pay.
- Back has 18.3% repeated-node potential at n=5; its admission tests support
  its construction exemption. It admits one bend: every route crosses
  column 1, so a second path meets the first's cells. Admission is bounded
  to 6..12 essential inputs without a width (16 of 96 controls improved).
- Dig has 10.9% repeated-node potential at n=5; its admission tests support
  its construction exemption. Its shared pool is 2..10 unique 64-row classes
  indexed by one decimal digit over 2..6 prefix bits; a larger pool needs a
  multi-digit index. A finished sharing layout whose `_chain_lanes` corridor
  crosses another class's lane arrow or branch `$` is rejected and falls back
  unshared: 131 of 602 shared layouts in the n=12 scan behind this entry
  (random 64-bit leaf classes mixed with constant leaves). A per-class gutter line removes the
  rejection but shares no more (26 to 24 lane layouts) and grows shared
  layouts ~5%: a crossed leaf or constant read row kills the gutter, and
  recovery would save nothing anyway: at n=12 the indexed leaf decoder
  emits 11-22x less area than every shared layout, which `generate` never
  picks there.
- Boolfuck has sub-gate repeated-node potential: 2.3% of emitted size at n=5,
  pinned in `tests/generators/test_boolean_boolfuck.py`.
- Home Row is a lookup that names no decision-tree node.
- ROTfuck is a lookup that names no decision-tree node.
- Dimensional is a lookup that names no decision-tree node.
- LaserFuck's path-dependent leaf code makes equal subtables unequal text.

<!-- SHARING-COUNTS:START -->

A test (`tests/generators/test_boolean_sharing_catalogue.py`) checks that 39
of 58 tree-shaped generators build parity or a repeated-block table at most
0.90x its dense or distinct-block twin (7 by a local helper); 19 are
exempt with a reason. One shrinking probe does not establish complete sharing.

<!-- SHARING-COUNTS:END -->

- Underload references a canonical sharing helper.
- Unlambda references a canonical sharing helper.
- Circuit Diagram compares three complete residual folds against its fallback
  by exact emitted characters, without a node-count cap; sharing wins ties.
  The [construction proof](proofs/circuit-diagram-sharing.md) bounds modeling
  and emitted text by O(T), rather than claiming every shared rectangle has
  linear area.
- Line compares complete ordered residual folds by exact emitted pixel area;
  a complete fold wins a fallback tie. Neither fold (streaming, projected
  streaming) has a sharing cutoff. The [construction proof](proofs/line-sharing.md) establishes
  complete state sharing, O(T) modeling and area-admitted output. On 200
  seeded eight-input tables, complete drawings total 7,929,032,800 scale-one
  pixels against 3,809,364,000 for the smaller fallback (108.15% larger);
  51,200 native rows of the public PNGs pass. This is the canonical
  average-larger exemption, not a physical area lower bound. Partial-prefix
  cloning remains unshipped: its 2.19% aggregate planned gain misses the
  bespoke gate; its native positive control passes all 256 rows, from
  33,700,800 to 32,865,600 pixels with the same 23-command maximum.
- Polynomial declares `_polynomial_states`.
- Piet is exempt: a strip has no jump, so a repeated subtable cannot be shared.

- Line:
  The Margulis cofactor witness establishes an expander minor in the
  original-order residual graph, not a language-wide area floor. At twelve
  inputs, Line's default layout passes all 4,096 rows in
  12,483,200 scale-one pixels. Reversal reduces the
  witness's nonconstant residual states from 18,437 to 548 at nineteen inputs
  (graph counts only). A language-wide area lower bound needs a physical embedding
  proof and a witness covering alternative input orders and encodings.
  [VLSI layout bounds](https://publications.csail.mit.edu/lcs/pubs/pdf/MIT-LCS-TR-305.pdf)
  require an applicable embedding model;
  [universal-circuit size bounds](https://encrypto.de/papers/KS16.pdf) count
  logical gates, not rendered area.

#### Ignored inputs and constants

`test_generator_shape_is_what_the_catalogue_says` checks that a tree row folds
on a one-dependency table and a reducing row drops its ignored inputs. A second
test (`tests/generators/test_boolean_canonical_catalogue.py`) checks that
generators have the helper; its declared exceptions handle the case themselves
(three rows for ignored inputs, eleven for constants).

#### Suffix banks

The suffix bank defers each word's greatest repeat inside its own body, so a
nested definition shares like a top-level one.

A bank block must defer through a distinct unused flag at a level no
shallower than its own: a shallower ancestor would rewrite the flag before
dispatch.

- Painfuck admits a bank at several depths; one cell per input level
  is the whole pool.

#### Run time and memory

The execution check in `tests/proofs/deep/execution.py` holds every
generator's command count linear. Bracket matching is precomputed at load.
Persistent stores use shared 32-cell chunks.
Those choices prevent repeated scans, but command cost and source size remain
separate axes. Loading is intentionally excluded from execution time.

- RAM0 also indexes addresses.

The payload benchmark checks 96 tables and all 6,120 rows through eight
inputs, reporting UTF-8 source bits, hidden control stacks, signed integer
widths and the simultaneous peak of data, control, cursor and machine flags
(separate peaks need not coincide; Python overhead, static parser indexes
and I/O state are excluded). Sampled peaks are measurements, not
language-wide space bounds; construction bounds are asserted by the removed
screen and controlled by executed checks in each language's own tests.

- BFStack has a sampled peak machine payload of 756 bits at eight inputs.
- Subleq has a sampled peak machine payload of 3,066 bits at eight inputs.

`T log T` workspace (eight ledger rows) is a store key or a shared reference,
which `state_bits` (`scripts/benchmark.py`) counts in full each time; the
counting rule stands. Dense tables, n=8 to 9 unless stated:

- A Painter Ant, B-tapemark, Collatz Multiverse, Dimensional, Flowchart and
  Streetcode key a sparse store by address: bits per entry rise one per input
  (A Painter Ant 9.0 to 10.0 a painted cell, Streetcode 8.0 to 8.9).
- Unlambda's frames share subterms, each counted at every reference:
  14,752 to 28,384 continuation bits.
- Forþ keys every scope by heap index, but twin calls hold the count near
  `4.6T/n` (`S·n/T` 4.75, 4.86, 4.42 at n=8, 10, 12), so keys cost about
  `4.6T` bits. A table whose 16-row blocks all differ holds S at
  `2^(n-2) + 538` from n = 13 (262,678 at n = 20, measured; no call reaches
  past 512 scopes, and a twin 50,625 or more back is inlined, never
  called): bits a scope rise 180.2 to 185.8 over n = 16..20, but 46.5 bits
  a row at both ends, so T log T is not separable from linear there.

- Malbolge:
  `test_boolean_malbolge.py` executes the boundary rows at every arity,
  every row at ten, and every 128th row at fifteen and sixteen weekly.
  No row shares a cell, so a row's answer is wrong only if its own cell
  is: a corrupted cell fails exactly the rows that read it.

Sixty-four ledger cells are `at most` throughout and seventeen more past an
exact range (2026-10-23, counted from the ledger; open ones are on the
[roadmap](roadmap.md#generator-linearity)):

- Route race: the shipped program is the shortest of several forms or
  layouts, so the worst table is a maximum over a minimum and switches
  with the winner. Back scaling and execution past n = 6 (the comb's
  Rudin-Shapiro table folds: 2,240 cells against 2,522 at n = 7);
  ArrowQueue execution (proved 11T + 32n + 92),
  BFStack workspace, Boolfuck workspace,
  Circuit Diagram workspace and scaling (an H-tree pool from n = 9 caps
  the area; the default measures at most 0.26 of the cap), Container scaling (the threshold build loses
  to the tree from n = 6: 883 against 1,076) and workspace, CVNC
  execution, FALSE scaling and execution (reached at n = 4, 5 only; at
  n = 6 diagram 292 against expression 293), Fargo all three, For Thorn
  execution, Minifuck execution (from n = 13 the stored plan ships, under the
  mux's worst), Object Disoriented scaling, Piet all three,
  Smallfuck execution, Streetcode workspace; scaling for Algebraic Programming
  Language (144 against 182 at n = 4, exhaustive; the reduced
  diagram's 10T + 4n + 6 holds to n = 14), Packlang, Painfuck (232 against 239 at n = 4), 6-5 (105 against 166 at
  n = 4, the shorter of two layouts to n = 5),
  SStack (24T - 9 exact to n = 4), Underload (exact at n = 4, 5) and
  Unlambda (to n = 2), and Brainfuck (13-29% loose, n = 5..8), For Thorn,
  Smallfuck, Subleq and AddSubJump (per-candidate sums); Boolfuck scaling past n = 7 (the gates take its
  worst: 1,968 against 4,681 at n = 8); S*bleq scaling below n = 11.
- Window slack: Interprogck8 scaling, execution and workspace bound the
  construction, not the worst table. 420T + 900 characters against 200T
  at most found, n = 4..10 (the windows opened are bounded, not located);
  R + 11n commands against 0.64R at n = 7 (a run skips the lines a flight
  hops); the workspace adds a slot and a frame of the longest body, 33
  characters, which only some tables hold.
- Layout slack: Slow ACV Mammalian scaling, execution and workspace bound
  every list at its residue maximum, but the layout is fixed by n and the
  essential set (a table changes only its leaf bits), so the lists sit at
  fixed residues and the maxima never co-occur. Exhaustive n = 3 (256
  tables): 2,656 commands, 518 bits, 24,423 characters against 4,921, 802
  and 54,796; sampled tables n = 7..12: 1.3-2.4x over on all three (n = 12
  random: 327,178 characters against 475,725; 8,824 commands against
  15,720). Exact needs the generator's own address solve, not a bound.
- Address widths: the peak sums the bit-lengths of table-dependent
  positions, which cross powers of two by layout. AddSubJump, Caballo,
  Crement, Pointless, S-BLEQ (1.002x: cell bits plus 6n, packed
  route sampled to n = 10) and Underload workspace;
  Painfuck workspace (slack 1
  at n = 3..6, never 0); Decleq scaling (8, 10, 14 short at n = 2..4,
  exhaustive); Bitdeque scaling (GOTO digits by layout; 358 against
  400 at n = 4, exhaustive); 3x workspace (exact key bits; 1.3-1.5x at n = 3..6, 1.8x at n = 9);
  Malbolge workspace (about 470 data-dependent re-encipher widths, the
  bound now 1.03x).
- Coincident peaks: the bound adds component maxima no single row or
  table reaches together, and the exact peak needs a per-row profile or
  a joint optimisation. Algebraic Programming Language execution (a
  random half beside complemented (n-1)-parity runs 296 > 293, the parity
  path, at n = 9: executed definitions K add to the longest path);
  Circuit Diagram execution (2n + 1 is derived and reached to n = 20, but
  a bank can beat the fold that reaches it); ABCDirection, Algebraic Programming Language,
  FALSE (1.3x past n = 8, per route), For Thorn, Object Disoriented (1.7x,
  per level) and Packlang workspace; Polynomial both; SStack execution (exact at n = 5 and 8
  only); Unlambda execution and workspace; RAM0 scaling (a repeat goto
  needs a zero child already built); SendStuff scaling (a constant child
  replaces the branching node the bound also prices).

## Curation

<!-- COLLECTION-SIZE:START -->

The collection has 95 languages.

<!-- COLLECTION-SIZE:END -->

Its floor is 31; every language but the three interpreter-only classics
(Deadfish, HQ9+, Nope.) has a generator. Removed: unused
ordinary imperative entries with shared-shim generators; Nopstacle for
incompatible embeds; ZTOALC L for a searched syntax-level lookup table. The 2D screen intersected
1,543 unimplemented with 567 two-dimensional pages, then filtered 36 by prior
verdicts, co-categories, I/O and branch vocabulary, and page length.

- Super SNUSP was admitted by the 2D screen.
- Alight was admitted by the 2D screen.
- Pinyin was rejected by the 2D screen.

### How a language is admitted

Fame admits languages with at least 60 unique esolangs linking pages. Resolve
title redirects, exhaust `list=backlinks` continuations, include redirect links
across all namespaces, and deduplicate by page ID. Pause at least three seconds
between requests.

The cutoff is policy, adopted 2026-10-01, not a measured popularity boundary.
Record resolved title, date and count; missing data means unassessed
(`unassessed = true`, which `finish` flags until the count is recorded). Low
backlinks count against only old languages; Wikipedia pageviews are not a
gate.

Below 60, a language is admitted only as a first implementation: when the
repo adds it, no implementation exists but the maintainer's. Its page is in
the Unimplemented category, or the edit that first tagged it Implemented is
User:Bangyen's. An intrinsic axis can choose between such candidates; it
admits nothing alone and removes nothing. Scaling removes: an uncapped
generator whose `O(T)` generation time and emitted size are neither proved
nor ruled out by a language lower bound takes its language with it
(Polynomial, Unary and Ascenic keep theirs on proved bounds; Malbolge's cap
leaves no asymptotic question). Adopted 2026-10-21; Vandevelo was removed
under it.

A route admits a language only when its specification fixes the core
semantics. 3D Brainfuck was removed on 2026-10-06: its page never says how
a linear source places blocks in the grid or what the generation pointer
does, so its interpreter invented the core, the invented semantics the
大白话 deferral rules out. Transistor (2) was built and dropped on
2026-10-07 for the same reason: its page gives no grammar and no I/O, and
its one loop example calls an undefined `or`.

Nor does a route admit a command-for-command substitution of a collected
language: a fixed token map under which every program behaves the same adds
no interpreter or generator, the ground that excludes Trivial brainfuck
substitution as a family. Adopted 2026-10-14 for candidates; no collected
language is one (Painfuck adds +2/-1 steps, ROTfuck a rotating command set).
The test follows Felleisen's expressiveness criterion: a construct a local,
compositional translation eliminates while preserving observable behaviour
adds no expressive power (Felleisen, "On the Expressive Power of Programming
Languages", 1991).

The first-implementation route also excludes a language whose generator
re-spells a collected generator: the construction transfers step for step
by token substitution and uses nothing the older language lacks. Same
family is not enough; Rubic's tree branches on cube parity, not a jump.
Adopted 2026-10-15, retroactively: Factor (brainfuck's flag tree as a
prime product), HQ9+ with headers (Qoibl's packed literal), Parenthesys
(Alight's indexed string) and Piet++ (Piet's strip, recoloured) were
removed. Painfuck shares brainfuck's flag tree but stays: its moves use
`d` and `r` and its I/O is numeric, none of them brainfuck's. Fame
admissions are exempt: S\*bleq, itself a re-spelling of Subleq, was
collected first, and Subleq's generator re-spells S\*bleq's in turn;
the fame route is what admits Subleq.

Nor does the first-implementation route admit a page the wiki categorizes as
a Brainfuck derivative: the family already holds brainfuck and ten collected
derivatives. Adopted 2026-10-15 for candidates; each package's
`language.toml` records the category as `bf_derivative` in its `[curation]`
section. The seven derivative first implementations that
predate it stay, each the wiki's only implementation of its page.

### Recognition sources

Sources checked 2026-10-01 supply selections, not admission gates
or popularity rankings.

[Kneusel, *Strange Code* (2022)](https://nostarch.com/strange-code) has
named esolang chapters on FRACTRAN, Piet, brainfuck and Befunge. Filska
and Firefly are the author's own creations; Forth, SNOBOL, and CLIPS
belong to the separate atypical-language section.

[Morr, *Esoteric Programming Languages*](https://blinry.org/esolangs/esolangs.pdf)
selects brainfuck, INTERCAL, Befunge, Malbolge and Shakespeare as iconic
examples with different properties, not an exhaustive canon.

[LMU teaching notes](https://cs.lmu.edu/~ray/notes/esolangs/) give a
brief themed, theoretical, golfing, multidimensional, and
difficulty-oriented tour, selecting LOLCODE, Glowup Vibes, ArnoldC, Chef,
Shakespeare, Rockstar, brainfuck, Binaryfuck, Lenguage, GolfScript, Pyth,
CJam, Jelly, 05AB1E, Vyxal, Befunge, AsciiDots, Piet, Whitespace,
Unreadable and Malbolge.

The [Esolang featured archive](https://esolangs.org/w/index.php?title=Esolang:Featured_languages&oldid=161213)
records administrator-selected features, not popularity endorsements:
Thue, Funciton, brainfuck, Deadfish, Emmental, Malbolge, Glass and ///
were featured.

### Backlink counts

The 2026-10-01 count gives Brainfuck 2,057 backlinks; 282 counted only the first
API batch. Brainfuck-relative gates and the indeterminate band are retired.

The 2026-10-01 fame audit recorded these backlink counts. Clears the
fame gate: Befunge 381, Underload 167, Thue 155, Malbolge 129,
INTERCAL 103, FALSE 91, Fish 91, Unlambda 89, Smallfuck 66, FRACTRAN
65, Piet 65. Below the fame gate: Whitespace 58, Forth 57, Chicken 55,
Shakespeare 54, LOLCODE 47. Rejected: Brainloller 26, Braincopter 14.

Existing fame exceptions must still clear the bar. Whitespace was removed at
58 backlinks.

<!-- CURATION-CENSUS:START -->

The 2026-10-06 census (`snapshot.json`) records each
language's backlinks and route: 21 clear the fame gate
and 74 are first implementations.

<!-- CURATION-CENSUS:END -->

### Removed languages

Funge-98 (31, two dozen implementations) was removed on 2026-10-06. The six
languages implemented elsewhere before the 2026-09-27 rule (123, BF-PDA, BIO,
Jaune, NoComment, Sophie; 2-10 backlinks) were removed on 2026-10-14.
Vandevelo (3) was removed on 2026-10-21 under the scaling rule: its shipped
source is `O(T log n)` characters and no bound for every program is known
either way.

Four languages left on 2026-09-18 with linearity unproved and no language
lower bound; three stay out under the scaling rule:

- %^2^-1: the planner hit a totality wall (30631e3bc).
- Interprogck8: `DownAccLines` reach and non-nesting capture blocked the
  generator (30631e3bc). It returned (5bb5a565c) with a `Theta(T log T)`
  lane build; shared window rungs made it linear (2026-10-22).
- WII2D: its 256-domain cost policy had no readout rule (30631e3bc).
- COD: the template build was `Theta(T**2)` (03131147d). A read-mode
  decision tree, re-attempted 2026-10-21 and executed, reaches
  `Theta(T log T)` area: 84,510 cells at n=8 against the removed build's
  942,668 characters.

### Notes on individual languages

- Bitwise Cyclic Tag (181) also adds the cyclic-schedule axis.
- Deadfish (315) is interpreter-only because it has no input vocabulary.
- Quassaunt (3): the `%%Multithread` extension the wiki lists apart from
  the language is not implemented; the interpreter refuses it.
- SendStuff (3): the extended language (`/` commands, `{}` node sets,
  fragments, strings) is a separate version on the wiki and is not
  implemented.

- [Cyclic tag](https://esolangs.org/w/index.php?title=Cyclic_tag_system&oldid=156412)
  (94) clears the fame gate despite duplicating an earlier queue language's
  consume-one-bit axis.
  The 2026-10-01 audit pins consume-one-bit semantics: append the current
  production iff the bit is one, then advance cyclically; empty data halts.
  With no specified I/O, the package adopts BCT's initial-queue embed and
  final-deleted-bit answer. Serialize productions with semicolons, then a comma
  and the initial queue; preserve empty productions and require at least one.

  For T = 2**n, productions i = 0..n-1 append 2**(n-i) zeros; production n
  appends `1`. The remaining 2T productions alternate table bits with empty
  productions. Initial data embeds the n ordered bits with uniform `0`/`1` fills,
  then `1`. For row r, the inputs leave 2r zeros before a new sentinel; those
  zeros skip 2r productions, and the sentinel appends table[r]. The next empty
  production consumes the answer and halts.

  A non-constant table's source is exactly 5 * 2^m + 2n + 1 characters for
  m essential inputs (5T + 2n + 1 when all are) and execution takes
  n + 3 + 2r steps; a constant table's source is n + 2.
  Emission writes 2(T-1) padding zeros and 2T table productions without
  search: O(T) build work. Tests execute 309 tables and 3,352 rows,
  exhaustive through three inputs, then constants, parity and eight seeded
  random tables per arity four through six; probes sampled through n=14
  reach at most 81,949 characters and 32,783 steps. Published evolution,
  zero-no-append, empty-data, empty-rule and nontermination controls passed.

- Emmental (43) is implemented elsewhere and fails the backlink gate;
  no intrinsic axis is established.
- Prelude (13) is implemented elsewhere and fails the backlink gate;
  no intrinsic axis is established.

The 2026-10-01 fame audit covered eight census candidates:

- [Boolfuck](https://samuelhughes.com/boof/) (76): integrated with a
  native decision tree over single-bit cells: each input byte's low bit is
  read onto its own cell and tested in place, one flag interleaved beside
  each bit, so every node costs O(1) commands and rendered size stays
  linear in T. Little-endian bit I/O supplies zero at EOF and pads
  partial output bytes.
- [Subleq](https://esolangs.org/wiki/Subleq) (83): integrated with unbounded
  integers, direct jumps, `-1 B C` byte input (EOF raises), `A -1 C` byte
  output, and negative jumps halting. The shared packed decoder stores
  T/n chunks of n bits, with O(n) read instructions: O(T) rendered text.
- [///](https://esolangs.org/wiki////) (88): integrated with ordered
  one-character `a`/`b` embeds. Binary-to-unary substitutions form the row
  index; 2^m fixed sweeps, for the m inputs the table depends on, consume
  that many two-character table entries.
  Escaped future patterns prevent earlier sweeps corrupting later rules.
  The selected entry becomes 0/1 and the suffix is deleted. Source is
  exactly 20*2^m + n + 53 characters, plus k + 10 for k = n - m > 0
  ignored inputs; a constant table is n + 9.  Build work is O(T).

The constructions supply the bounds; dense size-difference ratios at
n=8, 10, 12 are measurements over the same corpus: Cyclic tag 3.997,
Boolfuck 3.981, Subleq 1.994, /// 4.000.

- [HQ9+](https://esolangs.org/wiki/HQ9%2B) (136): interpreter-only.
  No instruction reads input. `H` and `9` emit fixed non-Boolean text; `Q`
  emits source containing `Q`; `+` emits nothing. No program emits a bare
  Boolean answer. Output formatting and case are pinned in the interpreter.
- [Nope.](https://esolangs.org/wiki/Nope.) (131, 2026-10-03): interpreter-only.
  `ConstantLanguage("Nope.")` ignores source and input, so neither runtime
  input nor source embeds can change its output. Accept arbitrary source,
  including empty source, under those constant semantics.
- [大白话](https://esolangs.org/wiki/大白话) (134): deferred. The command table is
  explicitly partial; expression precedence, complete block grammar, library
  semantics, and embedded-language dispatch are unspecified. A restricted
  implementation would need a separately documented dialect, not invented semantics.
- [Trivial brainfuck substitution](https://esolangs.org/wiki/Trivial_brainfuck_substitution)
  (112): excluded as a family, not a single language. Its backlink count
  does not establish fame for any particular member.

### Rejected and deferred candidates

The 2026-09-27 audit closed these candidates:

- Self-replicating marbles leaves section order and collision timing undefined.
- Wirefunge leaves initialization open and duplicates an earlier grid
  language's gates.
- Bytemap leaves byte order, division faults, and optional 8bpp undefined.
- Gifunk defines motion through APNG/GIF frames but no instructions.
- Turing Paint is obscure but already implemented.
- Befunk is obscure but already implemented.

The 2026-10-01 non-text screen deferred [BOOMOP](https://esolangs.org/wiki/BOOMOP):
its entry/termination brightness metric, face selection at ray-edge hits, and
equal-distance teleport anchors are unspecified. Character I/O is explicit;
generator feasibility remains unaudited pending routing clarification.

The 2026-10-15 intake deferred [Semqain](https://esolangs.org/wiki/Semqain):
single-thread semantics are fixed, but thread scheduling, `[+` on an empty
message queue, and `[` sub-commands 4-15 are unspecified. A threadless build
would be a restricted dialect.

HuePrism, BitCode, PicCode, Brainloller, Braincopter, and the game-save
languages remain rejected from the same image-source screen.

## Specification decisions

Where a language's wiki page is silent or contradicts itself, the package picks
one reading. These are those choices.

- 6-5 accepts operands beyond its specification; generators use `0..35`.
- FALSE's `ø` pick counts from zero, so `0ø` is `$`; the description ("dup
  the nth stack item") does not say where the count starts.  Reading a
  variable before storing it raises rather than inventing a value, and a
  character that is no command is ignored the way whitespace is -- the spec
  states neither.  Integers wrap to signed 32 bits (the spec's width) and `/`
  truncates toward zero, and `O` is accepted as an ASCII spelling of the
  non-ASCII `ø`.  `^` answers the spec's `-1` at end of input, which
  the shell reaches by catching the port's `EOFError`: raising instead made
  the reference's own cat loop, which tests `^` against `-1`, a crash.
- FRACTRAN has no I/O in the language, so this package reads the starting
  value from the source's first token and prints the value the run stops on.
  Prime-power products (`2^3*5` is 40) abbreviate starting values that would
  otherwise need thousands of decimal digits.
- Thue is nondeterministic by specification -- the rule *and* the position are
  drawn at random through the shared `randomness` hook. A fixed tie-break
  would change overlapping-rule programs; `--seed` makes the draws repeatable.
  The generator writes rules that never overlap,
  so each state it reaches has exactly one rewrite and the draw cannot change
  the answer; `tests/generators/test_boolean_thue.py` asserts that over every
  table to three inputs, and checks the answer under three seeds and the
  unseeded draw.
- Unlambda's `@` reads a Unicode character, including newlines. At EOF,
  it hands its argument `v` and clears the current character; `?x` and `|`
  then take their no-character branch.
- Bitdeque `GOTO n` counts from 1, as the wiki's "the Nth operation" reads;
  a target past the last command halts and a taken `GOTO 0` raises, both
  unstated on the wiki. The generator's labels match this.
- brainfuck uses wrapping bytes, a tape growing in both directions and EOF
  errors; its page allows cells left of the start, and two of its Hello
  Worlds need them. Its page describes implementation conventions rather than
  conflicting requirements.
- Line leaves cell width and tape boundaries unspecified: cells are unbounded
  integers and the sparse tape extends in both directions.
- Flowchart leaves path timing, cursor ownership and equal-distance junctions
  unspecified. Paths take no time, as the wiki's eight-pointer Hello World
  requires, so a step runs one node per pointer in the spec's order; cursors
  are per pointer; junctions prefer straight, right, then left. I/O is
  byte packing, low bit first, as the spec says; EOF reads empty, and the
  wiki cat's final empty pop pads to a trailing NUL.
- LaserFuck inherits Brainfuck commands without defining EOF: exhausted input
  raises `EOFError`.
- SStack has no example with a stated output on its page; its brainfuck
  interpreter is marked untested. Popping an empty stack reads 0 and leaves it
  empty, `:x:` peeks and raises `HaltError` above 255, EOF raises, and
  whitespace is discarded anywhere, inside a token too.
- BrainIf rejects unknown commands, including those under a false guard.
  `inc`, `left` and `right` remain aliases for the canonical commands.
- SLOW ACV MAMMALIAN rejects unknown words; commands are uppercase and
  whitespace-delimited. The Hello World fixture omits prose annotations.
  Its storage range is `0..255`, but EXCRETE and PRONOUNCE say modulo 255;
  `cell_modulus` and `io_modulus` select 255 or 256; cells default to 256
  and I/O to the page's 255.
- Alight retains infix, left-to-right expressions for compatibility with
  existing programs and generators, despite the explicit postfix rule.
  Its cat examples use infix expressions; `expression_syntax="postfix"` follows
  the conflicting Operations section. Three-argument `at` defaults to
  `list_update="in_place"`, which the reversed cat needs (it discards the
  result); `"copy"` follows the prose's "return a copy".
- CV(N)(C) accepts ASCII `g` as an alias for `ɡ` to run the wiki greeting.
  It discards LF to run line-wrapped generated programs; this is a source-rule
  deviation, not a specification gap.
- Grapheme discards LF to run line-wrapped generated programs; this is a
  source-rule deviation, not a specification gap. It defaults to `integer_conversion="between_letters"`: `FAFY` prints
  1. `"after_each_letter"` includes the prose's final multiplication and prints
  10. Both integer mode and string conversion follow this setting; generators
  adapt their literals. The same page’s truth machine requires 1 rather than
  the prose’s 10. An unset variable reads as its own name, which the page’s
  variables example (`VARIABL`) requires.
- Packlang literals default to decimal; `literal_policy="binary_digits"`
  treats literals containing only `0` and `1` as binary. The same page uses
  decimal `101` in Hello World and binary digits in PlusOrMinus and dependency
  examples. Character input preserves newlines; EOF supplies newline to `charGet`.
- ROTfuck defaults to `rotation="backward"` (`+` turns into `]`): the wiki's
  one-character cat `,[` then echoes; `"forward"` follows the prose (`+` into
  `-`), under which the cat fires an unmatched `]`. A jump seeks its partner
  before the rotation ("after the instruction is executed"). The wiki Hello
  World prints no greeting under any direction or seek timing. The generator
  targets either direction.
- Smu reads an unset variable as empty, as the wiki cat needs at EOF.
  Bits ride bytes low bit first, so the cat copies bytes;
  output `=` prints nothing, `(` or `)` halts, and an unbalanced program
  popped to run halts. The page's expanded cat drops the `=` after `(+=)`
  and forces a leading 1; the compact source fixes the repair.
- Pinyin is rejected: its spelling rule contradicts its examples and its
  input-1 truth-machine example has no deterministic reading.

## Source-count bound

- Unary: <a id="unary"></a>
  Valid sources encode only their zero count; whitespace adds no functions.
  Sources of length at most L supply at most L+1 functions. Covering all
  2**T truth tables therefore requires L >= 2**T - 1 somewhere; writing
  those zeros has the same generation-time lower bound.

  The generator reads bytes 0/255 in input order. Halt answers zero; a fixed
  empty loop answers one. Complemented reads feed a folded decision tree;
  constants, projections and conjunctions use direct guards. Encoding m
  commands needs between 8**m and 2*8**m - 1 zeros. Cap raw export at 32 Mi
  characters, expanded generation work at 256 Mi characters, and gzip files
  at 256 KiB. Nine inputs is an absolute ceiling; most nontrivial tables
  hit the work cap earlier. Removing the resource screens leaves
  a finite encoding for every table.

  The eight-command AND guard `,>,[<[]]` emits 27,452,351 zeros. All four
  rows execute: three halt, 11 cycles, and each consumes two inputs. The
  committed AND example stores gzip text; program size counts expanded characters.
  Compression is streamed in 64 KiB chunks; the interpreter counts decompressed
  zeros without retaining expanded source. The default unwrapped AND occupies
  26,712 gzip bytes. `str(program)` exports plain text; `to_gzip()` and `save()`
  export files. The CLI writes gzip by default and `--plain` exports text.
  Decoded Brainfuck uses wrapping bytes, a tape growing in both directions
  and zero at EOF.

  Nine-input constant false emits 230,087,533 zeros and 223,664 gzip bytes.
  Generation took 0.658 s; all-zero/all-one rows halted after nine reads in
  0.209/0.208 s. Ten-input constant false needs 1,840,700,269 zeros and was
  priced but not built. Arity is not a uniform promise below either cap.
