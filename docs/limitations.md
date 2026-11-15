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
- Forbin expression calls retain their documented host-recursion limit.
- Streetcode's four-way junction is an implementation convention: the source
  specifies only a two-road choice.

- NQ ignores input whitespace; `R` reads through EOF. Empty-queue reads
  and writes fail. The cyclic-tag example switches `>1` to `>0`.
  The history does not settle ungrouped guard extent or skip wrapping.
  `guard_binding="opcode"` (default) skips one opcode or whole grouped guard,
  including across source wrap. `"recursive"` skips a complete guarded
  instruction whose target must fit its lexical group or source.
  `+0->1>0+2WH` prints `#` under opcode binding and underflows under recursive
  binding. Neither choice establishes author intent; generated programs have
  identical source, execution and state under both.

### Image-based languages

<!-- RASTER-SOURCES:START -->

Line and Piet carry a raster source: `generate` returns a
`ProgramArtifact` containing a `Raster`; `run` takes it or a PNG path
through the shared codec; `describe` reports `source_kind="raster"`.

<!-- RASTER-SOURCES:END -->

Text and image-based languages share the same VM and step rules.

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
discarded, never left unread, and output follows the last read. Leaving a
trailing ignored input unread would make input consumption depend on the table. The measured savings were 9-29%
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

See the [optimization criteria](CONTRIBUTING.md#what-makes-a-generator-optimization-worth-shipping).

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
- FRACTRAN writing each guard as one literal (`29*11` as `319`) saves
  9.6-10.4% of random tables at n = 6..8, 8.3% at 10 and 6.8% at 14
  (parity 7.1-9.2%): the guard primes lengthen, so the `*` saved is a
  falling share.  The factored spelling stays because it keeps runs on
  the interpreter's prime index; literal guards outgrow its base cap and
  fall back to the integer scan, so shipping them also needs an index
  that factors guards over the program's own primes.
- Object Disoriented's last-level short forms save 2.9% at n=7 and 0.6% at
  n=10; parity 7.8% at n=8.
- Cheapest names to the most-used nodes: `subtree_ids` already numbers
  bottom-up, so reordering can save at most 0.08-0.40% in Bleh, Stisp,
  SendStuff and Codesick; re-laying BitDeque's jump targets at most 5.8%.
- Defaulting to the smaller-area balance layout (2026-10-22; shipped for
  Piet, ArrowQueue and B-tapemark):
  - Clockwise's narrow route and banded strips (49-58T cells at n=10..12)
    lose to the flat default's 25T + 40n + 20; the strips also grow
    superlinearly in time (2.9 s at n=14).
  - LaserFuck's balance widths save 35.5% at n=6, 21.5% at n=7 and 11.9%
    at n=8.
  - Circuit Diagram's balance saves 12.4% at n=7 and 15.2% at n=8 but
    searches: 1.3 s at n=10, 24 s at n=12, 524 s at n=14.

### Searches

Malbolge's table-independent navigation (`emitter.py`'s `goto`) scans the
next 32 cells and weighs jumps against walking, using pointer chains, cycle
follows and bounded second-jump scans. Its main line ends at cell 6,548 for
one input, below the 6,561 boundary. On the recorded memory states, the
cheapest paths with at most three jumps per `goto` end at 6,607, and
allowing four jumps brings the end to 6,558.

The bounded-read lower bound concerns fixed probes plus cycle data
(effective start and target). Across the traced states and their
single-cell unwrite variants, changing any of 59 distinct cells can
change the optimal first step. A fixed probe set of at most 58 cells
therefore fails. A separate witness excludes even the full written
pattern, and one state forces 15 reads with adaptive probes. The
restricted algebraic signature (derived indices and per-trit algebra,
with arbitrary constant equality and random access excluded) remains
open for terms of any size. The classified invariant relations gave no
separating product relation.

Short-layout seeds and stubs through fifteen inputs use canonical actions.
Rotation count and the composed per-trit map reduce 1,365 chains of up to
five operations to 59 actions, preserving all 939 reachable addresses.
Placement selects the lowest-cost feasible action. Hub addresses need
trits in {0, 2}, and their two data cells must clear tables and earlier
placements.

### Largest input counts

`describe(language).generator_max_inputs` reports the three caps:

- Befunge supports thirteen inputs via a six-bit ASCII lookup in the
  80×25 grid. Finite source space excludes some sixteen-input tables
  ([exceptions and walls](proofs/index.md#exceptions-and-walls)).
- Unary's current unrolled generator supports [at most nine inputs](#unary).
- Malbolge supports all tables through sixteen inputs. Positional
  addressing packs the first inputs three bits per two-trit digit, and
  the last input selects one of two answers per cell. At seventeen the
  shipped construction covers tables that ignore an input or are constant
  on Hamming-weight classes. Named rows of both families execute in the
  sparse suite. See the [construction summary](proofs/index.md#malbolge-bound).

Malbolge's seventeen-input construction and impossibility questions both
remain open. The current two-answer readout would need 65,536 cells in a
59,049-cell store. The counting proof excludes some eighteen-input tables
and needs another 46,076 bits of structure to exclude a seventeen-input
table. A length restriction fails on a ten-input witness whose answer
depends on cell 58,967. A per-program dependence restriction fails on the
one-input identity program `'o'*59046 + '/<v'`, where every cell matters.
A bound over one normal form per table remains open.

Construction-specific results for seventeen:

- The address-independent window conflict graph has independence number
  8 and chromatic number 12. State conditioning can attain eight clean
  meanings per address with four interval states, at additional routing
  cost. The archived three-cell, seven-meaning build had room for 2.77
  cells per jump against a 2.99 lower bound on the reconstructed routing
  model. The original routing and integration records lack retained
  tooling, so the exact historical comparison remains unverified.
- Adjacent-cell, threaded, streaming, hub, membership, permutation and
  marching approaches hit reachability, layout or measured cost limits.
  Native marching controls establish finite instruction reuse. The
  word-mediated landing variant executes one case at 21 cells per
  deposited word. A full build must still fit the 9,897-cell complement
  and pass the parity and per-row checks in the [roadmap](roadmap.md).
- Native scratch controls include arithmetic halving (33 cases on one
  13,368-character program) and a shared two-word `crazy` fold (17 input
  pairs on one 4,428-character program). Mutants failed both controls.
  The reduced LAST-only layout was already 8,432 cells short before the
  remaining query and selector. General ASCII input, packed addressing
  and bit selection still need a full composition.
- Without `i`/`j`, reset execution keeps `C == D`. A `p` gets its own
  instruction character, and the input pair (49, 48) is unreachable.
  That restricted machine cannot express NOT at any length.

See `a2373c8aa:docs/limitations.md` for the detailed Malbolge measurements,
counterexamples, and provenance under **Searches** and **Largest input
counts**. The older `scripts/malbolge17/` archive survives at `09ab2fad`
and `b42d79e` on the old module layout.

### Size lower bounds

### Scaling

Size is measured from rendered output, and correctness claims require running
the generated program. A generator guarantees its size class, not its
constant. The [optimization criteria](CONTRIBUTING.md#what-makes-a-generator-optimization-worth-shipping)
cover constant-factor changes. Execution measurements exclude
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
  its construction exemption.
- Dig has 10.9% repeated-node potential at n=5; its admission tests support
  its construction exemption. Its shared pool is 2..10 unique 64-row classes
  indexed by one decimal digit over 1..6 prefix bits; a larger pool needs a
  multi-digit index. A finished sharing layout whose `_chain_lanes` corridor
  crosses another class's lane arrow or branch `$` is rejected and falls back
  unshared: 131 of 602 shared layouts in the n=12 scan behind this entry
  (random 64-bit leaf classes mixed with constant leaves). A per-class gutter line removes the
  rejection but shares no more (26 to 24 lane layouts) and grows shared
  layouts ~5%: a crossed leaf or constant read row kills the gutter, and
  recovery would save nothing anyway: at n=12 the indexed leaf decoder
  emits 11-22x less area than every shared layout, which `generate` never
  picks there.
- Boolfuck has sub-gate repeated-node potential: 2.5% of emitted size at n=5,
  pinned in `tests/generators/test_boolean_boolfuck.py`.
- Home Row is a lookup that names no decision-tree node.
- ROTfuck is a lookup that names no decision-tree node.
- Dimensional is a lookup that names no decision-tree node.
- LaserFuck's path-dependent leaf code makes equal subtables unequal text.

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

Fifty-seven ledger cells are `at most` throughout and twenty-three more past an
exact range (2026-10-23, counted from the ledger):

- Route race: the shipped program is the shortest of several forms or
  layouts, so the worst table is a maximum over a minimum and switches
  with the winner. See the [generator ledger](proofs/index.md#generator-ledger)
  for the bounds. For Back, at n = 8 the full pair comb
  takes 3,712 cells against the fold's 3,312. The area comparison limits a
  selected comb to 114 rows at n = 8 and 218 at n = 9. Geometric subtree
  cuts attain the execution bounds at both arities. Later execution retains
  the global upper bound. Other examples include ArrowQueue execution,
  Polynomial execution (C - 2
  at n = 3, 4 over every table; C minus the doubling levels, 60, 95, 131, 198,
  329, 588 at n = 5-10, witnessed),
  Boolfuck workspace,
  Circuit Diagram workspace and scaling (an H-tree pool from n = 9 caps
  the area; the default measures at most 0.26 of the cap), Container scaling (the threshold build loses
  to the tree from n = 6: 883 against 1,076) and workspace, CVNC
  execution, FALSE scaling and execution (reached at n = 4, 5 only; at
  n = 6 diagram 292 against expression 293), Fargo all three, For Thorn
  execution, Object Disoriented scaling, Piet all three,
  Smallfuck execution, Streetcode workspace; scaling for Algebraic Programming
  Language (144 against 182 at n = 4, exhaustive; the reduced
  diagram's smaller bound holds through n = 14), Packlang, Painfuck (historical before 2026-11-02: 232 against 239 at n = 4), 6-5 (105 against 166 at
  n = 4, the shorter of two layouts to n = 5),
  SStack (the bound is exact through n = 4), Underload (exact at n = 4, 5) and
  Unlambda (to n = 2), and Brainfuck (13-29% loose, n = 5..8), For Thorn,
  Smallfuck, Subleq and AddSubJump (per-candidate sums); Boolfuck scaling past n = 7 (the gates take its
  worst: 1,968 against 4,681 at n = 8); S*bleq scaling below n = 11 and BFStack workspace below n = 9 but n = 5 (the bound charges every open loop
  bl(L) bits; positions below 2^(bl(L)-1) cost fewer. Smallest gap by table:
  n = 4 11 (exhaustive, 165 against 176), n = 5 0 (exact: 0^16 1 0^15 measures 321); n = 6..8 not re-measured since the decoder race went, 2026-10-28).
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
  Painfuck workspace (historical before 2026-11-02: slack 1
  at n = 3..6, never 0); Decleq scaling (historical before 2026-11-02 jump threading: 8, 10, 14 short at n = 2..4,
  exhaustive); Bitdeque scaling (GOTO digits by layout; 358 against
  400 at n = 4, exhaustive); 3x workspace (exact key bits; 1.3-1.5x at n = 3..6, 1.8x at n = 9);
  Malbolge workspace (about 470 data-dependent re-encipher widths, the
  bound now 1.03x).
- Coincident peaks: the bound adds component maxima no single row or
  table reaches together, and the exact peak needs a per-row profile or
  a joint optimisation. Algebraic Programming Language execution (a
  random half beside complemented (n-1)-parity runs 296 > 293, the parity
  path, at n = 9: executed definitions K add to the longest path);
  Circuit Diagram execution (native mux nodes and competing banks need not
  attain the derived bound); ABCDirection, Algebraic Programming Language,
  FALSE (1.3x past n = 8, per route), For Thorn, Object Disoriented (1.7x,
  per level) and Packlang workspace; Polynomial workspace; SStack execution (exact at n = 5 and 8
  only); Unlambda execution and workspace; RAM0 scaling (a repeat goto
  needs a zero child already built); SendStuff scaling (a constant child
  replaces the branching node the bound also prices); 3x scaling (20-28%
  below F: a complement copy collapses the subtree F prices as a split, so
  no table reaches both its head and tree maxima; exact worsts at n = 2..4
  run 72-76% of F).
- Fenced ranges: exact to a measured arity, unproved past it; each reopens
  only as stated.
  - SMU scaling past n = 16: the worst is a per-arity design optimum (the
    binding choice is the split at 17, tie-breaks at 18, the mixed share
    at 19, XX multiplicity at 20), no rule found; at 21 the exhibited
    family's 98,929 pair slots cannot hold 131,072 places.  Reopens with a
    rule or a successor family.
  - INTERCAL uses exact per-program statement counts and worst-row written
    workspace; all-one inputs attain every named mask's two-bit peak.
    Separate n-only formulas are conservative ceilings, not maxima.
    Historical maxima belong to the old assignment policy: execution was
    checked through n = 26 (12,091,691 workspace bits; 4,461 MB peak RSS),
    and workspace through n = 27 (2,164,188 streamed statements; 680 MB
    generation peak; 23,818,646 bits). Its source witnesses reached n = 23;
    those maxima do not describe the select compiler.
  - S*bleq scaling past n = 28: one-off builds attain P at 26, 27 and 28
    (105,463,455 characters, 3.30 GB peak), the harness at the scaling
    arities to 25; the route's peak doubles per arity, about 6.5 GB at 29.
  - What!? past n = 22: the witness builds to 26 and E(22) = 8,519,845
    steps and W(22) = 587 bits are executed, but the interpreter's
    one-object-per-token parse loads n = 22 in 3.15 GB and dies at 23.
    Reopens with a leaner parse.

## Curation

<!-- COLLECTION-SIZE:START -->

The collection has 117 languages.

<!-- COLLECTION-SIZE:END -->

Its floor is 31. Deadfish, HQ9+ and Nope. are interpreter-only.
The 2D screen admitted Alight and Super SNUSP and rejected Pinyin.
Screening data is in `a7b3f7abd:docs/limitations.md`.

### How a language is admitted

Fame admits esoteric languages with at least 50 unique esolangs linking
pages. Resolve title redirects, exhaust `list=backlinks` continuations,
include redirect links across all namespaces, and deduplicate by page ID.
Pause at least three seconds between requests.

The cutoff is policy, not a measured popularity boundary: 60 from 2026-10-01,
lowered to 50 on 2026-10-28, where it admits every language in Morr's and
Kneusel's selections (below). The page must describe an esolang: Forth (57)
and C++ draw backlinks as influences, and models with no syntax (Tag
system 54, Turing machine) are not languages.
Record resolved title, date and count; missing data means unassessed
(`unassessed = true`, which `finish` flags until the count is recorded). Low
backlinks count against only old languages; Wikipedia pageviews are not a
gate.

Below 50, a language is admitted only as a first implementation: at its
original admission (a removal later undone keeps the date), no outside
implementation exists. An outside implementation is posted publicly, as
source or a runnable link, and implements the page's semantics; one a
review shows misreads them does not count (ROTfuck's), one that only
crashes on large programs does (Polynomial's), and a translation scheme
written in prose does not (Stun Step's Talk-page mapping to Reversible
Brainfuck). Each package records the
date as `admitted` in `[curation]`, and a known outside implementation as
`outside_implementation`; `tests/tooling/test_language_toml.py` refuses a
member whose outside implementation predates its admission. A first
implementation also needs a generator: interpreter-only is the fame
route's alone.

A route admits a language only when its specification fixes the core
semantics. 3D Brainfuck was removed on 2026-10-06: its page never says how
a linear source places blocks in the grid or what the generation pointer
does, so its interpreter invented the core, the invented semantics the
大白话 deferral rules out. Transistor (2) was built and dropped on
2026-10-07 for the same reason: its page gives no grammar and no I/O, and
its one loop example calls an undefined `or`.

Nor does the first-implementation route admit a token substitution of a
collected language: a fixed bijection between command tokens (whitespace
and comment conventions aside) under which every program behaves the same,
both ways. An implementation of the original plus the renaming already
implements it. Ook! (brainfuck) is the anchor and excludes Trivial
brainfuck substitution as a family. A 2026-10-29 screen of 13 nearest
pairs found none among collected languages, each refuted by a run
counterexample (S\*bleq reads 0 at EOF where Subleq raises; Piet++ has 32
commands to Piet's 17). Fame admissions are never excluded.

Scaling removes: an uncapped generator whose `O(T)` generation time and
emitted size are neither proved nor ruled out by a language lower bound
takes its language with it (Unary and Ascenic keep theirs on proved
bounds; Malbolge's cap leaves no asymptotic question). Adopted 2026-10-21;
Vandevelo was removed under it. It is the one ground that depends on the
repo's work.

The rules above govern membership. The `bf_derivative` field in
`[curation]` records the wiki category. A rule change lands with its
membership diff in one commit. See retired criteria and counterexamples in `a7b3f7abd:docs/limitations.md`.

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
65, Piet 65, Whitespace 58, Chicken 55, Shakespeare 54. Not esolangs: Forth
57. Below the fame gate: LOLCODE 47. Rejected: Brainloller 26, Braincopter
14.

Existing fame exceptions must still clear the bar. Whitespace was removed at
58 backlinks under the 60 gate and readmitted at 50 (2026-10-28).

### Removed languages

Funge-98 (31, two dozen implementations) was removed on 2026-10-06. The six
languages implemented elsewhere before the 2026-09-27 rule (123, BF-PDA, BIO,
Jaune, NoComment, Sophie; 2-10 backlinks) were removed on 2026-10-14.
Vandevelo (3) was removed on 2026-10-21 under the scaling rule: its shipped
source is `O(T log n)` characters and no bound for every program is known
either way.
Three left on 2026-10-29 on the route, an outside implementation predating
admission: Polynomial (LegionMammal978's Mathematica on its Talk page,
2015-07-09; collected 2020-07-12), Piet++ (`pietpp.py` in
github.com/iannmiui-png/miusoft_paint-98, 2026-08-29; collected
2026-10-03) and Tiangou (Monochromeninja's Python on TIO, 2021-06-01;
collected 2026-10-27).
Minifuck was removed on 2026-10-31 under the spec rule: its generator's
emission model depends on non-command characters occupying instruction
positions for `[` skips, which the spec's text does not support (the page
counts only 3 instructions), and under the spec's natural reading the
shipped generator diverges on 258 of 258 corpus rows. A rebuild grounded
the general, two-state, parity, constant, unary and gap routes, but the
stored route is structurally blocked — no command-only equivalents at
lengths up to 12 and 15 on exact searches, and its travel crosses
row-dependent cells — so full grounding is unreachable. The rebuild branch
stays unlanded as the record.

Every exclusion and its ground:

| Ground | Languages |
|---|---|
| route | 123, BF-PDA, BIO, Jaune, NoComment, Sophie, Funge-98, Emmental, Prelude, LOLCODE, Brainloller, Braincopter, Turing Paint, Befunk, Factor, Polynomial, Piet++, Tiangou |
| spec | 3D Brainfuck, Transistor, Pinyin, Self-replicating marbles, Wirefunge, Bytemap, Gifunk, BitCode, PicCode, Minifuck, the Minecraft ports; deferred: 大白话, BOOMOP, Semqain |
| token substitution | Trivial brainfuck substitution |
| scaling | Vandevelo, %^2^-1, WII2D, COD, ZTOALC L |
| no generator | HuePrism (no input), Nopstacle (its blank and `#` spell no input embed) |

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

- B-tapemark (fenced 2026-10-31): the page does not settle which grid's
  marker moves after a swap.  It says the symbol on the first grid is
  executed and then "the position marker" is moved, each grid has one, and
  neither example swaps.  All five page revisions back to the 2013 creation
  leave the swap and marker wording unchanged, and no example in any
  revision swaps.  The shipped reading is correct on all 218 corpus rows.
  Under the other reading
  (the executing grid's marker moves) 147 of 218 rows hang (step cap at
  least 50,000 against at most 759 shipped steps); the 71 clean rows are
  exactly the swap-free executions (constant programs and each stage
  program's all-ones row, the only row whose every compare misses;
  witnesses n=1..4 all rows, parity/random n=5..6 sampled, narrow layout
  included).
  - Algebra: the traced `0110` round trip (swap at X heading d0, back
    heading d1) puts the program marker's offset between readings at d0-d1
    and the data marker's at +d1, so no single trip is invariant; a
    cancelling second trip per branch needs sum(d1) = 0 with sum(d0-d1) = 0,
    e.g. each trip beam-safe (d1 = d0) with opposite exit headings.  That
    is a second copied gadget, entry and exit turning lanes and lane
    funnels on the match branch of every stage, in all three layouts.
  - Wide prototype (`0110` stage 0): a parallel walk on stage row 2
    (weight-1 `|` cells; the beam already executes the stage's own
    compare-column `|` heading E, the mismatch branch's +1 cell) plus one W
    `|` on row 3 cancels the +d1 offset exactly (+12 chars for the stage, 5
    of them the lane's cells; shipped behaviour unchanged).  The program
    half is blocked in the shipped geometry: the lane crosses the descent
    column (a `%` there is a no-op under both readings), but the beam
    travelling W on row 3 meets that row's own `\` and turns N into the
    copy row, and every other exit from the row-2 corridor is blocked by
    the copy row, the run cells or the compare turn.  A construction must
    relocate the run, descent and exit funnel together.
  - Wide redesign: built the same day (cancelling lane plus an intercept
    dropping the alt beam to a travel row that re-enters the next stage
    down its own entry column, exit `|` changed to `*`; witnesses n=1..4
    all rows and n=5..6 samples clean under both readings) at about +30%
    size (221 to 281 chars at n=2, 2,489 to 3,311 at n=8); held unlanded on
    its prototype branch.
  - Folded is fenced: the fold links at local column 9 sever the lane's
    east passage (the alt beam turns N at the link; a parity control runs
    31 of 32 rows alt-bad), and fold 0's run is unrideable with a deficit
    that cannot be paid.
  - Narrow is fenced: at weights 1..2 the only candidate intercept column
    is the shipped descent column itself, and with the lane hand-patched
    and accounted exactly the template `\` at local 7 turns the beam N.
  - Both readings were implemented as a registered dialect with a
    dialect-parameterized generator (222-row corpus correct under each
    reading's own semantics, the alt dialect's programs no larger than the
    default's), withdrawn the same day it was built, and landed
    2026-11-01 at Bangyen's direction to match NQ's registered-dialect
    pattern: the fence above stands as the record of why the second
    reading exists, and the port re-applied the parameterization over
    the area-strip generator (default-dialect output byte-identical,
    914 size measurements unchanged).
- Bitwise Cyclic Tag (181) also adds the cyclic-schedule axis.
- Deadfish (315) is interpreter-only because it has no input vocabulary.
- Quassaunt (3): the `%%Multithread` extension the wiki lists apart from
  the language is not implemented; the interpreter refuses it.
- SendStuff (3): the extended language (`/` commands, `{}` node sets,
  fragments, strings) is a separate version on the wiki and is not
  implemented.
- S*bleq: the interpreter also runs the store targets `ab` (S*bl*q) and
  `b` (Subl*q), each with an indirect form, but no registry entry or
  dialect selects them and the generator emits base S*bleq only.
  Registering one means generalizing the hoisted tree and packed decoder
  to its store target, execution-gated; an indirect form dereferences its
  operands, so it needs a pointer cell per operand, a different
  construction.

- [Cyclic tag](https://esolangs.org/w/index.php?title=Cyclic_tag_system&oldid=156412)
  (94) clears the fame gate despite duplicating an earlier queue language's
  consume-one-bit axis.
  The 2026-10-01 audit pins consume-one-bit semantics: append the current
  production iff the bit is one, then advance cyclically; empty data halts.
  With no specified I/O, the package adopts BCT's initial-queue embed and
  final-deleted-bit answer. Serialize productions with semicolons, then a comma
  and the initial queue; preserve empty productions and require at least one.

  For T = 2**n, productions i = 0..n-1 append 2**(n-1-i) zeros; production n
  appends `1`. The remaining T productions are empty for a 1 and `0` for a 0.
  Initial data embeds the n ordered bits with uniform `0`/`1` fills, then `1`.
  For row r, the inputs leave r zeros before a new sentinel; those zeros skip
  r productions, and the sentinel meets row r's: empty, so the sentinel is
  the last bit deleted (1), or `0`, which is deleted last. The queue runs dry.

  A non-constant table's source is exactly 2 * 2^m + 2n + 2 + z characters for
  m essential inputs and z zeros in the reduced table (at most 3T + 2n + 1
  when all are essential) and execution takes at most n + 3 + r steps; a
  constant table's source is n + 2.
  Emission writes T-1 padding zeros and T table productions without
  search: O(T) build work. Tests execute 309 tables and 3,352 rows,
  exhaustive through three inputs, then constants, parity and eight seeded
  random tables per arity four through six; probes sampled through n=14
  reach at most 49,181 characters and 16,400 steps. Published evolution,
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
- Chicken is one JavaScript-valued array: the stack is its end, so a pop
  truncates and a load past it is `undefined` (the page's `undefined` and
  NaN examples need that). The input is all of stdin as one string, a
  jump counts from the cell after it, and running off the array exits.
  Integers are exact rather than doubles, a string reads as a number only
  if blank or a decimal integer, and only decimal `&#N;` unescapes. The
  stack array as an operand, a non-index store address and a load from an
  `undefined` source raise `HaltError`.
- Shakespeare's word lists are the SPL 1.2.1 lists as carried by shakespearelang
  1.0.0 (the original tarball was unfetchable), in `words.toml`; the
  Python package is a cross-check only. At most two characters stand on
  stage (a third entering halts, as the page says; the package halts only on
  the next "you"). The be-verb after "You" is optional (the Hello World
  fixture), acts number from I, a goto stays in its act and a missing scene is
  a load error. Integers are unbounded; quotient and remainder truncate toward
  zero. A read at EOF raises, so the Cat program echoes its input and then
  ends on `InputExhaustedError` (the package stores -1 and fails printing it).
  The page's Cat has `Ooen`, which raises; the pinned program is the repair
  `Open`. Number input is a signed token (the package reads digits only).
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
  at 256 KiB. This unrolled construction accepts at most nine inputs; most
  nontrivial tables hit the work cap earlier. Removing the resource screens
  leaves a finite encoding for every table. The language permits counted reads:
  seven-command `-[>,<-]` encodes 3,082,847 zeros and consumes exactly 255
  inputs using an independent byte counter; all-zero, all-255 and alternating
  streams halt after 1,277 commands and preserve the following byte.

  The eight-command AND guard `,>,[<[]]` emits 27,452,351 zeros. All four
  rows execute: three halt, 11 cycles, and each consumes two inputs. The
  committed AND example stores gzip text; program size counts expanded characters.
  Compression is streamed in 64 KiB chunks; the interpreter counts decompressed
  zeros without retaining expanded source. The default unwrapped AND occupies
  26,712 gzip bytes. `str(program)` exports plain text; `to_gzip()` and `to_file()`
  export files. The CLI writes gzip by default and `--plain` exports text.
  Decoded Brainfuck uses wrapping bytes, a tape growing in both directions
  and zero at EOF.

  Constant true decrements the last 0/255 read, then loops on the nonzero
  cell: six reads fit the cap at 230,087,415 zeros.

  Nine-input constant false emits 230,087,533 zeros and 223,664 gzip bytes.
  Generation took 0.658 s; all-zero/all-one rows halted after nine reads in
  0.209/0.208 s. Ten-input constant false needs 1,840,700,269 zeros and was
  priced but not built. Arity is not a uniform promise below either cap.
