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
- Piet emits and executes pixels.

## Source positions

VM instruction positions declare `ip_shape`: `offset`, `grid`, `line`, or
`opaque`. `tests/test_vm_protocol.py` checks every language and rejects
undeclared or misspelled values. Opaque positions have no source coordinate.

- Line extraction accepts anti-aliased PNGs only when strokes retain a connected
  dark core. The 3px scan fixture executes addition; a one-third-pixel shift of
  a 1px stroke is rejected with 921 unaccounted pixels rather than silently
  changing the program.

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

### Largest input counts

- Malbolge:
  Malbolge's source-embedded generator covers sixteen inputs. Through ten, a
  five-cell mixer maps rows to gap-3 addresses with three-cell answer stubs.
  Eleven through fourteen use collision-resolving pointer cascades; fifteen and
  sixteen use positional readouts, one cell per row pair. The representative
  dense, parity, constant tables were executed exhaustively at each shipped
  arity. Construction details and measurements are in
  [construction summary](proofs/index.md#malbolge-bound).

  Seventeen remains open. Native capture, semantic readout, footer dispatch and
  terminal-output components execute separately; no source computes an arbitrary
  full 17-input truth table. Raw record addresses can overlap executing code,
  so relocation must precede capture. The reduced LAST-only layout is short by
  8,432 cells before adding the remaining query, selector and metadata. This is
  a deficit for that construction, not an impossibility bound. See
  [the construction summary](proofs/index.md#malbolge-bound).
  The shipped cap remains sixteen.

  A cheaper seventeen-input layout is checked but unbuilt (2026-10-13). The
  sixteen-input readout gives two cells per 14-bit prefix, one each for the
  last group bit `b` = 0 and 1. A third cell per prefix forces one low digit to its
  missing value and moves that digit to the top. The three maps are disjoint, giving 49,152
  cells and leaving 9,897 (one cell wraps; reorder the top digit). That
  replaces the 8,377-10,449-cell address fold with two extra group-4 runs.
  Six run-time pointer cells (`_D_POINTERS`) cut sixteen's main line from
  5,505 to 4,038 cells; all 65,536 rows stay correct. Seven meanings per
  cell need the address parity: `p` with `A` all-2 then all-1, then ten
  rotations folded into an all-1 cell, gives it in 240 cells, 0 of 59,049
  words wrong (scratch, executed). Swaps `v` {0,3,4}, `u` {1,2} make the
  third cell's parity equal the first's for every prefix (model).
  Dispatch does not fit (2026-10-14, scratch, executed): the seven-class label
  window plus 14 hubs alone takes 5,155 main-line cells, leaving the line near
  7,200 against 6,562 before the third-cell fold and per-state transitions.

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
  2**177148` programs. There are `2**262144` truth tables on 18 inputs, and one
  program computes at most one table, so some 18-input tables have no Malbolge
  program. Malbolge is therefore a language exception, not merely a ceiling.

  Seventeen -- the registry target -- needs the count under `2**131072`, a
  factor `2**46076` below it, and counting does not get there. A length cut
  needs every answer to rest inside the first 43,690 cells, but cell 58,967
  alone flips row 299 at ten inputs (`0` against `1`, both executed). An
  alphabet cut needs 4 of the 8 characters at a cell to matter: single cells
  realise 5 to 8 distinct behaviours (12 of 20 sampled walked-code cells at 5 or
  more), and an every-line cap of `k` buys `log2(8/k)` bits in all -- one bit at
  `k = 4`. What is left is a dependence cut: every table-computing program's
  answer resting on at most 24,434 cells, the largest `K` with `C(59049, K) *
  8**K < 2**131072`. Per program it is false: `'o'*59046 + '/<v'` computes
  the one-input identity and every cell flips it, so only a cut over one
  normal-form program per table remains open.

- Vandevelo's fixed sparse-candidate cap forces Ω(T log n) emitted characters
  on an explicit odd-prefix family, where T = 2ⁿ. Character-level generation
  time is therefore superlinear for the shipped construction. A replacement
  with universal O(T) size and generation time remains open; no language-wide
  impossibility was proved. See [the bound summary](proofs/index.md#vandevelo-sparse-bound).

The no-`i`/`j` model cannot express NOT. Straight-line `c == d` from the reset
state gives a `p` its own cell's instruction character, one of 94 values in
33..126, and the input pair `(49, 48)` is unreachable, so NOT is not
expressible at any length.

Shipped limits, in inputs:

| Generator | Dense | Parity | Limit |
| --- | ---: | ---: | --- |
| Malbolge | 16 | 16 | Stubs need gap-3 readouts (none at eleven bits); the hashed cascade through fourteen resolves collisions over up to three levels and stops where their depth outruns the decoder. Fifteen and sixteen address positionally, three bits per two-trit digit, so no row collides; that positional readout needs 65,536 row-pair cells at seventeen in a 59,049-cell store. Three-cell packing remains unintegrated ([scaling](proofs/index.md#malbolge-bound)). |
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

- Circuit Diagram loading is dominated by parsing super-linear area.

- FRACTRAN's row-addressing tree costs `Theta(T log T)`, but that is not a
  language floor. The shipped generator gives equal subtables one state, so
  it names `O(T / log T)` primes of `O(log T)` digits: `Theta(T)` text, and at
  most `n + 1` fractions fire a run. At n=12 it emits 3.81 characters per entry
  versus 23.6 for the tree. The construction and the counting floor are in
  [fractran](proofs/index.md#fractran-bound) and `src/esolangs/languages/fractran/tests/proof_fractran.py`.

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
  multi-digit index.
- Boolfuck has sub-gate repeated-node potential: 2.3% of emitted size at n=5,
  pinned in `tests/generators/test_boolean_boolfuck.py`.
- Home Row is a lookup that names no decision-tree node.
- ROTfuck is a lookup that names no decision-tree node.
- Dimensional is a lookup that names no decision-tree node.
- LaserFuck's path-dependent leaf code makes equal subtables unequal text.

A test (`tests/generators/test_boolean_sharing_catalogue.py`) checks that 49
tree-shaped generators use a sharing helper: 32 reference a canonical helper
(`subtree_ids`, `SubtreeDiagram`), eight a declared local helper, and nine are
exempt. Having a helper does not establish complete sharing.

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
  51,200 native rows of the public PNGs pass. This
  is the canonical average-larger exemption, not a physical area lower bound.
  Partial-prefix cloning remains unshipped: its 2.19% aggregate planned gain
  misses the bespoke gate; its native positive control passes all 256 rows,
  from 33,700,800 to 32,865,600 pixels with the same 23-command maximum.
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
nested definition shares like a top-level one: the n=16 five-input fixture
falls 4% (8485 -> 8131 characters) for one dispatch test.

A bank block must defer through a distinct unused flag at a level no
shallower than its own: a shallower ancestor would rewrite the flag before
dispatch.

- Painfuck admits a bank at several depths; one cell per input level
  is the whole pool.
- brainfuck admits a bank at several depths; one cell per input level
  is the whole pool.

#### Run time and memory

The execution check in `tests/proofs/deep/execution.py` holds every
generator's command count linear. Bracket matching is precomputed at load.
Persistent stores use shared 32-cell chunks.
Those choices prevent repeated scans, but command cost and source size remain
separate axes. Loading is intentionally excluded from execution time.

- RAM0 also indexes addresses.

The payload benchmark checks 96 tables and all 6,120 rows through eight
inputs. It reports UTF-8 source bits, hidden control stacks, signed integer
widths and the simultaneous peak of data, control, cursor and machine flags.
Separate peaks need not coincide. Python overhead, static parser indexes
and I/O state are excluded. Sampled peaks are measurements, not language-wide
space bounds; construction bounds are asserted by the removed screen and
controlled by executed checks in each language's own tests.

- BFStack has a sampled peak machine payload of 756 bits at eight inputs.
- Subleq has a sampled peak machine payload of 3,066 bits at eight inputs.

- Malbolge:
  `test_boolean_malbolge.py` checks stride samples (every 8th/16th/32nd row)
  and every second-level cascade row. Both are needed: at eleven inputs,
  corrupting `_cascade_program`’s level-0 answers fails 117 stride rows and
  **0** second-level rows. Corrupting second-level answers fails 127
  second-level rows and only 18 stride rows. Only the stride sample covers
  the 1792 level-0 rows.

## Curation

<!-- COLLECTION-SIZE:START -->

The collection has 88 languages.

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
(`route = "unassessed"`, which `finish` flags until the count is recorded). Low
backlinks count against only old languages; Wikipedia pageviews are not a
gate.

Below 60, a language is admitted only as a first implementation: when the
repo adds it, no implementation exists but the maintainer's. Its page is in
the Unimplemented category, or the edit that first tagged it Implemented is
User:Bangyen's. An intrinsic axis can choose between such candidates; it
admits nothing alone and removes nothing. A stalled generator row stays open
on the [roadmap](roadmap.md); the language stays.

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

The first-implementation route also excludes a language whose generator
re-spells a collected generator: the construction transfers step for step
by token substitution and uses nothing the older language lacks, so the
language adds no generator. Same family is not enough; Rubic's tree branches
on cube parity, not a jump. Adopted 2026-10-15, retroactively: Factor
(brainfuck's flag tree as a prime product), HQ9+ with headers (Qoibl's packed
literal), Parenthesys (Alight's indexed string) and Piet++ (Piet's strip,
recoloured) were removed. Painfuck shares brainfuck's flag tree but stays: its
moves use `d` and `r` and its I/O is numeric, none of them brainfuck's. Fame
admissions are exempt: Subleq re-spells S\*bleq.

Nor does the first-implementation route admit a page the wiki categorizes as
a Brainfuck derivative: the family already holds brainfuck and ten collected
derivatives. Adopted 2026-10-15 for candidates; `curation.toml` records the
category as `bf_derivative`. The seven derivative first implementations that
predate it stay, each the wiki's only implementation of its page.

### Recognition sources

Sources checked 2026-10-01 supply selections, not admission gates
or popularity rankings.

[Kneusel, *Strange Code* (2022)](https://nostarch.com/strange-code) has these
named esolang chapters:

- FRACTRAN is a named chapter.
- Piet is a named chapter.
- brainfuck is a named chapter.
- Befunge is a named chapter.

Filska and Firefly are the author's own creations; Forth, SNOBOL, and CLIPS
belong to the separate atypical-language section.

[Morr, *Esoteric Programming Languages*](https://blinry.org/esolangs/esolangs.pdf)
selects these iconic examples with different properties, not an exhaustive canon:

- brainfuck is selected.
- INTERCAL is selected.
- Befunge is selected.
- Malbolge is selected.
- Shakespeare is selected.

[LMU teaching notes](https://cs.lmu.edu/~ray/notes/esolangs/) give a brief themed,
theoretical, golfing, multidimensional, and difficulty-oriented tour:

- LOLCODE is selected.
- Glowup Vibes is selected.
- ArnoldC is selected.
- Chef is selected.
- Shakespeare is selected.
- Rockstar is selected.
- brainfuck is selected.
- Binaryfuck is selected.
- Lenguage is selected.
- GolfScript is selected.
- Pyth is selected.
- CJam is selected.
- Jelly is selected.
- 05AB1E is selected.
- Vyxal is selected.
- Befunge is selected.
- AsciiDots is selected.
- Piet is selected.
- Whitespace is selected.
- Unreadable is selected.
- Malbolge is selected.

[Esolang featured archive](https://esolangs.org/w/index.php?title=Esolang:Featured_languages&oldid=161213)
records administrator-selected features, not popularity endorsements:

- Thue was featured.
- Funciton was featured.
- brainfuck was featured.
- Deadfish was featured.
- Emmental was featured.
- Malbolge was featured.
- Glass was featured.
- /// was featured.

### Backlink counts

The 2026-10-01 count gives Brainfuck 2,057 backlinks; 282 counted only the first
API batch. Brainfuck-relative gates and the indeterminate band are retired.

The 2026-10-01 fame audit recorded these backlink counts:

- Befunge: 381 backlinks; clears the fame gate.
- Underload: 167 backlinks; clears the fame gate.
- Thue: 155 backlinks; clears the fame gate.
- Malbolge: 129 backlinks; clears the fame gate.
- INTERCAL: 103 backlinks; clears the fame gate.
- FALSE: 91 backlinks; clears the fame gate.
- Fish: 91 backlinks; clears the fame gate.
- Unlambda: 89 backlinks; clears the fame gate.
- Smallfuck: 66 backlinks; clears the fame gate.
- FRACTRAN: 65 backlinks; clears the fame gate.
- Brainloller: 26 backlinks; rejected.
- Braincopter: 14 backlinks; rejected.
- Piet: 65 backlinks; clears the fame gate.
- Whitespace: 58 backlinks; below the fame gate.
- Forth: 57 backlinks; below the fame gate.
- Chicken: 55 backlinks; below the fame gate.
- Shakespeare: 54 backlinks; below the fame gate.
- LOLCODE: 47 backlinks; below the fame gate.

Existing fame exceptions must still clear the bar. Whitespace was removed at
58 backlinks.

<!-- CURATION-CENSUS:START -->

The 2026-10-06 census (`tests/support/fixtures/curation.toml`) records each
language's backlinks and route: 21 clear the fame gate
and 67 are first implementations.

<!-- CURATION-CENSUS:END -->

### Removed languages

Funge-98 (31, two dozen implementations) was removed on 2026-10-06. The six
languages implemented elsewhere before the 2026-09-27 rule (123, BF-PDA, BIO,
Jaune, NoComment, Sophie; 2-10 backlinks) were removed on 2026-10-14.

### Notes on individual languages

- Bitwise Cyclic Tag (181) also adds the cyclic-schedule axis.
- Deadfish (315) is interpreter-only because it has no input vocabulary.

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

  Source is exactly 5T + 2n + 1 characters; execution takes n + 3 + 2r steps.
  Emission writes 2(T-1) padding zeros and 2T table productions without search:
  O(T) build work. Tests execute 309 tables and 3,352 rows, exhaustive through
  three inputs, then constants, parity and eight seeded random tables per arity
  four through six. Probes sampled through n=14: at most 81,949 characters and
  32,783 steps. Published evolution, zero-no-append, empty-data, empty-rule and
  nontermination controls passed.

- Underload (167) clears the backlink gate.
- INTERCAL (103) clears the backlink gate.
- Emmental (43) is implemented elsewhere and fails the backlink gate;
  no intrinsic axis is established.
- Prelude (13) is implemented elsewhere and fails the backlink gate;
  no intrinsic axis is established.

The 2026-10-01 fame audit covered eight census candidates:

- [Boolfuck](https://samuelhughes.com/boof/) (76): integrated with a
  native decision tree over single-bit cells. Each input byte's low bit is
  read onto its own cell and tested in place, with one flag interleaved
  beside each bit, so every node costs O(1) commands and rendered size
  stays linear in T. Little-endian bit I/O supplies zero at EOF and pads
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
  ignored inputs; build work is O(T).

The constructions supply the bounds; dense size-difference ratios at
n=8,10,12 are measurements. Each uses a 309-table, 3,352-row corpus.

- Cyclic tag has a dense size-difference ratio of 3.997.
- Boolfuck has a dense size-difference ratio of 3.903.
- Subleq has a dense size-difference ratio of 2.926.
- /// has a dense size-difference ratio of 4.000.

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
