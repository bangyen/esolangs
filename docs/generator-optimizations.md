# What each text / boolean generator optimizes

Catalog of the size-and-shape optimizations each text and boolean generator
applies to the *emitted program*. `esolangs.tools.text.__all__` and
`.boolean.__all__` are the live counts; a stated total here goes stale every
time one is added, so none is stated.

"Optimization" here means what the generator does to make its output smaller
or better-shaped — not the runtime of the generator itself.

Figures here are measurements and go stale when a generator changes; the
shape classification is enforced independently by
`tests/tools/test_boolean_contract.py::test_generator_shape_is_what_the_catalogue_says`
(source of truth: that test's `_MINTERM_SHAPED`/`_REDUCING`/`_UNSHAPED`
sets), which fails rather than drifts. Prefer stating what a future change
must respect over what a past change did — the latter is in the commits.

---

## The recurring techniques

Eleven patterns account for nearly everything. Most generators combine two
or three.

| # | Technique | What it buys | Lives in |
|---|---|---|---|
| 1 | **Delta encoding** | each character costs its distance from the previous one, not its full code point | `text/helpers.py:28` `delta_program` |
| 2 | **Multiply/factor loops** | a byte costs `O(sqrt(v))` instead of `O(v)` via `a*b + r`; the per-language cost of a run is an argument, so brainfuck/home_row minimize `a+b+r` and suffolk `a+b+2r` | `text/helpers.py:71` `factor_triple` |
| 3 | **Binary doubling** | a byte costs `O(log v)` by walking its bit expansion | addsubjump, unsquare |
| 4 | **Shortest-of-N dispatch** | build two constructions, measure, return the smaller | `wrap.py:114` `shortest` (laserfuck, streetcode, %^2^-1, unsquare, brainfuck, bfstack) |
| 5 | **Constant-subtree folding** | a subtree whose rows agree emits a leaf, not a branch | `boolean/helpers.py` (both walkers) |
| 6 | **Complement / polarity** | a dense table is evaluated from its zero rows and inverted | `boolean/helpers.py:81` `_maybe_complement` |
| 7 | **Shape-aware width** | honour a width by building a *different* shape, not by reflowing | `laserfuck_layout.py`, `wrap.py` |
| 8 | **Literal batching** | print a whole string in one statement rather than per character | `text/helpers.py` `_literal_chunks` |
| 9 | **Equal-width embedding** | *anti*-optimization: pad both bits to equal width so length can't leak inputs | `boolean/helpers.py:134` `instantiate` |
| 10 | **Dependency reduction** | a table that ignores an input is emitted as the *smaller* table, still reading (or embedding) the rest | `boolean/helpers.py` `essential_inputs` + `read_at`; `taglate`, `minifuck`, `home_row` |
| 11 | **Input reordering** | the tree splits on its inputs in whichever order emits the shortest program, so more subtrees fold — the bar is that the **emitted program changes** and still **consumes its inputs in the same order**, which rules out only a template whose emitted program is *identical* under the permutation | `boolean/helpers.py` `best_input_order` (`six_five`, `forth`, `streetcode` and `laserfuck` roll their own) |

## Which shape a boolean generator is

Most of the boolean techniques apply to one shape and are meaningless for
the other, so the shape is worth knowing before reaching for one. Folding
(5) and input reordering (11) are tree optimizations; complement/polarity
(6) is a minterm one. Dependency reduction (10) is the exception that
belongs to **neither**: it rewrites the table over its essential inputs
before the shape-specific machinery runs, so a sum benefits as readily as a
tree — `home_row` is the worked example.

The two are told apart by **what the size depends on**. A minterm sum costs
one term per selected row, so its size tracks the ones-count and is blind to
*which* inputs those rows involve. A decision tree costs one leaf per
surviving subtree, so at the same ones-count a table depending on a single
input is far cheaper than parity. Comparison method: best of the six
one-dependency tables against `01101001` (both ones-count 4).

**Tree-shaped.** cvnc, taglate, polynomial, dig, myscript, six_five,
addsubjump, sophie, modulous, laserfuck, nevermind, jaune, bitdeque,
unsquare, flowchart, streetcode, forth, basicfuck, bfpda, ram0,
forbin_boolean, arrowqueue, back, lamfunc, between, eval, factor, circlefuck,
painfuck, bf_tree, brainfuck, three_d_brainfuck, sbleq, dimensional,
dimensional_tree, clockwise, brainif, three_x, circuit_diagram, minsky_swap,
decleq, grapheme, bio, fargo, inject — folding 95% (taglate) down to 5% (bio).

**Minterm-shaped (4, `_MINTERM_SHAPED`).** a_painter_ant, bfstack, container,
algebraic_programming_language — all within 4% of parity on a
one-dependency table, because there is no subtree to collapse.

**Reducing (10, `_REDUCING`).** `home_row`, `cod`, `nocomment`, `bit_tilde`,
`rotfuck`, `suptiftam`, `suffolk`, `qoibl`, `collatz_multiverse` and
`point_break` are minterm sums that gain **60.6%**, **92.5%**, **27.3%**,
**81.5%**, **76.3%**, **69.4%**, **14.7%**, **53.2%**, **66.1%** and
**50.7%** respectively on a one-dependency table by *dependency reduction*
(10) rather than by folding — the reason they are not filed as
minterm-shaped despite being sums.

The three remaining minterm sums are measured, not skipped: `container` and
`bfstack` are setup-dominated — a constant table is 93% and ~100% of a
one-dependency program's length respectively, so nearly all of their arity
cost is per-input setup that reduction cannot reach (see the setup/body note
below) — and `a_painter_ant`'s setters *are* its routing geometry, so
reducing it would be a restructure rather than a projection.

A sum of minterms is the *ideal* shape for technique 10: it pays per selected
row **and** per input within each row, so dropping an input removes rows and
shortens every surviving row. Folding-based generators gain less because they
already collapse what a degenerate table repeats — the distinction the shape
test would otherwise lose, so they are carried in their own `_REDUCING`
category rather than relabelled tree-shaped: the gain tracks dropped
*arity*, and reordering does not become applicable the way it would if they
had grown a tree.

**Neither.** Eight generators are exempted from the shape test altogether
(`_UNSHAPED` in `test_boolean_contract.py`, which is the list of record):
`wii2d`, `ztoalc_l_boolean`, `minifuck`, `one_two_three`,
`pct_squared_minus_one`, `slow_acv_mammalian_boolean`, `jaune_multiply` and
`circlefuck_byte`.  Some are a different shape and some simply raise on the
`n == 3` tables the test uses — `one_two_three` caps at two inputs, and
`minifuck` and `pct_squared_minus_one` are parameterized routes whose length
tracks their embed rather than any table shape.  Two are worth naming for
their mechanism: `wii2d` measures *negative* (a one-dependency table costs
slightly more than parity), its construction being a route search over a
grid; and `ztoalc_l` measures a flat **0%** — every table in the comparison
has ones-count 4 and they all render to exactly the same length — because it
is a *table lookup*, not a tree or a sum: the row index is built
arithmetically by double-and-add and the table is one-hot encoded into an
array, so there are no subtrees to collapse and no per-row terms to count.
Its size tracks the trajectory peak its command count selects from the
anchor table.

**A third shape: algebraic (2).** `fargo` and `super_snusp` are neither a
tree nor a minterm sum but an *algebraic normal form* — the XOR of the
AND-products the Möbius transform selects. Fargo's size tracks the function's
algebraic degree, which makes it the only generator whose worst case is
**linear** rather than exponential: parity, the table that folds nothing
anywhere else, is its *cheapest* dense case at one term per input (10
characters at `n == 1` growing to 62 at `n == 8`, against brainfuck's 225
to 1649 by `n == 4` alone). It measures 56.5% folding on the
one-dependency comparison, so the catalogue test files it tree-side, but
the mechanism is different: a one-dependency table is one ANF term
whatever its arity, and nothing about it is a subtree collapse.

What makes it possible is the *interface*, not the language's power:
Fargo's `@ i` indexes the input number's `i`th bit directly, so the
generator pays nothing to read, normalize, or store bits before testing
them. Input reordering is therefore vacuous here — there is no read order
to permute. Worth checking for on any future candidate whose input is
bit-addressable rather than streamed.

Super SNUSP has a streamed interface, so it retains only the essential
inputs while consuming every input line, then builds its ANF over that
projection. This is dependency reduction (10), not a subtree fold or an
input reorder: the resulting program is shorter because it has fewer input
products to form.

One entry sits near the boundary and is worth reading as a measurement
rather than a label: `minsky_swap` comes out at 10% only because a
one-dependency table is *smaller* than parity there by a few characters of
embedding, not because anything folds.

`circuit_diagram` measures **99.3%** and is tree-side: dependency reduction
(10) builds its chains over the essential inputs only, so a one-dependency
table drops from 2756 characters to **40**. It needs no `_REDUCING`
exemption, since it clears the folding bar on its own. (A minterm sum whose
*constants* are special-cased can file tree-side for the wrong reason on the
split-order metric alone — worth checking that the win is a real fold before
trusting the number.)

Technique 9 is the one deliberate refusal to shorten. A zero embedded as
nothing makes `len(program)` a function of the inputs, leaking the very bits
the program is supposed to compute — an earlier Bio embedding ran to 236/240/
244/248 characters for its four instantiations.

---

## Text generators

### Delta-encoded (the dominant family)

Each character costs only its distance from the previous one.

| Generator | Detail |
|---|---|
| `nocomment` | `i`/`d` runs via shared `delta_program` |
| `circlefuck` | tape *is* the program; a no-op char near the first target seeds the cell |
| `basicfuck` | one variable `a`, `+=`/`-=` |
| `six_five` | `_six_five_path` arithmetic tokens |
| `rotfuck` | delta the **shorter way around** the 8-bit wrap |
| `bio` | delta folded mod 256, *plus* `a*b+r` search on the delta itself |
| `polynomial` | `+=`/`-=` deltas, then encoded as polynomial roots |
| `container` | signed delta split across two `A>=i` rules |
| `painfuck` | signed delta in bases 7 and 3 |
| `one_two_three` | running **XOR** in `edi`; emits only the differing bits |
| `bit_tilde` | tracks the tape, toggles only bits that must change |
| `brainfuck` | **hybrid**: delta when close, else `[-]` + multiply-loop rebuild |
| `bfstack` | same hybrid; both pick with `shortest`, but `bfstack` breaks a tie toward the rebuild where `brainfuck` keeps the walk |
| `unsquare` | delta chain off the retained accumulator (~21% on "Hello, World!"), **bounded by parity** — `x` can't restore oddness, so odd targets off an even accumulator reseed |
| `cvnc` | `ci`/`cə` runs via shared `delta_program`, at **2 characters per unit**: every command needs a partner of the other class to form a CV syllable, and `c` (function reset) is the only consonant that touches neither accumulator nor deque while an invalid `u` is the only such vowel, so the pairing is forced rather than chosen — no other pairing undercuts the factor of two |
| `super_snusp` | shortest of direct letter/decimal loads and signed `(`/`)` deltas from the retained output cell |

### Arithmetic-construction

| Generator | Optimization |
|---|---|
| `home_row` | `a*b+r` counter loop, `a` searched near `sqrt` → `O(sqrt)` |
| `suffolk` | factors minimizing `a + b + 2r`, not `sqrt`, because `r` is spelled `>!` at two characters a unit; the emitted line measures `12 + a + b + 2r` |
| `addsubjump` | binary doubling → `O(log byte)` |
| `collatz_multiverse` | two-line multiply-add per constant; **only the bytes actually referenced** are built (`_PLAN` / `_extend_plans`), reaching large values in `O(log)` constants |
| `wii2d` | per character picks cheapest of literal digit / square / double / combination |
| `slow_acv_mammalian` | SEED runs split around the SPRINT walk, solving `(q+1)*K == target (mod 256)` |
| `minifuck` | tracks the bit pool; prints only when nonzero |

### Shortest-of-N

| Generator | Competing forms |
|---|---|
| `laserfuck` | `_laserfuck_multiply` (spread values) vs `_laserfuck_base_ring` (clustered) — compared by **bounding-box area**, not `len` |
| `pct_squared_minus_one` | `_pct_path` (high-delta) vs `magnitude` (low-delta, repetitive) |
| `streetcode` | ring vs plain, and both again folded; shorter wins |
| `clockwise` | weave vs bare ring — ring only ever won on 1-char text by ≤1.26x, so it was **removed**; the loss is recorded |

### Literal batching

`between`, `taglate`, `myscript`, `three_x`, `eval`, `modulous`, `nevermind`,
`sbleq`, `forbin`, `suptiftam`, `dimensional`, `qoibl`, `sophie`, `forth`,
`decleq` — print via string literal or embedded data rather than per-character
arithmetic. `forth` still builds each char as `m * 15**n + p`.

### Special cases

- **`streetcode`** — the *first* character (whole code point: 72 for `H`, 937
  for omega) uses a counting ring, making it a product; later characters keep
  the unary walk, since adjacent gaps are almost always cheaper than a ring's
  fixed row block.
- **`brainif`** — starts a falling character from the **largest parked value
  not above it** rather than from zero. The `l` of "Hello, World!" costs 66
  lines from the comma's parked 44 vs 110 from zero.
- **`ztoalc_l`** (text *and* boolean) — precomputed anchor table
  (`ztoalc_starts.py`) of Collatz starts with the smallest trajectory peak per
  length interval. The boolean generator places its commands the same way the
  text one places characters, which is what let it drop its placement search
  entirely.
- **`factor`** / **`three_d_brainfuck`** — reuse `brainfuck`'s output unchanged.

### Width handling (9 of them lay out their own shape)

`clockwise`, `dig`, `eval`, `laserfuck`, `modulous`, `myscript`, `streetcode`,
`three_x`, `wii2d`. The rest are reflowed afterward by token-aware wrappers in
`wrap.py` (never a blind character slice — that would split `-6` or BIO's `0ox`
triples). A width too small is answered with the narrowest available shape
rather than an exception; `dig` even stands the program on end and runs it down
two columns.

---
## Boolean generators

### Constant-subtree folding (5) — the single biggest lever

A subtree whose rows all agree emits a leaf instead of a branch. **Every tree
generator in the catalogue now folds**; the classification is measured, not
inherited, by `test_generator_shape_is_what_the_catalogue_says`.

The seven that never fold — `point_break`, `collatz_multiverse`, `suptiftam`,
`bit_tilde`, `a_painter_ant`, `qoibl`, `suffolk` — all cost one term per
one-row, so there are no subtrees to fold. A constant table is small there
because the sum is *empty*. **Nothing is left to convert.**

Six of the seven are literally sums of minterms. `a_painter_ant` is the
exception and is worth naming, because reading "sum-of-minterms" as a
statement about its *structure* is wrong: it paints a decision tree, one leaf
per input combination. It belongs here anyway because a one-leaf costs a
paint-and-return walk and a zero-leaf costs a single space, so its size
tracks the ones-count and nothing folds — every ones-count-4 table at n=3
costs exactly 268 characters, whether it depends on one input or is parity.

Two constraints a future change must respect:

- **Measure against every one-dependency table, not just `11110000`.**
  Generators that branch last-input-first (modulous, forth, unsquare;
  circlefuck before it chose its own order) fold `10101010` instead, and an
  MSB-aligned table alone reports them as non-folding when they save 56–77%.
- **A folded leaf must still do the work the skipped levels did** — emit its
  own clear, advance what the walk would have advanced, drain what would have
  drained. Skipping levels without carrying that is the recurring fold bug.

Two generators look like they have headroom, and it is a missing
*complement* (6) rather than a missing fold: `a_painter_ant` (all-0 92,
all-1 444) and `rotfuck` (370, 408) are cheap on all-zeros and expensive
on all-ones, and neither calls `_maybe_complement`. Taking the cheaper
polarity of every n=3 table would be 17.96% for `a_painter_ant` and 2.81%
for `rotfuck`.

**`a_painter_ant`'s share of that is not reachable, and the reason is the
output convention rather than the construction.** Its answer is *the colour
of the cell the ant lands on* — white is one, black is zero — read directly
by `landing_colour`. A complement build paints the zero leaves and would
then have to report the **opposite** of the landing colour, and there is no
output instruction, no NOT, and nowhere to put the inversion: the polarity
is baked into how the answer is read. The 17.96% is `min(cost(table),
cost(~table))`, real as an arithmetic bound and unbuildable as a program.
It is the same shape as `123`, whose affine ceiling turned out to belong to
its printing route rather than to the language: **when a measured ceiling
will not build, suspect the output convention before the construction.**

Mind also the trap that `_maybe_complement`'s docstring records: an all-ones
table complements to the same empty sum an all-zeros table has, which is
wrong for `circuit_diagram`, which special-cases constants to a single
self-fed gate.

Structure and cost model can disagree here — `_head` literally paints a
tree, one leaf per input combination — and the catalogue tracks the cost
model, per the 268-characters-either-way measurement above.

An unshipped alternative for deep folds — a single reusable drain cell rather
than one gadget per skipped bit — is verified correct but not shipped: the two
constructions cross at five skipped levels, which needs n≥5, past where the
suite exercises folding. See git history for the geometry and the crossover
table.

### Complement / polarity

`_maybe_complement` flips a table with more ones than zeros, evaluating the
zero rows and inverting — one term saved per row, paid for once.

| Generator | Cost of the flip |
|---|---|
| `circuit_diagram` | **free-ish and huge**: a dense 3-input table drops ~7000 → ~130 characters |
| `collatz_multiverse` | **free** — the OR already ends on the flip it would have added |
| `point_break` | **free** — `g` is `1 - f` for its own loop-guard reasons |
| `suptiftam` | one line, against four lines per input per minterm |
| `suffolk` | one minterm block per row saved — 5.1% averaged over every n=3 table, 45% on the densest n=4 ones. Builds **both** polarities and returns the shorter, since a complement literal sits at a nearer cell than a raw one, so row counts alone do not decide it |
| `qoibl`, `bit_tilde`, `grapheme` | fewer minterms; grapheme picks whichever row-set is shorter |
| `container` | `OUT` spends one `+1 S{row}>=Gout` line per one-row, so a dense table sums its zero rows from a 49 start and subtracts — 12.7% on the densest n=4 table. The per-row survivor blocks are fixed and unaffected |

### Dependency reduction (10) — sixteen generators, both shapes

A table ignoring an input is emitted as the *smaller* table, still
consuming the rest. `essential_inputs` (in `boolean/helpers.py`) names the
inputs whose flip changes some row, and `read_at` projects the table onto
them.

What differs per generator is **how the ignored inputs are still honoured**,
and that is set by the interface rather than by the construction:

- **`taglate` reads and discards.** The read count is the interface
  (`test_every_table_reads_the_same_number_of_inputs`), so the emitted
  program keeps every read: `h` appends the character to the queue's tail,
  `e` repeated once per queued cell rotates it back to the front, and `f`
  drops it — leaving the queue exactly as it was so the reduces' positional
  arithmetic is undisturbed. Constant tables go from 451 characters to 21.
  Note `taglate`'s own `_reorder_tt` is a different thing despite the name.
- **`minifuck` embeds and erases.** A parameterized generator, so the
  ignored inputs are `{Xi}` slots rather than reads; `_project` handles what
  it can and `_reconverged` emits the ignored setters first, then drives
  every row to one identical state.
- **`cod` embeds into a sealed box, and pays nothing at all.** COD is a
  *grid*, so unlike a one-dimensional tape it has cells that are genuinely
  unreachable: `_cod_dead_box` walls an ignored setter in `~` on every
  side, and its `)` increments nothing because no cod is ever there. The
  leaf cascade is `2**n - 1` blocks whatever the table says, so dropping
  inputs takes a one-dependency table from 1504 characters to **113**
  (92.5%) and a constant to 113 as well.

  Two traps, both worth carrying to the next grid language. **A space is
  not inert filler** — it is open water, so `_cod_combine`'s space padding
  cannot be used to line the box up beside the program; padding the reduced
  program to a common width lets the cod swim out and it prints nothing at
  all. The boxes are therefore stacked above and below. And a **gapped**
  dependency set (inputs 0 and 2 but not 1) would emit the core's slots
  around the ignored one, leaving `{X2}` before `{X1}`; widening the set to
  its span restores name order, where taglate declines a gapped set
  outright because there the widened table would ghost-pad itself.
- **`home_row` embeds and weighs zero.** The cheapest of the three, because
  the ignored input needs neither a discard nor an erase: its packing line
  `{Xi}lsffff a^weight fl` simply carries **weight zero**, so the gate still
  runs and consumes its guard while adding nothing to the accumulator. The
  setter keeps its two-character width and its position, so equal-width
  embedding (9) and name order both hold with nothing to reconcile. The
  saving is the leaf chain: `2**n` lines become `2**k`, taking every
  one-dependency table at `n == 3` from 213 characters to **84** (60.6%) and
  a constant to 82, with non-degenerate tables byte-identical.

- **`grapheme` reads and abandons.** Its reads are the interface, so an
  ignored input keeps one, but it costs a *single character*: `W` pushes
  the line it read and nothing ever pops it. That is safe by construction
  rather than by measurement — every operator pops what it consumes and
  `Y` prints the top of the stack, so a value left below the accumulator
  is unreachable, not merely unused. Cheaper than taglate's rotate-and-drop,
  which has a queue's positional arithmetic to keep undisturbed. A
  one-dependency table at `n == 3` goes from 180 characters to **49**
  (72.8%), helped by the minterms shortening too: each spends one factor
  per input, so dropping inputs shrinks every surviving minterm as well as
  removing minterms.

  Note `grapheme` stays **tree-shaped** in the catalogue and out of
  `_REDUCING`: it gains 75.0% against parity, well past the folding test's
  bar, so filing it as a reducer would suppress a check it passes on its
  own. `_REDUCING` is only for generators whose gain would otherwise look
  like a contradiction.

- **`nocomment` embeds and weighs zero, like `home_row`.** Its index is
  built by a guarded run of `i`s per input — `["i"] * (2**w)`, a run length
  the *generator* picks — so an ignored input contributes an empty run while
  its guard still executes and still leaves the pointer on its complement
  cell. The saving is the staircase and the preloaded output cells, both one
  per row: a one-dependency table at `n == 3` goes from 373 characters to
  **271** (27.3%).

  The figure to note is that it *grows with arity*, which is the opposite of
  the usual direction: at `n == 4` it is 653 → **387** (40.7%), because the
  staircase scales as `2**n` while the NOT-gate prologue and setup do not.
  A generator whose fixed overhead dominates at small `n` can still be a
  strong reducer where it matters.

- **`circuit_diagram` drives nothing from the ignored rail, and it is the
  largest win in the catalogue.** Its cost is entirely the body: one `a`
  chain per selected row, each a gate per literal plus the runs feeding it.
  Every input keeps its own `-` row — the rows *are* the read order — but
  the chains are built over the essential inputs' rails only, and an ignored
  rail simply drives nothing. A one-dependency table at `n == 3` drops from
  2756 characters to **40** (98.5%).

  The precedent was already in the generator: a constant table is one
  self-fed gate over `rails[0]` while every other rail drives nothing, and
  still consumes all `n` reads. Dependency reduction is that same move
  generalized from "reads no literal" to "reads the ones that matter" —
  worth remembering that a generator's own constant special-case is often a
  reducer already written for one table.

- **`bit_tilde` reads into a cell it then never copies out of.** Its cost is
  per one-row *and* per input within it — each minterm pre-copies one cell
  per input and nests one `{` test per input — so dropping an input removes
  rows and shortens the rows that survive. The reads stay (one `)` each,
  and they are the interface); an ignored input is simply read into its own
  cell and never copied out. 778 → **144** at `n == 3` (81.5%), and 2425 →
  **237** at `n == 4` (90.2%).

  **One trap, and it is the kind only execution finds.** `(` prints cell 7's
  window and input 0's bit lands there, so it must be consumed whether or
  not the table depends on it. The stock generator did that as a side effect
  of its first copy; when input 0 is *ignored* nothing else touches cell 7
  and the program prints the input bit rather than the answer. That is
  exactly the 16 tables at `n <= 3` which ignore input 0, and it cost a
  60-row gate failure before an explicit `{ ~ }` clear was added. **A cell
  that a construction incidentally cleans is load-bearing.**

- **`rotfuck` reads and normalizes an input it then never guards with.**
  Its cell layout and block list are both dominated by `2**n` — one mismatch
  cell and one minterm cell per row, one guarded `[ body ]` block per (row,
  input) pair — so evaluating over the essential inputs drops the exponent.
  Every input keeps its `,` read, its cell and its complement; an ignored one
  is normalized like the rest and then simply never guards a block. 1576 →
  **373** at `n == 3` (76.3%), and 5123 → **482** at `n == 4` (90.6%).
  Constants improve too, 1404 → 370.

- **`suptiftam` reads an input it then never names as a factor.** A minterm
  is four lines per input on top of one row per selected row, so dropping an
  input removes rows and shortens the survivors. Every input keeps its read
  and its `%-[read]22%` normalization; an ignored one is simply never used
  as a factor. 700 → **214** at `n == 3` (69.4%) and 1555 → **247** at
  `n == 4` (84.1%).

- **`suffolk` reduces the least, and the reason is the more useful finding.**
  It reads an input it never uses as a literal — the same move its constant
  branch already made for *every* input — but its win is only 875 → **746**
  at `n == 3` (14.7%), against a 69% screen. Measured, **96.5% of the
  reduced program is the per-input read-and-complement setup**: `const`
  re-walks its gap once per unit, so preloading 48 at each of `n` cells
  costs 591 characters at `n == 3` while the whole minterm body it replaces
  is about 3.5%. The setup is the interface and cannot be dropped.

  It is still worth having — nothing grows, and at `n == 4` the body has
  grown enough to make it 1479 → **1066** (28%) — but it is the clearest
  case in the catalogue of a **screen measuring headroom that the reads
  make unreachable**. Where a generator's per-input setup dominates, price
  the setup before believing an arity screen.

- **`qoibl` reads an input it then never names as a factor.** A minterm is
  one `qe` factor per input on top of two lines per selected row. 633 →
  **296** at `n == 3` (53.2%) and 1276 → **369** at `n == 4` (71.1%).

  It is the counterpart to `suffolk` and the pair is the useful comparison:
  both are minterm sums that read their inputs, but qoibl's per-input setup
  is **29%** of a one-dependency program against suffolk's **96%**, and the
  delivered figures track that (53.2% against 14.7%) rather than tracking
  the screen, which promised both about 70%. **Split the program into
  per-input setup and per-row body before believing an arity screen** — the
  screen prices the whole program, and only the body is reachable.

- **`collatz_multiverse` reads an input it never turns into an indicator.**
  A minterm costs an indicator per input plus an AND chain, on top of one
  minterm per selected row. 2419 → **821** at `n == 3` (66.1%). Its constant
  branch was already the reduction for zero essential inputs — reads every
  input, discards it, prints the constant — so this generalizes it, the same
  move as `circuit_diagram` and `suffolk`.

- **`point_break` answers by halting, and the reduction is unaffected.** Its
  result is the termination convention — halt for 0, loop forever for 1 —
  so the gate compares the halt observable (`point_break_result`, which
  proves the loop by a state revisit) rather than printed text. The
  construction reduces like any other minterm sum: each selected row costs a
  `LET` per factor, so dropping an input removes rows and shortens the rest.
  292 → **144** at `n == 3` (50.7%). Its own docstring already stated the
  rule this relies on — *the reads are the interface, and only the body may
  shrink*.

- **`three_x` is the first *tree* generator reduced deliberately, and it
  retires the idea that trees have nothing to gain.** Its tree prunes only
  the rows that *differ from the default*, which for a one-dependency table
  is still half of them, each carrying a full-depth guard chain; folding
  never sees the degeneracy. Reducing collapses those to one guard: 603 →
  **185** at `n == 3` (69.3%).

  **The bug it produced is worth keeping.** `_three_x_ordered` receives an
  *already-permuted* table from `best_input_order`, so the essential set it
  computes is in the tree's coordinates, not the input stream's. Mapping
  slots back through the stream order mixes the two — which agrees only when
  the essential set is contiguous from 0, so it was invisible on every
  one-dependency table and produced **522 wrong rows** on gapped sets like
  `[0, 2]`. When a generator reduces *inside* a reorder wrapper, check which
  coordinate system the reduced indices live in.

- **`polynomial` can only drop its *leading* ignored inputs, and the reason
  is worth reading before reducing any read-assigns-to-a-register
  generator.** A read assigns to the single register, so the tree must
  consume the stream in order:

  - a **trailing** ignored input is already free — the tree collapses its
    subtree and drains the read at the leaf, machinery it already had;
  - a **middle** one cannot be dropped at all, since the drain consumes the
    stream in order and removing it makes the tree branch on the wrong bit
    (measured: 92 wrong rows over the 26 tables at `n <= 3` whose ignored
    set is not a leading run);
  - only the **leading** run is genuinely wasted, because the tree burns a
    full branching level before reaching the input that matters.

  So the reduced build keeps every input from the first essential one
  onward and drains the run before it. `11001100` falls 6855 → **1678** and
  `10101010` 4106 → **1175**; `11110000` is correctly unchanged, its
  essential input already being first. Only the *tree* takes the prefix —
  the DAG indexes its states by how many bits have been read, so prepended
  instructions shift every state and it answers correctly only while the
  drained bit is 0, emitting nothing once it is 1.

**Both shapes reduce.** The minterm side is where this started, but the
discriminator was never the shape — it is the split below. A tree folds a
degenerate table away only when its fold *direction* matches the essential
inputs and its cost is leaf-count-bound; `three_x` fails the second (its
cost is per differing row) and keeps the full gap. `grapheme` (72.8%) and
`circuit_diagram` (99.3%) were already tree-side counterexamples.

**Before building the next one, split it.** The arity screen prices the
whole program, but only the per-row **body** is reducible; per-input
**setup** is the interface and stays. A cheap proxy for the split is the
length of a *constant* table against a one-dependency one, since a constant
needs no body:

| generator | setup share | delivered |
|---|---|---|
| `point_break` | 12% | 50.7% |
| `collatz_multiverse` | 21% | 66.1% |
| `qoibl` | 29% | 53.2% |
| `container` | 93% | not worth building |
| `suffolk` | 96% | 14.7% |
| `bfstack`, `clockwise` | ~100% | not worth building |

The screen called `suffolk` and `qoibl` both about 70%; the split called
them apart in one measurement each. **Three candidates were retired on this
evidence without being built.**

**What to check on the next candidate.** The win is available wherever cost
tracks *arity* rather than the table's contents, which is why it crosses the
tree/sum divide. The question is only what the ignored input's placeholder or read
must still do — and the five shipped answers (rotate-and-drop it, erase it,
weigh it zero, abandon it on a stack, wall it off) are roughly in increasing
order of cheapness. Two things make it
free rather than merely cheap: a construction where the ignored input's
contribution is already multiplied by something the generator picks, so the
factor can be set to zero; or **a dimension the interpreter cannot reach
into**, which is why the 2D languages are the better hunting ground — a 1D
tape has no dead cells, which is exactly why minifuck needed reconvergence
where cod needs only a wall.

It also **sidesteps the storage wall that closed reordering** for
`polynomial` (25.1%), `modulous` and `sophie`: those need somewhere to hold
a read bit, and a discarded or zero-weighted input needs no storage.

### Input reordering (11) — the decision-tree generators

The tree splits on inputs in whichever order emits the shortest program, so
more subtrees fold. **The bar: the emitted program must change and still
consume its inputs in the same order.** The test is on the *drawing*, not on
which `{Xi}` name sits where. A parameterized template whose emitted program
is byte-identical under the permutation books a saving against the harness's
fill order and is a redefined benchmark; one whose drawing genuinely changes
is a reorder however its slots are labelled, since `instantiate` substitutes
by name and each input still reaches its own slot. Both shipped forms clear
it: `eval` interleaves stack ops *between* the slots, and `back` permutes
which name fills each slot while building its tree on the permuted table.

**Who ships one is a grep, not a list here.**  The authority is
`grep -rn 'best_input_order' src/`, **then the callers of
`decision_tree_program`, then — repeatedly — whoever delegates to or reuses
the output of anything already found.**  That last step has to run to a
fixed point rather than once: `painfuck` is three hops out
(`decision_tree_program` → `bf_tree` → `brainfuck` → `painfuck`), so a
single pass finds five of the seven inheritors and stops.  A reorder can
arrive through a *transliteration*, with nothing in the generator naming
it — `factor`, `three_d_brainfuck` and `painfuck` reuse brainfuck's output
outright and inherit the saving unchanged.

**Do not narrow that pattern to `best_input_order(truth_table`.**  It was
written that way and silently missed every inheritor, for one reason: the
shared call in `helpers.py` breaks its arguments across lines, so the table
is not on the same line as the callee.  A grep that names the authority is
only as good as the spellings it matches, and a one-line pattern cannot see
a wrapped call or an inherited one.

`bitdeque`'s is the one worth reading, because it is *not*
the free reorder the roadmap still lists as open — its rotations happen
inside the tree (`EJECT PUSH`, `POP INJECT`, two commands per position),
while the load block stays byte-identical because the `{Xi}` setter's parity
is derived from the input's name.

**Not applicable — sum-of-minterms**, where the minterm count does not depend
on split order: `a_painter_ant`, `circlefuck_byte`, `circuit_diagram`, `cod`,
`container`, `grapheme`, `home_row`, `jaune_multiply`, `point_break`,
`suffolk`, `suptiftam`.

**Measured upside but unreachable as a reorder** — no addressable storage to
hold a read bit, so a bit can only be branched on before the next read:
`polynomial` (25.1%), `modulous` (16.4%), `sophie` (16.4%).

**Dependency reduction (10) reaches part of this**, because it is
*order-blind*: it rewrites the table over its essential inputs before any
split order is chosen, so it needs nowhere to hold a read bit. That is the
escape the reorder could not take. Residual merging
collects what the screen was measuring for polynomial and sophie.

**`cvnc`'s walk cost turned out to be zero.** It delivers **13.8% at `n =
3`** (every table) and **17.9% at `n = 4`** (300 sampled), with **no table
growing** — the delivered figure rises with `n` rather than falling, because
the walk it screened for is free (below).

What makes it free is that a deque has *two* ends. The obvious way to
reconcile a permuted test order with a fixed read order is to rotate the
bits into place, and rotations are what the screen was told to charge for.
There is no need: each read is pushed to whichever **end** it will later be
popped from (`m` or `n`, riding the read's own syllable for one character),
and each node pops the end holding the bit it wants. `_deque_schedule`
searches the `2**n` push assignments; what that reaches is exactly the
**unimodal** permutations — all of them through `n = 3`, 20 of 24 at
`n = 4`, 252 of 720 at `n = 6` — and unservable orders return the empty
string, which `best_input_order` already reads as "not buildable" and
skips.

The hoist is not free, which is why it does not replace the node-read tree:
a stored read costs one character more than a bare one and a fetch costs
three where a node read costs two. What repays it is that a folded subtree
then owes **nothing** — the node-read build still owes its remaining `so`
runs and the `cə` that normalizes the bit they leave behind. So the two are
built and the shorter returned, the `six_five` precedent. Parity keeps the
node-read build; one-dependency tables take the hoist.

**The generalizable part: count the ends before pricing a walk.** A reorder
over storage with two addressable ends may need no walk at all, because the
*push* side has a free choice that can pre-arrange the pop order. That is a
different escape from `back`'s (whose harness substitutes its bits) and it
applies to any deque-shaped store — `bitdeque`'s `INJECT`/`EJECT` pair is
the other one in this repo.

Four rules worth carrying into the remaining candidates:

- **Read the interpreter's op set, not what the generator emits.** `bitdeque`
  was excluded on the latter and turned out to be one of the largest wins.
- **The screen is neither a floor nor a ceiling.** It prices only the reorder,
  so a generator whose reads sit at its nodes gains a hoist too and beats it
  (addsubjump screened 16.7%, delivered 31.7%; sbleq 8.3% → 24.7%); a node
  testing a *position* rather than naming an input owes a walk and comes in
  under it (circlefuck 10.47% → 10.42%, streetcode 16.8% → 16.76%, laserfuck
  16.3% → 16.08%). **How far under is the walk's cost as a fraction of the
  program**, so a compact program pays a larger fraction for the same
  absolute walk — an early Back build lost 2.85 points that way, on moves
  costing only 2.00 characters each, because its programs average 82
  characters against Streetcode's 842. **But first check whether a walk is
  needed at all.** It is *exact* when the reads already sit in named storage
  and the reorder is a rename — `three_x` permutes the **store target** each
  `?` writes to, leaving the tree untouched, and delivered its screened
  4.5%/5.4% to the character. `back` *could* be exact the same way —
  permuting which name fills each load slot delivered 11.99% against its
  12.0% screen — but that build is declined for emitting its placeholders
  out of name order, and the walk it pays instead costs about 2.85 points.
  A generator with no sequenced reads has no *need* to move a pointer at
  all; whether it should is then a question about the shape of the
  template rather than about the language.
- **Reachable orders are often far fewer than `n!`** — stack- and pointer-bound
  generators reach a structured subset (Forþ and Unsquare a product; BrainIf
  only `n+1` j-splits, since a written cell cannot be crossed without
  destroying it). Enumerate the reachable set; don't search `n!`.
- **A size comparison is meaningless until both builds compute the function.**
  Measure only correct programs.

**When a candidate is worth building.** The screen figure alone does not
decide it; what it costs to reach does. Two questions settle almost every
case, and both are answerable before writing any code:

1. **Are the reads already hoisted into addressable, named storage?** If so
   the reorder is a rename — a `best_input_order` wrapper and a permuted
   operand — and the screen is reliable. Worth doing down to about 5%,
   because the change is a few lines (`three_x` at 4.5% is ~38 lines;
   brainfuck and dimensional inherit theirs from
   `decision_tree_program` for about four).
2. **If the reads sit at the nodes, what does the hoist buy?** Read the
   interpreter and estimate it before building. A hoist that deletes a
   per-leaf drain is usually large (`sbleq` screened 8.3%, delivered 24.7%;
   `addsubjump` 16.7% → 31.7%). A hoist that merely relocates a cost is not,
   and a restructuring generator costs one to two hundred lines carrying a
   language invariant — so proceed only when the estimate plausibly clears
   **10%**.

`brainif` is the worked counter-example, and it was reverted rather than
kept. It screened 4.9% and delivered 5.2% at n=3 / 8.0% at n=4 — the win was
real. But its reads sit at its nodes, so reaching it took ~146 lines resting
on a language invariant subtle enough
to be worth stating: BrainIf gates every line on an exact cell value, and the
two lines of a guarded move test *different* cells, so a guarded pair over
written cells fires **twice** whenever the neighbouring digits differ. The
sound spellings are a destination that is still zero, a cell whose digit is
known (one line), or normalizing a dead cell first (`if 48 increment` then
`if 49 move left`, never on cell 0, which holds the answer byte). The
existing node-read construction is built entirely inside that law — its leaf
drain *is* the walk home — which is why the hoist relocated cost instead of
deleting it, and why 5.2% was the whole of the return. Rule 2 would have
closed it before the first line was written; the commit history has the
build if the trade is ever worth revisiting.

**The grid tier: three placements shipped, two closed on cost.**
`streetcode`, `laserfuck` and `back` hoist their reads into a tape and test
a *position*, which makes reordering a placement — change which cell each
input lands in and every node tests something different, with the tree, the
fold and the leaves untouched.  `dig` and `flowchart` read at the node and
would need a restructuring hoist, which neither earns.  `back` is where a
cheaper build was measured and then declined: filling in *cell* order
instead of name order is free, but templates must emit their slots in name
order, and that invariant is not tradeable for a gain of that size.

**The queue is now closed in both tiers.** The grid tier's three placements
(`streetcode`, `laserfuck`, `back`) are shipped, and its two read-at-node
candidates (`dig`, `flowchart`) were costed and closed above. Nothing with a
measured screen is left unbuilt and unexplained.

The tier's lesson is that "2D" was never the dividing line. What decides the
cost is **where the node reads** — the same question the sequential tier
answers — and the grid generators split on it exactly as the token-sequence
ones do. Three of them hoist their reads into a tape and test a *position*,
which makes reordering a placement: change which cell each input lands in and
every node tests something different, with the tree, the fold and the leaves
untouched. Two read at the node and would need a restructuring hoist, which
neither earns.

`factor` and `three_d_brainfuck` reuse brainfuck's output and inherit the
saving unchanged; a shorter program also shrinks factor's set of tables
whose integer encoding exceeds Python's digit limit.

**A trap when wiring the rest.** A generator that validates its own output
during construction needs that check frame-mapped too. ZTOALC L used to ask a
simulator whether the program computed `truth_table[c]`, but a reordered tree
walks to the row whose bits are gathered in `perm` order, so the unmapped
check demands a different function and rejects every correct placement. The
symptom is a clean 0.00% across every table — indistinguishable from
"reordering does not help here". (ZTOALC L no longer searches or reorders at
all: it constructs a branch-free array lookup placed on a Collatz trajectory,
so there is nothing left to validate. The trap still applies to any generator
that gates its own candidates.)

### Layout and geometry

| Generator | Optimization |
|---|---|
| `laserfuck` | ring reader does 48 subtractions as a **loop** — 2 rows regardless of n, vs 49 columns per input. Tree rows scale with *one* edges only; the all-zeros path is a straight line. Cell 0 doubles as counter **and** answer cell. A zero answer emits no code |
| `clockwise` | hoists the root's 7 reads onto row 0, retiring seven rows (~⅕ of blanks). Printing `'0'`/`'1'` costs one `+` since they differ by one bit |
| `flowchart` | leaves laid on exact `(( ))` pitch with **no gutter** — n=4 drops 2444 → 1557 characters |
| `back` | load runs down column 0 so no row carries it as indent; one `/` does both turns |
| `streetcode` | shapes differ in aspect; a width picks among them. `_streetcode_lift` moves the leading run to the oncoming lane, taking columns off every row |
| `dig` | pruned rows are **never written**; `$` covers a run of cells so the forced reads need no block each |
| `wii2d` | bit-vector requirement sets, dedup of routes sharing a preimage effect; budget counted in *work units* so output is machine-independent |

### Structural / algorithmic

| Generator | Optimization |
|---|---|
| `bf_tree` | tree shares bit tests: `O(2**n)` vs minterm's `O(n * 2**n)` — XOR-n at n=8 is 20K vs 33M characters |
| `nocomment` | computes the numeric index and uses it as a byte-sized skip into a staircase — straight-line, no leaf chains. `s` doubles as a NOT gate, so the complement is computed at runtime from one embed. Past `n == 8` the index no longer fits a byte, so it is split into byte-sized summands and one staircase is walked per summand: `s` peeks rather than pops, so displacements add across stages and a chain of legal skips reaches any index |
| `home_row` | packs bits into one accumulator + linear chain; the removed routing generator walled at n=2 |
| `bfstack` | avoids branching entirely — encodes inputs as a number, decodes with nested loops |
| `suffolk` | branch-free minterms at `limit=1`; a constant table needs no minterm *blocks*, though it still reads every input (8 reads on every table, constant or not); dense tables evaluated from their zero rows and inverted |
| `three_x` | result defaults to the **majority** table value, so only differing rows emit an override |
| `bitdeque` / `ram0` | fixed-length setters keep absolute `GOTO` targets stable — this is what unblocked the earlier "variable-length setter" wall |
| `lamfunc` / `ram0` | each input stored once and read back, rather than re-embedded at every node |
| `point_break` / `arrowqueue` | no output command — use the halt/loop termination convention |

### Equal-width embedding (the deliberate non-optimization)

`bio` (`0oz;` to a dead register), `bfstack` (4-char run proved minimal by
exhaustive search over `<>@[]`), `back` (constant `-` primer, then `+` or `-`),
`home_row` (`a` then `s` or `j`), `bfpda` (4 chars), `eval` (2 chars),
`bitdeque`/`ram0`/`minsky_swap` (fixed-length setters), `wii2d` (one-column
junction slot). `back`'s zero once embedded as a blank that `rstrip` removed,
making the program's *height* reveal the input.

---

## Sources

- Shared machinery: `text/helpers.py`, `boolean/helpers.py`, `wrap.py`,
  `laserfuck_layout.py`, `ztoalc_starts.py`, `_polynomial.py`
- Folding classification: measured, not inherited (see "measure against
  every one-dependency table" above). The method is a ones-count-controlled
  length test — equal ones-counts keep `_maybe_complement` and
  minterm-count-driven generators from shrinking for the wrong reason, so a
  strictly shorter program on the folding table means the generator folds. A
  generator that picks its own split order (circlefuck, unsquare) folds
  every one-dependency table, so it is the reorder rather than the fold that
  the MSB-aligned table measures there.
- Everything else: generator docstrings and bodies under
  `src/esolangs/tools/{text,boolean}/`
