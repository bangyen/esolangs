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

The [optimization criteria](CONTRIBUTING.md#what-makes-a-generator-optimization-worth-shipping)
govern these experiments. Circuit Diagram's four reorder candidates saved
8.48% of area at n=7, and its smaller-area balance layout took 524 s at
n=14. FRACTRAN's literal guards saved 6.8% at n=14 and fell back to integer
scans when their factors outgrew the prime index. Forbin and EGL saved a
declining share because they trimmed fixed setup. See the archived
measurements for the other trials.

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

See the [coverage proofs](proofs/index.md).

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

The canonical sharing rule applies unless a measurement or a construction
exemption covers it. SStack's repeated-node potential is 24.6% at n=5, but
its reachable folds save 4.8%. Boolfuck's potential is 2.5% at n=5.
Piet strips have no jump to a shared subtable. Line and Circuit Diagram
compare complete layouts by emitted area. Their standalone proofs describe
the constructions and witnesses
([Line](proofs/line-sharing.md), [Circuit Diagram](proofs/circuit-diagram-sharing.md)).

thisthat, Back and Dig have construction exemptions supported by their
admission tests. Dig's shared pool uses 2–10 distinct 64-row classes, indexed
by a decimal digit. A layout that crosses another class's lane arrow or
branch falls back to an unshared layout. At n=12 the indexed leaf decoder
was 11–22 times smaller in area than the shared layouts measured there.
Home Row, ROTfuck and Dimensional use lookups without decision-tree nodes.

#### Ignored inputs and constants

`test_generator_shape_is_what_the_catalogue_says` checks folding on a
one-dependency table and removal of ignored inputs. The canonical catalogue
test checks the helpers and declared exceptions.

#### Suffix banks

Each word defers its largest repeat in its own body. A bank block needs
a distinct unused flag at its depth or deeper because a shallower
ancestor may overwrite its own flag before dispatch. Painfuck uses one
cell per input level for the pool.

#### Run time and memory

Execution counts exclude loading. The payload benchmark reports the
simultaneous peak of data, control, cursor and machine flags, with signed
integer widths and shared references charged each time. Python overhead,
static parser indexes and I/O state are excluded. Sparse store keys can
cost `T log T` bits. Sampled peaks and upper bounds have separate entries
in the [generator ledger](proofs/index.md#generator-ledger).

Route races, layout residues, address widths and noncoincident peaks
can make upper bounds loose. For example, Slow ACV Mammalian's lists
have fixed residues once the arity and essential set are known, so their
individual maxima cannot all occur together. Exact fenced ranges and
current formulas live in the ledger. The archived notes retain the
measurements, witnesses and reopening conditions for the older audits.

- SMU's scaling maximum is unresolved past n=16. The exhibited family
  has 98,929 pair slots at n=21 for 131,072 places. A rule for the per-arity
  optimum or a successor family would reopen it.
- INTERCAL uses exact per-program statement counts and worst-row written
  workspace. All-one inputs attain each named mask's two-bit peak. Its
  arity-only formulas give conservative ceilings.
- S*bleq's source bound was attained at n=26–28 in one-off builds. The
  n=28 witness emitted 105,463,455 characters at 3.30 GB peak.
- What!? built a witness to n=26. At n=22 it executed 8,519,845 steps
  and used 587 written bits. The parser used 3.15 GB at n=22 and failed
  at n=23. A leaner parse would extend the executable range.

The Malbolge suite executes boundary rows at every arity, all rows at ten,
and every 128th row at fifteen and sixteen in the weekly run.

## Curation

<!-- COLLECTION-SIZE:START -->

The collection has 125 languages.

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

The reference selections are [Kneusel](https://nostarch.com/strange-code),
[Morr](https://blinry.org/esolangs/esolangs.pdf),
[LMU](https://cs.lmu.edu/~ray/notes/esolangs/) and the
[Esolang featured archive](https://esolangs.org/w/index.php?title=Esolang:Featured_languages&oldid=161213).
Admission uses the backlink method above.

### Backlink counts

The fame audit recorded 2,057 Brainfuck backlinks and 58 for Whitespace.
Whitespace was readmitted when the gate dropped from 60 to 50. Individual
admission records are in each language's `language.toml`.

### Removed languages

| Ground | Languages |
|---|---|
| route | 123, BF-PDA, BIO, Jaune, NoComment, Sophie, Funge-98, Emmental, Prelude, LOLCODE, Brainloller, Braincopter, Turing Paint, Befunk, Factor, Polynomial, Piet++, Tiangou |
| spec | 3D Brainfuck, Transistor, Pinyin, Self-replicating marbles, Wirefunge, Bytemap, Gifunk, BitCode, PicCode, Minifuck, the Minecraft ports; deferred: 大白话, BOOMOP, Semqain |
| token substitution | Trivial brainfuck substitution |
| scaling | Vandevelo, %^2^-1, WII2D, COD, ZTOALC L |
| no generator | HuePrism (no input), Nopstacle (its blank and `#` spell no input embed) |

Minifuck's removed generator counted non-commands in skip offsets. Under
command-only offsets, all 258 corpus rows diverged. Its replacement could
ground the smaller routes, but the stored route remained blocked.
Vandevelo left under the scaling rule with an `O(T log n)` source build.
Polynomial, Piet++ and Tiangou had outside implementations predating
admission. The archive gives those implementations and dates.

Interprogck8 was removed when its generator was blocked on non-nesting
capture. It returned with a `Theta(T log T)` lane build, then shared window
rungs made the construction linear.

### Notes on individual languages

- B-tapemark: the spec leaves the marker moved after a swap ambiguous.
  The alternate reading caused 147 of 218 rows from the default generator
  to hang. Both readings now have a registered dialect with a generator.
  The alternate marker offset depends on both turn headings, so the
  experimental common layout used a cancelling lane and an intercept.
  Its wide prototype worked under both readings at about 30% larger size.
- Quassaunt rejects the separate `%%Multithread` extension.
- SendStuff implements the base language; its separate extended version
  adds `/` commands, node sets, fragments and strings.
- S*bleq runs the `ab` and `b` store targets and their indirect forms.
  The registry and generator expose only base S*bleq.
- Cyclic tag consumes one bit, appends the current production iff it is
  one, advances the production index and halts on empty data. The input
  is the initial queue and the answer is the last deleted bit. Use
  semicolons between productions and a comma before the queue. Preserve
  empty productions and supply at least one.
- Boolfuck reads little-endian bits, supplies zero at EOF, and pads
  partial output bytes. Subleq uses unbounded integers, direct jumps,
  byte I/O and negative-target halts. Input at EOF raises.
- Deadfish, HQ9+ and Nope. are interpreter-only. Deadfish and HQ9+ have
  no input instruction. Nope. accepts arbitrary source and always emits
  the same output.

### Rejected and deferred candidates

大白话 leaves its grammar, library and embedded-language dispatch open.
BOOMOP leaves the brightness metric, edge collisions and teleport
ties open. Semqain leaves scheduling, empty-queue reads and several
subcommands open. The table above records the rejected candidates.

ALEFL leaves function parameter scope unspecified. In
`'=65;$_('){,(');}_(66);,(');`, local binding prints `BA` and shared binding
prints `BB`. The published calls have no parameters.
[ALEFL revision 168585](https://esolangs.org/w/index.php?title=ALEFL&oldid=168585)

GolferDream's paired conditional grammar rejects its single-arm
calculator. Its FizzBuzz puts 100 in the box before a loop that runs
only at zero, so it prints nothing. The random range `[0,n)` is also
described as inclusive. With seed 0, `1r.` prints 0 with an exclusive
upper bound and 1 with an inclusive one in the probe.
[Wiki revision 197426](https://esolangs.org/w/index.php?title=GolferDream&oldid=197426)

Flump takes an integer in the last cell and leaves its answer there.
For `T` input rows, some input is at least `T-1`, so an answer of 0 or 1
takes at least `T-2` decrements of that cell. A loopless run with `P`
program triplets must use distinct first operands for those decrements.
Each operand must name cell `3P+2` at execution. It can gain at most
`P` bits during the run, so it starts with at least `2P+2` unary ones.
Since `P >= T-2`, the emitted source has a quadratic lower bound.
An unrolled decrement scan matches it with at most `3(T-1)+1` triplets
and `O(T)` unary address width.
[Flump revision 141132](https://esolangs.org/w/index.php?title=Flump&oldid=141132)

The detailed optimization, scaling and curation audits are archived at
`48a5fb666:docs/limitations.md`.

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
