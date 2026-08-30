# What each text / boolean generator optimizes

Catalog of the size-and-shape optimizations each of the 45 text and 61 boolean
generators applies to the *emitted program*.

"Optimization" here means what the generator does to make its output smaller
or better-shaped — not the runtime of the generator itself.

Figures here are measurements and go stale when a generator changes; the
script that re-derives the shape classification is
`tests/tools/test_boolean_contract.py::test_generator_shape_is_what_the_catalogue_says`,
which fails rather than drifts. Prefer stating what a future change must
respect over what a past change did — the latter is in the commits.

---

## The recurring techniques

Ten patterns account for nearly everything. Most generators combine two or
three.

| # | Technique | What it buys | Lives in |
|---|---|---|---|
| 1 | **Delta encoding** | each character costs its distance from the previous one, not its full code point | `text/helpers.py:28` `delta_program` |
| 2 | **Multiply/factor loops** | a byte costs `O(sqrt(v))` instead of `O(v)` via `a*b + r` | `text/helpers.py:71` `_factor_triple` |
| 3 | **Binary doubling** | a byte costs `O(log v)` by walking its bit expansion | addsubjump, unsquare |
| 4 | **Shortest-of-N dispatch** | build two constructions, measure, return the smaller | laserfuck, streetcode, %^2^-1, brainfuck |
| 5 | **Constant-subtree folding** | a subtree whose rows agree emits a leaf, not a branch | `boolean/helpers.py` (both walkers) |
| 6 | **Complement / polarity** | a dense table is evaluated from its zero rows and inverted | `boolean/helpers.py:44` `_maybe_complement` |
| 7 | **Shape-aware width** | honour a width by building a *different* shape, not by reflowing | `laserfuck_layout.py`, `wrap.py` |
| 8 | **Literal batching** | print a whole string in one statement rather than per character | `text/helpers.py` `_literal_chunks` |
| 9 | **Equal-width embedding** | *anti*-optimization: pad both bits to equal width so length can't leak inputs | `boolean/helpers.py:97` `instantiate` |
| 10 | **Dependency reduction** | a table that ignores an input is emitted as the *smaller* table, reading and discarding the rest | `boolean/other.py` `_taglate_dependencies` |
| 11 | **Input reordering** | the tree splits on its inputs in whichever order emits the shortest program, so more subtrees fold — the bar is that the **emitted program changes** and still **consumes its inputs in the same order**, which rules out only a template whose emitted program is *identical* under the permutation | `boolean/helpers.py` `best_input_order` (`six_five`, `forth`, `streetcode` and `laserfuck` roll their own) |

## Which shape a boolean generator is

Most of the boolean techniques apply to one shape and are meaningless for
the other, so the shape is worth knowing before reaching for one. Folding
(5), input reordering (11) and dependency reduction (10) are tree
optimizations; complement/polarity (6) is a minterm one.

The two are told apart by **what the size depends on**. A minterm sum costs
one term per selected row, so its size tracks the ones-count and is blind to
*which* inputs those rows involve. A decision tree costs one leaf per
surviving subtree, so at the same ones-count a table depending on a single
input is far cheaper than parity. Measured 2026-08-28 over all 59 exported
generators, comparing the best of the six one-dependency tables against
`01101001` (both ones-count 4):

**Tree-shaped (43).** taglate, ztoalc_l, polynomial, dig, myscript, six_five,
addsubjump, sophie, modulous, laserfuck, nevermind, jaune, bitdeque,
unsquare, flowchart, streetcode, forth, basicfuck, bfpda, ram0,
forbin_boolean, arrowqueue, back, lamfunc, between, eval, factor, circlefuck,
painfuck, bf_tree, brainfuck, three_d_brainfuck, sbleq, dimensional,
dimensional_tree, clockwise, brainif, three_x, circuit_diagram, minsky_swap,
decleq, grapheme, bio — folding 95% (taglate) down to 5% (bio).

**Minterm-shaped (13).** a_painter_ant, bfstack, bit_tilde, cod,
collatz_multiverse, container, home_row, nocomment, point_break, qoibl,
rotfuck, suffolk, suptiftam — all within 4% of parity on a one-dependency
table, because there is no subtree to collapse.

**Neither (1).** `wii2d` measures *negative* (a one-dependency table costs
slightly more than parity): its construction is a route search over a grid,
so neither model describes it.

Two entries sit near the boundary and are worth reading as measurements
rather than labels. `circuit_diagram` folds only 12.6% yet special-cases a
constant to 57 characters against 2756 — it is a minterm sum whose
*constants* are special-cased, so the split-order metric puts it on the tree
side for the wrong reason. `minsky_swap` comes out at 10% only because a
one-dependency table is *smaller* than parity there by a few characters of
embedding, not because anything folds.

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
| `bfstack` | same hybrid, with a measured threshold |
| `unsquare` | delta chain off the retained accumulator (~21% on "Hello, World!"), **bounded by parity** — `x` can't restore oddness, so odd targets off an even accumulator reseed |

### Arithmetic-construction

| Generator | Optimization |
|---|---|
| `home_row` | `a*b+r` counter loop, `a` searched near `sqrt` → `O(sqrt)` |
| `suffolk` | factors minimizing `a + 2b + 2r` — *not* `sqrt`, because `>!` and `><` cost two characters each |
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
- **`ztoalc_l`** — precomputed anchor table (`ztoalc_starts.py`) of Collatz
  starts with the smallest trajectory peak per length interval.
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
all-1 444) and `rotfuck` (1404, 1740) are cheap on all-zeros and expensive
on all-ones, and neither calls `_maybe_complement`. Taking the cheaper
polarity of every n=3 table would be 17.96% for `a_painter_ant` and 2.99%
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

**A note on `a_painter_ant`'s classification, since it reads oddly.** It
*builds a tree* — `_head` paints one leaf per input combination and the ant
is routed to the leaf its inputs select — but it is listed as minterm-shaped
above, and that is right, because the classification is about **what the size
depends on**. Each one-leaf emits a paint-and-return walk and each zero-leaf
emits a single space, so the cost tracks the ones-count and is blind to which
inputs the table depends on: measured, every ones-count-4 table at n=3 costs
exactly 268 characters, one-dependency and parity alike. Structure and cost
model can disagree, and the catalogue tracks the latter.

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

### Dependency reduction (10) — taglate

A table ignoring an input is emitted as the *smaller* table, reading and
discarding the rest (`_taglate_dependencies`). Note `taglate`'s own
`_reorder_tt` is a different thing despite the name.

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

**Shipped:** `six_five`, `jaune`, `eval`, `circlefuck`, `unsquare`, `sbleq`,
`three_x`, `forth`, `sophie`, `polynomial`, `addsubjump`, `streetcode`,
`laserfuck`, `back` (via `best_input_order`; `six_five`, `forth`,
`streetcode` and `laserfuck` roll their own — the two grid ones because their
`width` has to choose among *every* candidate, and `best_input_order` returns
only the shortest. `back` has no width, so it uses the wrapper).

**Not applicable — sum-of-minterms**, where the minterm count does not depend
on split order: `a_painter_ant`, `circlefuck_byte`, `circuit_diagram`, `cod`,
`container`, `grapheme`, `home_row`, `jaune_multiply`, `point_break`,
`suffolk`, `suptiftam`.

**Measured upside but unreachable as a reorder** — no addressable storage to
hold a read bit, so a bit can only be branched on before the next read:
`polynomial` (25.1%), `modulous` (16.4%), `sophie` (16.4%). Residual merging
collects what the screen was measuring for polynomial and sophie.

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
kept. It screened 4.9% and delivered 5.2% at n=3 / 8.0% at n=4, verified by
11000 interpreter runs — the win was real. But its reads sit at its nodes,
so reaching it took ~146 lines resting on a language invariant subtle enough
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

**The grid tier is not all layout surgery — streetcode was the first one
opened.** It screened 16.8% and **delivered 16.76%** at n=3 (258872 → 215478
characters over all 256 tables, 112 of them improved, none grown; every one
verified against the interpreter, plus 57 tables at n=4 over 912 runs). It
came in a shade *under* its screen — 16.8% → 16.76%, the same 0.04pp shave
circlefuck took at 10.47% → 10.42% — which is what the rule predicts for a
node testing a **position** rather than naming an input: the walk that puts
each bit in its cell is the difference. Its halls test cells positionally: every
hall spends one `=`, so level *k* tests cell *k+1* whatever is in it. That
makes the reorder a **placement** rather than a walk. Only the shared
shape's prefix changes, from stepping one cell per read to walking to each
input's target: at two inputs a swap reads `==I_I` where the identity reads
`=I=I`. The tree, the fold, the leaf's `skipped` advances and the lap are
untouched, and the reads stay in stream order.

Three things that decided the build, worth carrying to the rest of the tier:

- **The cell map is the inverse of the permutation.** Level *k* tests cell
  *k+1* and must test input `perm[k]`, so input *i* is stored at
  `perm.index(i) + 1`. Reading it forward stores the right bits in the wrong
  cells and every non-identity order computes a different function.
- **Only one shape needed touching.** The shared shape wins *every* table at
  n=1..4, so the ring and hallway survive only as `width` fallbacks and are
  built at the identity order alone. Their labels thread the `+1` hand-off
  between neighbouring loops, which a permuted placement would have to
  re-derive for no measured gain — measured, not assumed.
- **The walks are junction-free.** The prefix runs down the shaft, not along
  the street, so no mouth is crossed while CP names an arbitrary cell — which
  is what makes a permuted prefix as safe as the identity one under the
  gap-junction law. The fixed seeding suffix is relative to cell *n*, so the
  prefix walks CP back there after the last read rather than assuming it
  landed there.

**LaserFuck is the second, and it confirms the rule.** It screened 16.3% and
**delivered 16.08%** at n=3 (99527 → 83527 characters, 112 of 256 tables
improved, none grown; verified over 8192 interpreter runs — every table, every
row, all four initial headings — plus 47 tables at n=4 over 3008 runs). Its
node is `>#v)`: step the pointer, then `)` tests the cell under it, so level
*k* tests cell *k+1* exactly as streetcode's halls do. Only the reader's read
section changes, from `,>,>,<<<` to a walk between each `,`.

It was *easier* than streetcode, and the reason is worth stating: the read
section sits between the two rings, past `multiply`'s `)` and before
`retire`'s `}`, so it holds no conditional characters at all. A walk there
cannot steer the beam, so there is no analogue of the gap-junction law to
design around — the whole hazard budget streetcode spent was language-
specific. Check where a candidate's reads sit relative to its conditionals
before assuming the same cost.

The one shared trap is the frame: **the cell map is the inverse of the
permutation** in both, and both start their walk from wherever the preceding
block left the pointer (streetcode cell 0, LaserFuck cell 1 — `multiply` ends
on a `>`). Deriving the identity spelling first and checking it reproduces
what the generator already emitted catches an off-by-one before any table is
run.

**Back is the third, and it is where a cheaper build was measured and then
declined.** It screened 12.0% and **delivers 16.55%** at n=3 against its own
identity order (25167 → 21003 characters, none grown) and **17.33% at n=4**
over the complete 65536-table space. Verified by 2048 fill-and-run cycles at
n≤3 and **1048576 at n=4** — every table, every input combination — with the
equal-width embedding checked on each one.

Node `+\>` tests the current cell and *then* advances, so level *k* tests
cell **k**, one lower than streetcode's halls and LaserFuck's `>#v)`, which
both step before they test. Input *i* therefore belongs at cell
`perm.index(i)` — the inverse of the permutation — and the load walks the
pointer there with `>`/`<`, exactly as the other two placements do.

**A free build exists and is not used.** Filling in *cell* order instead —
putting `{X perm[c]}` in cell *c* — emits no walk at all, because the pointer
only ever steps one cell forward, and it measured **11.99% against the 12.0%
screen**: the store-target regime (`three_x`, `decleq`), where the screen is
exact. It is declined because it leaves the template's placeholders out of
name order, and every other generator in this module emits `{X0}`..`{Xn-1}`
in sequence. Both forms are correct — `instantiate` substitutes by *name*, so
a placeholder is filled wherever it sits — so the choice is consistency, not
correctness, and it is worth recording that it costs about 2.85 points.

Mind the two baselines when comparing those numbers. **11.99% and 12.0% are
against the pre-reorder generator**, which loaded in name order and stepped
one cell at a time. **16.55% is against this generator's own identity order**,
which now spends a walk of its own, so its identity build is larger (25167
against the old 23119) and the same emitted programs measure as a bigger
saving. The 21003 characters the walk build actually emits is the figure to
compare across builds: the free build emits 20347.

The load's units are emitted in **reverse** name order, because the load is
drawn bottom-to-top up column 0 (the beam runs up it), so the template's text
reads them backwards: loading input *n−1* first is what puts `{X0}` first on
the page. One consequence is worth knowing — with the units reversed, parity
now *shrinks* under reordering (126 → 118 at n=3) without folding anything,
because some orders simply spend a shorter walk. "The identity order wins on
a table that folds nothing" was true of the walk-free build and is not a
general invariant; what survives is the one-sided one, that no table comes
out larger than its identity build.

The walk itself is cheap in absolute terms — two characters a move, the
character plus the newline its own load row carries — and reads as a couple
of points only because Back's programs are small: 82 characters on average at
n=3, against LaserFuck's 326 and Streetcode's 842. **Price a walk against the
program's own size**; compact programs are where a fixed cost shows up as a
large fraction.

**One layout idea is screened and unbuilt.** The load runs up column 0 at one
command per row, so it is `2n+2` rows tall while the tree needs only ~7.5;
snaking it into two columns would halve that. Counted at n=3 it nets about
**+1.9%** — 13 characters of rows saved against 7.5 for shifting the tree one
column right and ~4 for the turn mirrors — which is under the 5% bar for a
cheap change, and the mirror estimate is the soft part: a turn cell cannot
also carry a load command, and `+`'s conditional step interacts with the
beam's direction at a mirror. Recorded rather than built.

**The rest of the tier, and why each closes.** What is left splits by *where
the node reads*, which is the same question the token-sequence tier answers,
not by being 2D:

- **`clockwise` (1.3%, a lone accumulator) and `wii2d` (3.4%)** have nothing
  to place into and sit below the threshold anyway.

**`dig` (19.8%) and `flowchart` (17.1%) both read at the node, and both
close.** Each was costed against rule 2 before any code was written, and
neither clears the 10% bar — the screen figures are the largest left in the
tier and are still not worth reaching.

**`dig` closes on the language, not the arithmetic.** `_DIG_BRANCH` is
`>2$~;#@`: read, store and turn in one fixed block. The store looks like
somewhere to park a bit, and it is not — `_value()` reads only the cells
*adjacent to the mole*, taking the first digit in a fixed direction order,
and the mole has a single accumulator. So a hoisted bit is readable only
while the mole stands beside it, and a tree has many nodes testing the same
input from different squares. That leaves re-embedding per node (the
`wii2d_tree` wall) or walking the mole back past each stored digit
(relocation, which is what made `brainif` deliver only its screen). Neither
is a hoist that deletes work.

**`flowchart` closes on a count, and it is negative before the hard part is
counted.** The setup is the promising one: today every skipped level still
pays a `/ /` box on a folded leaf's rail, because the reads are the
interface, so a hoist that reads all `n` inputs once in staging should
delete those — the pattern that made `addsubjump` beat its screen. Counted
over all 256 tables at n=3, it does not: 1724 `/ /` boxes against 1214
`< >` switches, so folding saves only ~2 rail boxes per table. Removing
every read box recovers 6896 characters; staging `n` inputs costs 6144
(`/ /` plus `\[ ]/` per input) and popping instead of reading at each node
costs 2428 more. That is **−1676 characters, −1.43%, before a single
`< ]`/`[ >` deque select is counted** — and the selects are the dominant
term left, since each node must walk the cursor to its own input at three
characters a step.

The deques are real and the pops would work (only one root-to-leaf path
runs per execution, so each input is popped at most once). The construction
is simply not cheaper than the reads it replaces. Worth keeping as the case
where the *language* has the richest storage in the tier and the hoist still
loses — read the generator to classify, then count before building.

**What the fill-slot bar rules out, precisely.** It is a test on the emitted
**drawing**, not on where the names sit. "Permuting a parameterized
template's fill slots is not a reorder" excludes a template whose program is
*byte-identical* under the permutation — there the saving is booked against
the harness's fill order and nothing was made smaller. It does not exclude a
template whose drawing changes, and both shipped parameterized reorders
change one by emitting different code, not by moving names: `eval`
**interleaves runtime ops between the slots** (`_eval_stack_programs` records
that the `{Xi}` blocks keep their slots and the harness fills them exactly as
before, while the emitted ops rearrange the stack the nodes pop from), and
`back` **walks its pointer between the load units**. Both keep their
placeholders in `{X0}`..`{Xn-1}` sequence, and both pay real characters for
the rearrangement.

**Permuting the names is legal and is still not done.** `instantiate`
substitutes by *name*, so a named input reaches its own slot wherever that
slot sits; a build that permutes Back's slots and keeps the tree on the
permuted table changes the drawing and clears the bar, and it is free —
measured at 11.99% against a 12.0% screen, against 16.55% (identity-relative)
for the walk build. It is declined so that every template in the module reads
in name order, which `test_slots_run_in_name_order` now enforces. Worth
knowing the option exists and what it costs, rather than believing the bar
forbids it.

**The free-reorder trick turned out to be the outlier, not the pattern**, and
that is part of why Back does not use it either. The obvious follow-up was to
apply it to every generator that pays for its reorder, so each was measured
against a *free-reorder ceiling*: the same fold, built with the identity
emission on a permuted table. The headroom is what such a build would take
off the shipped size, and there is none worth having (n=3, all 256 tables):

| generator | shipped | ceiling | headroom |
|---|---|---|---|
| `lamfunc` | 11.71% | 11.71% | **0.00%** — already free |
| `bitdeque` | 14.90% | 15.67% | 0.90% |
| `ram0` | 14.75% | 13.31% | **−1.69%** |

`lamfunc` was already in Back's regime: each input is stored once and read
back by name, so its reorder is a pure rename with nothing to pay. `bitdeque`
pays rotations (`EJECT PUSH` / `POP INJECT`) but they are cheap against its
programs, and removing them is blocked in the *harness* rather than the
language — `_fill_bitdeque` derives each setter's `INVERT PUSH` / `PUSH
INVERT` parity from the input's **name**, assuming input *i* sits at load
position `n−1−i`, so permuting names between slots would desync every fill
site. Fixing that is fill-harness surgery for 0.9%.

`ram0` is the interesting one: its shipped reorder **beats** the free
ceiling, so permuting is doing something folding alone cannot. That is the
per-language cost `best_input_order`'s docstring predicts — RAM0 spells an
address as a run of `A`, so a good order also wants the deep levels on low
addresses. A "free" reorder there would be a *worse* one.

`arrowqueue` (12.4%) is separate: it is
a *queue*-fed grid template, so a real reorder needs re-enqueue gadgets to
bring a bit to the front. Permuting which `{Xi}` name sits in each header
slot is not an alternative: `_header_rows` fills the header positionally
from the bits, so the names are inert, and even if they were not, an
identical emitted program booking a saving against the harness's fill order
is a redefined benchmark rather than a smaller program. **The bar is that
the emitted program changes and still consumes its inputs in the same
order.**

**The sequential queue is closed.** Every remaining candidate was screened at
n=3 over all 256 tables and then checked against the rule above; none is worth
building, and three close for reasons the screen figure alone does not show —
re-screening them would only reproduce the numbers below.

| generator | screen | why it closes |
|---|---|---|
| `brainif` | 4.9% | built, delivered 5.2%/8.0%, **reverted** — reads at the nodes, so reaching it cost ~146 lines on the guarded-pair law for a hoist that relocates cost rather than deleting it (see the rule above; construction in `d04932c`) |
| `taglate` | 3.1% | below the rename threshold |
| `minsky_swap` | 2.8% | **no decision tree** — `{Xi}` setters assemble the input's numeric index into `reg[0]` and a `~` cascade routes value *v* to leaf *v*, so there is no split order to permute |
| `bio` | 1.5% | **no decision tree** — each `{Xi}` packs `2**w` into `x`, so the program computes an index rather than branching on bits in an order |
| `decleq` | 1.4% | a real rename (reads land in `n` cells up front; a node's `cell cell c` can name any of them) and it was built and verified — 1.42%/2.25%, 14536 interpreter runs, nothing grown — but below the threshold, so it was **not kept** |
| `nocomment` | 0.7% | minterm-shaped; reordering is not applicable |
| `painfuck` | 0.5% | **already reordered** — it translates `brainfuck`'s output, so it inherits `decision_tree_program`'s reorder the way `factor` and `three_d_brainfuck` do; the residue is translation effects, not upside |
| `rotfuck` | 0.4% | minterm-shaped |
| `bfstack` | 0.2% | minterm-shaped |

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
during construction needs that check frame-mapped too. ZTOALC L asks its
simulator whether the program computes `truth_table[c]`, but a reordered tree
walks to the row whose bits are gathered in `perm` order, so the unmapped
check demands a different function and rejects every correct placement. The
symptom is a clean 0.00% across every table — indistinguishable from
"reordering does not help here".

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
| `nocomment` | computes the numeric index and uses it as a byte-sized skip into a staircase — straight-line, no leaf chains. `s` doubles as a NOT gate, so the complement is computed at runtime from one embed |
| `home_row` | packs bits into one accumulator + linear chain; the removed routing generator walled at n=2 |
| `bfstack` | avoids branching entirely — encodes inputs as a number, decodes with nested loops |
| `suffolk` | branch-free minterms at `limit=1`; a constant table needs no minterm *blocks*, though it still reads every input (measured 2026-08-28: 8 reads on every table, constant or not — an earlier note here claimed it read none); dense tables evaluated from their zero rows and inverted |
| `three_x` | result defaults to the **majority** table value, so only differing rows emit an override |
| `bitdeque` / `ram0` | fixed-length setters keep absolute `GOTO` targets stable — this is what unblocked the earlier "variable-length setter" wall |
| `lamfunc` / `ram0` | each input stored once and read back, rather than re-embedded at every node |
| `ztoalc_l_boolean` | tries every `b1` in turn with the simulator as sole gate, keeping any smaller start that places without collision |
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
- Folding classification: measured, not inherited. The method is a
  ones-count-controlled length test — equal ones-counts keep
  `_maybe_complement` and minterm-count-driven generators from shrinking for
  the wrong reason, so a strictly shorter program on the folding table means
  the generator folds. **Compare against every one-dependency table, not
  just `11110000`:** a generator that branches last-input-first (modulous,
  forth) folds `10101010` instead, and testing only the MSB-aligned table
  reports those as non-folding when they save 56–77%. A generator that picks
  its own split order — circlefuck and unsquare since they started reordering
  — folds every one-dependency table, so it is the reorder rather than the
  fold that the MSB-aligned table now measures there.
- Everything else: generator docstrings and bodies under
  `src/esolangs/tools/{text,boolean}/`
