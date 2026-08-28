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
| 11 | **Input reordering** | the tree splits on its inputs in whichever order emits the shortest program, so more subtrees fold | `boolean/helpers.py` `best_input_order` (`six_five` rolls its own, to keep its node-read build as a candidate) |

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

### Constant-subtree folding — the single biggest lever

Verified by a ones-count-controlled length test (equal ones-counts prevent
complement effects from confounding); see Sources for the method and its one
pitfall.

**Fold (16):** addsubjump, back, bfpda, bio, bitdeque, grapheme, jaune,
lamfunc, nocomment, polynomial, ram0, rotfuck, sbleq, six_five_arithmetic
(since retired — see below), three_x, ztoalc_l — plus basicfuck, brainif,
dig, laserfuck, between, and the
`decision_tree_program` pair (brainfuck/bf_tree, dimensional/dimensional_tree),
which fold inside their own construction.

**Also fold (5, re-measured 2026-08-27):** myscript, nevermind,
forbin_boolean, flowchart, sophie. The prior audit listed these as
non-folding; the ones-count-controlled test disagrees, e.g. sophie 25 vs 111
characters and flowchart 166 vs 632 on `11110000` against `10010110`.

**Build a tree but never fold (0).** `circlefuck` / `circlefuck_byte`,
`forth`, `decleq`, `eval`, `clockwise`, `streetcode`, `six_five` and finally
`arrowqueue` were all on this list and now fold — see below. **Every tree
generator in the catalogue folds its constant subtrees.**

**Re-checked by measurement 2026-08-28, and it still holds.** The worry is a
generator that special-cases a *whole-table* constant without folding
subtrees, since that collects the easiest case and leaves the general one.
The signature is a table depending on a single input costing the same as
parity — a full tree either way — while the constant is tiny. Screening all
59 generators on `00000000` / `11110000` / `01101001` flags twelve, but eight
of those fold under a *different* split order (Modulous, Forth, Circlefuck
and Unsquare branch last-input-first, so `10101010` is their folding case,
not `11110000`), and the comparison has to allow for that: measured against
the best of all six one-dependency tables, they save 56–77%.

The seven that genuinely never fold — `point_break`, `collatz_multiverse`,
`suptiftam`, `bit_tilde`, `a_painter_ant`, `qoibl`, `suffolk` — are all
**sum-of-minterms**, and a minterm sum has no subtrees to fold. Its cost is
one term per selected row, so a constant table is small because the sum is
*empty*, not because anything was collapsed. That is a different technique
(6, complement/polarity), not a missing one. **Nothing is left to convert.**

`point_break` is the one to look at if this seems too neat, since it *does*
carry an explicit constant short-circuit. Both constants complement to zero
selected rows, so the general path would emit an empty sum — the reads, the
complement setup and the loop scaffolding wrapped around nothing. The
short-circuit skips that scaffolding; it is not standing in for a fold,
because there is no tree underneath it to fold. What it must still do is
read its inputs, which it did not until this branch fixed it.

**Should the other minterm generators get the same short-circuit?** Measured
2026-08-28: no, because eight of the thirteen already emit their *smallest*
program on a constant table, with nothing left to strip — `bit_tilde`,
`cod`, `collatz_multiverse`, `container`, `qoibl`, `suffolk`, `suptiftam`
and `point_break` itself, whose 35 and 71 characters sit well under the 164
its other tables need. An empty sum is already the cheap case; the
short-circuit only earns its place where the scaffolding *around* the sum is
what costs, which is Point Break's loop guard and nobody else's.

Two do have headroom, and it is **not** a missing constant case:
`a_painter_ant` (all-0 92, all-1 444) and `rotfuck` (1404, 1740) are cheap
on all-zeros and expensive on all-ones. That asymmetry is the signature of a
missing *complement* (technique 6) — neither calls `_maybe_complement`, so a
dense table is summed over all its one-rows instead of its zero rows, and
all-ones is the extreme case. Worth doing, but as polarity, not as a
constant special-case; mind the trap `_maybe_complement`'s docstring
records, that an all-ones table complements to the same empty sum an
all-zeros table has.

Their read counts were checked at the same time, since an empty sum can drop
the reads the way a folded tree can: all seven consume every input on a
constant table. The note below that `suffolk`'s "constant tables need no
reads at all" is stale — it reads all 8.

Each was written off at some point on structural grounds, and each of those
arguments was wrong in the same way: they described why a folded node could
not be *removed*, when the fold only needs it *replaced* (`eval`) or its
skipped work *carried* (`streetcode`'s `=` advances, `arrowqueue`'s drains).
Treat the next such claim as a hypothesis.

Each used to emit a byte-identical program size for every table of a given
`n` — the signature of not folding, since the leaf count was fixed by `n`
alone — while growing ~2x per added input (measured n=2→4 before the folds:
forth 58→332, streetcode 591→3391, clockwise 255→1479). That per-row cost is
what the folds collapse. They were *not* uniform in how reachable the saving
was, and the accounts below are kept because the obstacles differed:

**Token-stream trees — tractable.** `circlefuck` / `circlefuck_byte`, `forth`,
`decleq`, `eval` and `six_five` emit a linear token sequence, so a fold is
a leaf test plus whatever index bookkeeping the language needs.

- `circlefuck` — Reads are unconditional and up front,
  and each leaf halts with `@`, so there was no sibling bookkeeping for a fold
  to disturb. `circlefuck` is a thin wrapper over `circlefuck_byte`, so the one
  fold serves both. Measured at n=3: `11111111` 594→203, `10101010` 594→263,
  `11001100` 594→384 characters.

  Two things were only visible from the code. Its subtrees are **strides**, not
  contiguous runs — it branches on the last input first, like Modulous — so the
  constant-test walks `range(row, len(table), 2**(n-1-k))` and `11110000` still
  folds nothing. And a folded leaf must emit its own `[-]`: the clear a
  full-depth leaf relies on lives inside each `[` on the way down, so skipping
  levels leaves the input bit in the cell and every one-valued input prints one
  too high. Verified exhaustively over every table at n≤3 (276 tables × every
  input combination) through the real interpreter, plus 47 tables at n=4 and
  random byte tables for `circlefuck_byte`.
- `forth` — It wrote every node of a full
  heap-indexed tree, `for m in range(1, 2**(n+1) - 1)`. The heap indices
  looked like an obstacle but were not: the interpreter stores scopes in a
  `dict[int, str]` keyed by the pushed number and calls with `.get()`
  (`interpreters/stack_based/forth.py:86,168`), so a gap in the numbering is
  just a scope that never exists — the fold is skip-emission, no renumbering.
  Measured: n=3 constant `119→35`, n=5 constant `571→45` (12.7x), and even a
  random n=5 table improves `753→571`. The committed example went `58→44`.

  Doing this surfaced a coverage gap: `forth`'s tests asserted program
  *structure* only and never ran a program, unlike every other generator's
  `test_truth_table`. That test now exists (every table at n≤3 × every input,
  through the interpreter), so the fold is pinned by behaviour, not shape.

  The catch was **orphans**. Marking only a folded node's two children leaves
  its grandchildren emitted but unreachable — dead code that still costs
  bytes. The first version produced a *constant* table (99 chars) larger than
  a partly-constant one (63), which is what exposed it; the fix walks the
  whole subtree. Pinned by `test_folded_subtree_leaves_no_orphans`.
- `decleq` — Same self-modifying-memory family as
  `sbleq`. Unlike the other two it splits **most-significant-first**, so its
  subtrees are contiguous runs and `11110000` folds here (to a single branch)
  where it folds nothing in circlefuck or forth.

  The twist is that `data_base` is computed *before* emitting — the output
  cells sit above the code, so their addresses depend on how long the tree
  turns out to be. A second walk (`tree_instrs`) sizes the tree first and must
  stop in exactly the places the emitting walk will.

  When the count is right, the code ends exactly at `data_base` and
  `mem.extend([0] * (out49 - len(mem) + 1))` allocates only the `n` read cells
  and the two output cells — the finished program contains no filler at all.

  Getting the count wrong is invisible from the output: the allocation fills
  out to whatever address was reserved, so every leaf still resolves and the
  program still prints correctly — it just carries a block of dead zero cells
  (63 at n=3). The test therefore pins the *cell count*, not the output; an
  output-based test passes either way, which I confirmed by desyncing the
  count deliberately.

  Savings are modest at small `n` because the 47-step normalize chains are a
  fixed `47n` cost the fold cannot touch, but they grow as the tree overtakes
  them: constant vs XOR is 7% at n=2, 16% at n=4, and **44% at n=6**
  (3448 vs 6148 characters).
- `eval` — the "positional indexing blocks it"
  call above was wrong. The premise held: the heap *is* positional, a node's
  `;` run is a function of its own index, and children sit at pinned
  `2i+1`/`2i+2`, so a folded subtree genuinely cannot be **removed**. The
  error was concluding it therefore cannot fold. It can be *replaced*: the
  node becomes the leaf it would have reached and its descendants become
  empty strings, so every index stays exactly where it was and the emptied
  slots are never popped, because the only node that routed into them is
  gone. Constant tables go `127→46` at n=3.

  Being parameterized, this one also has to preserve equal-width embedding.
  It does so for free — the fold shrinks the *template*, which is shared by
  every instantiation — but that is now pinned by a test rather than assumed.
- `six_five` — not marginal after all. It was
  listed here as marginal because only the n≤5 path used the tree, but the
  fold changed that too: it now decides the dispatch, and the second
  construction it used to defer to is gone (both below). The saving is the
  largest of any fold measured here:

  | n | constant | mixed (equal ones-count) | |
  |---|---|---|---|
  | 1 | 13 | 46 | 3.5x |
  | 2 | 14 | 106 | 7.6x |
  | 3 | 15 | 226 | 15.1x |
  | 4 | 16 | 466 | 29.1x |
  | 5 | 17 | 946 | 55.6x |

  (Constant column re-measured 2026-08-28; it had been recorded as 15/16/44/
  46/19, which was neither monotonic nor matching the emitted programs. A
  constant costs `n + 12`: the reads it must still spend, plus one leaf.)

  The committed example went 106→74 bytes.

  Markers needed no bookkeeping — unlike `forth`'s heap indices, `8n` jumps
  resolve by counting emitted `4`s in order, and a folded subtree simply
  allocates no marker and emits no `4`, so the numbering stays dense. The
  leaf tokens contain no bare `4` or `8` to miscount.

  The one real catch is the **leaf's base**. A full-depth leaf adds
  `48 + value - base` where `base` is 8 or 9, recording which way the last
  branch went. That cannot survive a fold: `B` *overwrites* the cell, so
  after the reads a folded leaf skipped it holds the last input character —
  48 or 49, differing per input — and every cell op (`5`, `6`, `2`, `9`)
  adds an unconditional constant, so no fixed suffix maps both to one
  value. Converging them conditionally would cost a `78` plus a jump, i.e.
  a marker, which is the scarce resource. The leaf instead steps to cell 1
  (`13`) and builds the digit from zero: cell 1 is untouched, because every
  tree path works in cell 0 and every leaf halts.

  The reads themselves are still spent — `B * (n - bit + 1)` — so a caller
  feeding several programs from one stream stays in sync. That invariant is
  pinned by `test_folded_leaf_still_reads_every_input`, which walks the
  emitted tree and asserts every root-to-leaf path spends exactly `n`
  reads; deliberately dropping the reads makes it fail `{1,2,3,4} == {4}`
  at n=4, so it is not a vacuous test. Verified exhaustively over every
  table at n≤3 (2120 runs through the real interpreter) plus constants and
  half-constants at n=4 and n=5.

  **The `n ≤ 5` gate is now raised too.** Folding is what spends the branch
  labels, so the dispatch counts them (`_six_five_markers`) instead of
  testing `n`: any table whose folded tree fits in 35 labels uses the tree,
  at any `n`. The old gate tested the *unfolded* node count, which is why
  it capped at n=5.

  This renders tables neither path could produce before — a table with ones
  at high indices has a huge `T`, so the arithmetic fallback refused it, and
  the tree was gated off:

  | table | n | labels | before | after |
  |---|---|---|---|---|
  | AND-6 (`0…01`) | 6 | 6 | `ValueError` | 191 chars |
  | one split | 6 | 1 | `ValueError` | 50 |
  | two regions | 6 | 2 | `ValueError` | 81 |
  | constant | 6 | 0 | 483 (arithmetic) | 20 |
  | AND-8 | 8 | 8 | `ValueError` | 256 |

  Verified through the interpreter over every input combination at n=6,
  plus n=7 and n=8 — the tree had never executed past n=5 before.

  The count must be exact, since the gate decides before building. It is
  structurally the same walk as the fold (both split MSB-first over a
  contiguous range, so a node's children are its slice's two halves),
  which avoids the second-walk desync trap `decleq` documents above. Note
  that counting `4` *characters* is not the same as counting markers: an
  `8n` jump whose operand happens to be `4` contributes one, which is why
  the test tokenizes the way the interpreter does.

  **`six_five_arithmetic` is retired.** A small `T` means ones confined to
  low indices, which leaves the rest of the table constant, which folds well
  inside the budget — the two conditions are mutually exclusive, so the
  kernel never covered a table the tree could not. Searching for a
  counterexample (contiguous prefix/suffix families exhaustively at n=6,7,8,
  plus ~18000 random sparse and dense tables) found **none**. The
  construction, its `_SixFiveAsm` assembler and `_six_five_nav` went with
  it: 299 lines down to 122. This is the third such retirement, after
  `brainfuck`'s and `dimensional`'s minterm evaluators — in each case the
  fold made the second construction redundant rather than merely worse.

  **Is the generator total?** No, and the boundary is exact. Labels are the
  only limit, and the worst case for the fold is a table no *input order*
  folds, which is **parity**: any permutation of parity is parity, so it
  spends the full `2**n - 1` under all `n!` orders. (An alternating table
  also folds nothing in stream order, and used to be quoted as the worst
  case, but it is only NOT of the last input — one reorder folds it to a
  single label.)

  | n | worst case | budget 35 |
  |---|---|---|
  | ≤5 | 31 | fits — **every table renders** |
  | 6 | 63 | over |
  | 7 | 127 | over |
  | 8 | 255 | over |

  So `six_five` is total through n=5 and partial above it, where it now
  raises `ValueError` naming the label count instead of falling through to
  a kernel that would have refused the table anyway. What survives past n=5
  is tables that fold hard — and since the budget is spent per input order,
  a table only has to fold under *some* order. Measured over 2000 random
  n=6 tables, 1.5% fit in stream order and **13.6% fit under the best of
  the 720 orders**, so reordering widened the renderable set about ninefold.
  At n=7 neither figure is above 0% (500 sampled) — though structured
  tables like AND-n fit at any width, needing just `n` labels.

**Grid trees.** `clockwise`, `streetcode`, `arrowqueue` place their tree on a
plane. `clockwise` turned out to need only a leaf test plus two geometry
corrections and **is now folded** (see above). `streetcode` was attempted and
**reverted** — see below. `arrowqueue` was the last one and **is now folded**
(below), so every tree generator in the catalogue folds.

#### arrowqueue: done — the queue is drained, not worked around

**Resolved.** A constant table is 93 characters against 275 at n=3, and 130
against 1434 at n=5. No program grows, instantiated or template (checked
exhaustively through n=3 against the pre-fold generator). The committed
example dropped 124→110 bytes.

The fold was **asymmetric** before the drain existed, which is what made it
look blocked. Collapsing a subtree to a bare leaf at n=2, against the real
interpreter:

| folded tree | want | got |
|---|---|---|
| whole tree → bare `1` leaf | `1111` | `0000` ✗ |
| whole tree → bare `0` leaf | `0000` | `0000` ✓ |
| left half → `1` leaf | `1100` | `0000` ✗ |
| left half → `0` leaf | `0011` | `0011` ✓ |

Every leaf relies on the queue holding exactly `R, D, L, U`, because the
ring's corner pops consume them in that order. Skipping a `+` branch leaves
that bit's direction queued ahead of them: the folded all-ones program
reaches the tree with `[R, R, R, D, L, U]`, so the corners pop `R, R, R`,
the ring never closes, and the pointer leaves the grid — reporting `0` for a
`1`. A **0-leaf is immune**, since it halts by leaving the grid anyway.

**The drain is what unblocked it,** and the key fact is that `+` *erases
arrival direction* — it points the IP wherever the popped value says,
regardless of how the IP got there. So a drain does not have to merge two
headed paths, only route two paths to the same **cell**:

```
 +*      the + pops one stale bit
*  *     a 0 goes right, then a * turns it down
** +*    a 1 goes down and three * walk it back up and right
```

Both exits land on the next `+` — the 0 route arriving headed down, the 1
route headed right, which a `+` does not care about. Chaining steps one row
down and one column right per drained bit, and the chain pushes nothing, so
the ring receives exactly the queue it expects.

Two things were only visible from the interpreter. The gadget's first draft
lost the 0 route: without a `*` at the exit column it runs straight off the
grid instead of turning down. And the drained leaf's grid needs
`skipped + 4` columns, not `skipped + 3`, since the 3-wide leaf sits at
column `skipped + 1`.

Verified exhaustively at n≤3 (every table × every input, through
`run_until_halt_or_cycle`), plus structured and random tables at n=4 and
n=5, and the whole n=4 split family. Deliberately removing the drains fails
16 tests, so they are pinned by behaviour.

**Only `1` leaves are drained.** Draining `0` leaves too was a measurable
mistake: a `0` leaf halts by running off the grid whatever is queued, so its
drain buys nothing, and it *costs* — the staircase sits a column right of the
branches it replaced, leaving `_compact` fewer all-blank columns to drop.
AND-2 is the case (only its `00` half is constant), and it went 124→128 bytes
until the case was carved out. It is 109 now, below where it started.

That the fold must never grow a program is pinned by
`test_folding_never_grows_a_program`, which compares every table at n≤3
against the pre-fold construction.

#### the reusable drain — verified, deliberately not shipped

The staircase unrolls one gadget per skipped bit, so a deep fold's leaf is
wide. A **single** drain cell can do the whole job instead, because a `+`
whose exits both return to it keeps popping until the queue is spent —
verified draining k=0..5, every stale pattern. This one works (user's
design, verified here rather than invented):

```
    +~+
    ~ ~
    +~+
  *~  *
*  *  ~
***+*~*
  ***
```

Wired in behind a depth dispatch it is **correct everywhere** — 0/2120 on
the exhaustive n≤3 sweep, plus n=5/6/7 constants and half-constants in both
entry modes. It is not shipped because neither construction dominates:

| skipped | staircase | reusable drain |
|---|---|---|
| 1 | 60 | 92 |
| 3 | 93 | 108 |
| 4 | 111 | 116 |
| **5** | 130 | **124** |
| 8 | 193 | **148** |

They cross at five skipped levels, which needs n≥5 — past where the test
suite exercises folding at all. Shipping both would mean a second
construction and a dispatch for a win nothing currently reaches, so the
staircase stays and this is recorded instead.

**What it cost to find, and the constraint that matters.** The drain accepts
exactly *one* entry: falling **south down column 1**. But a folded leaf is
reached three ways — the root by that southward descent from `_MIDDLE`, and
a child by travelling **east** along its row 0, either straight from the
0-branch or from the 1-branch (which turns a southward IP back east). Every
attempt that put the ring on row 0 failed identically (530/2120), because an
eastward arrival popped stale bits at the ring's corners and ran off the
grid; column-trimming never helped, since trimming changes columns and the
entry is a *row*. The fix is one `*`: at column 1 it converts an eastward
arrival into the southward one the drain wants. The two lead-ins are
mutually exclusive — a `*` at column 1 serves east and breaks south, at
column 0 serves south and breaks east, both together break both — so the
entry mode has to be a parameter, not a property of the block.

### streetcode

A constant table is 428 characters against 1439 at n=3, and 389 against 3391
at n=4.

Four things the fold depends on, each of which a change here must preserve:

- A subtree folds when its *rendered block* is constant — `count('~') ==
  count('O')`, or no `~` at all — which is the same test at any depth.
- Siblings are padded to a common width with `ljust`, or the hall's wall ends
  mid-grid.
- The skipped halls' `=` CP advances are carried into the folded leaf, or it
  prints from the wrong cell.
- Two hall markers are keyed on the child's shape, not its size: `k == 4`
  means "the child is four rows tall", and the hall's height is
  `len(top) + len(bot)`.

### Fold constraints worth knowing before editing a generator

**`modulous` and `unsquare` fold along a different axis.** Both branch on the
stack top, which is the *last* input, so they split on `row >> k` counting up
from the **LSB** — a subtree is a stride, not a contiguous run. They therefore
fold constant *strides* rather than constant prefixes:

| table | modulous | unsquare | |
|---|---|---|---|
| `11111111` | 52 | 48 | fully constant — folds hard |
| `10101010` | 115 | 94 | constant along the LSB axis |
| `11001100` | 242 | 186 | partly constant that way |
| `11110000` | 496 | 370 | constant along the *MSB* axis — no saving |
| `10010110` | 496 | 370 | scattered |

The standard `11110000` probe therefore reports "no fold" for these two even
though the fold is live and effective; `test_constant_subtrees_fold`
(`tests/tools/test_boolean_stack.py:110`) documents exactly this. This is the
same constraint `decision_tree_tokens` records at `helpers.py:182`
("Modulous walks its bits the other way, so its halves are not runs"), which
is why they cannot share the helper — not a defect.

Three generators inherit folding rather than implementing it: `factor`,
`painfuck`, and `three_d_brainfuck` all call `brainfuck()` and transform its
output, so they fold because it does. `painfuck` and `three_d_brainfuck`
described a "shorter of minterm and tree" dispatch that no longer exists;
their docstrings say so. Folding matters most to
`factor`, which encodes the program as an integer and refuses tables whose
encoding exceeds Python's digit limit, so folding turns some previously
unrenderable tables into runnable ones.

Folding was decisive enough to **retire whole constructions**: both `brainfuck`
and `dimensional` used to return the shorter of a tree and a minterm evaluator;
once the tree folded it won on every table at n≤4 (bar two constants, by a
bounded 2.5x), so the second construction and its dispatch were deleted.

Two constraints govern the fold:
- **Reads must not be skipped.** A folded leaf still consumes every input, or a
  caller feeding several programs from one stream desyncs.
- **The leaf must be path-independent.** `basicfuck` folds because its leaf just
  names `out`; BrainIf's leaves once jumped to a shared routine assuming the
  pointer had passed every marker, which cancelled the fold exactly until the
  answer byte was moved to cell 0 and built first.

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

### Dependency reduction — taglate

Every other technique here shaves a cost that scales with *rows*. Taglate has
none: a one and a zero both cost two characters (`bd`/`bb`), so every table of
a given `n` used to be byte-identical — all 256 at n=3 were 451 characters.
That is exactly why it looked unoptimizable, and why it has the largest
single-table saving in the catalogue.

Its cost is per **input**: the seed alone is `2**(n_eff + 2)` cells. So a
table that ignores an input is really a smaller table, and emitting it as one
drops a whole tier:

| table | depends on | before | after |
|---|---|---|---|
| `11110000` | input 0 | 451 | 21 |
| `11001100` | input 1 | 451 | 25 |
| `10101010` | input 2 | 451 | 29 |
| `00000000` | nothing | 451 | 21 |
| `1111111100000000` (n=4) | input 0 | 451 | 17 |

The ignored inputs are still read — reads-not-skipped holds — and then
discarded: `h` appends the character to the queue's **tail**, `e` repeated
once per queued cell rotates it to the front, and `f` drops it. The queue is
left exactly as it was, which is what keeps the reduces' positional
arithmetic intact; every earlier attempt failed by inserting a bare `h` and
shifting every slot the reduce blocks address.

**The rotation count is computed, not searched:** it is the queue length at
that point, which before any command has run is the seed's length.

Two shapes are deliberately skipped. A **gapped** dependency set (needing
inputs 0 and 2 but not 1) would want a discard *between* the reduced
program's own reads, where the queue is not what the following reduce block
assumes — the output comes out arithmetically corrupted, not merely
permuted. And an **odd-sized** dependency set would make the reduced program
ghost-pad itself and expect an input the stream does not carry, so the
window is widened by one adjacent ignored input to keep it even.

Coverage is 14.8% of tables at n=3 and 1.4% at n=4 — it thins as `n` grows,
because depending on every input is the common case.

**A pitfall worth recording.** Odd `n` above 1 is called with a leading
ghost digit (`_build_padded_tt`), so the caller supplies `n + 1` values.
Every scratch harness written for this without that convention produced
confident, wrong conclusions — the same failure as arrowqueue's leaf-entry
assumption earlier in this branch. Scrape the input convention from the
repo's own test or fill code before building a verifier.

**Taglate's `_reorder_tt` is not this technique**, despite the name: it
permutes the *table entries* into the slot order the reduce blocks expect,
which is correctness plumbing rather than a saving. What taglate optimizes
is the dependency reduction above. Reordering the inputs a *tree* splits on
is technique 11.

### Input reordering — the decision-tree generators

A decision tree splits on its inputs in some order, but which order is free:
the function is the same however its arguments are named. What the order
decides is which rows each subtree covers, and therefore how often technique
5 gets to fold one — `11110000` folds after a single split, while the same
function written as `10101010` folds only at the very bottom.

So the tree generators build the program under every input order and keep
the shortest (`best_input_order`), which is technique 4 applied to a family
of `n!` candidates rather than two hand-written constructions. The identity
order goes first and ties keep it, so a table no reorder helps emits exactly
what it emitted before — this can only shrink a program, never churn one.

| generator | n=3 (all 256 tables) | n=4 (sampled) | tables improved at n=3 |
|---|---|---|---|
| `ztoalc_l` | **32.4%** | — | 150/256 |
| `myscript` | 18.6% | 17.8% | 112/256 |
| `six_five` | 18.1% | **23.6%** | 186/256 |
| `nevermind` | 16.3% | 16.2% | 112/256 |
| `bitdeque` | 14.9% | 14.8% | 112/256 |
| `ram0` | 14.8% | **19.5%** | 212/256 |
| `basicfuck` | 14.2% | 15.2% | 112/256 |
| `forbin_boolean` | 12.7% | — | 152/256 |
| `lamfunc` | 11.7% | 12.3% | 112/256 |
| `between` | 11.4% | 12.1% | 112/256 |
| `brainfuck` | 8.6% | 7.8% | 114/256 |
| `dimensional` | 7.6% | 5.9% | 114/256 |

`factor` and `three_d_brainfuck` inherit brainfuck's output unchanged.

### The audit — every generator screened

All 59 exported boolean generators were screened by measuring, at n=3 over
all 256 tables, the shortest program any of the 6 input orders produces
against the identity's. That bounds what reordering could ever buy, so a
generator with **zero** upside is closed without reading a line of it.

**Screened clean (0% upside), no code read:** `a_painter_ant`,
`circlefuck_byte`, `circuit_diagram`, `cod`, `container`, `grapheme`,
`home_row`, `jaune_multiply`, `point_break`, `suffolk`, `suptiftam`. Most
are sum-of-minterms, where the minterm count does not depend on split order
— reordering is *not applicable* there rather than merely unhelpful.

**Excluded after checking the interpreter or construction** — each has real
measured upside and is still unreachable, which is why the screen alone is
not a verdict:

| generator | upside | why it cannot be reordered |
|---|---|---|
| `polynomial` | 25.1% | **no addressable storage at all** — one register, no tape or variables, so a bit that is read can only be branched on before the next read overwrites it |
| `modulous` | 16.4% | stack reaches top two only; variables store and print but never load back |
| `sophie` | 16.4% | reads inside the tree (`;` then `@$48{}`) with only an accumulator to hold a bit |
| `addsubjump` | 16.7% | reads at the node, drains skipped reads at each leaf |
| `unsquare` | 15.7% | reads up front but pops LIFO; `S` swaps the top two and there is one accumulator, so no rotation to depth |

**Two of these were wrong, and both are now done.** `six_five` and `jaune`
were excluded for "reading at the node" — but that describes what their
*generators* emitted, not what the languages allow. Both have a tape and a
pointer:

- `jaune` — the wiki calls it "an array of data cells, similar to brainfuck,
  with the addition of one 'hold' cell", and `?` branches on "the value of
  the current cell". With `>`/`<` to move, reads land in distinct cells and
  a node can walk to any of them. Verified: a hand-written program reading
  three bits up front and testing the **last** one first is correct on all 8
  combinations, and reading three bits then walking back prints each cell's
  own bit — which is what rules out a single accumulator.

  One caveat on the *spelling*. The wiki defines `v` as "Reads user input to
  the number", which — unlike `^`, `%` and `#`, which all say "current cell"
  explicitly — does not name a destination; it most likely describes the
  `v+`/`v-` operand form. This repo's interpreter has bare `v` write straight
  into `cells[ptr]`, a reasonable reading of vague wording rather than a
  quotation. Nothing here depends on it: `%` then `v+` puts a read bit in a
  chosen cell using only unambiguous commands.
- `six_five` — `B` reads into the current cell, `1`/`3` move the pointer
  (+2/-1), and `7n` compares the current cell. Same story, verified the same
  way.

Reordering them meant restructuring each generator to hoist its reads, which
is more than renaming a branch operand. **This is the third time the "reads
at the node" reasoning came from the generator instead of the interpreter**
(`bitdeque` was the first, and it became one of the largest wins). The rule
holds: a generator's current emission is evidence about the generator, never
about the language.

**6-5 is where the hoist turned out to have a price, and that changed the
shape of the fix.** Every other generator in the table replaced its build
outright, because reordering there costs nothing an unreordered program
was not already paying. Hoisting 6-5's reads does cost: the node-read tree
normalizes each bit in the one cell it ever uses and spends no pointer moves
at all, while the hoisted tree pays a move per node and eight `2`s per
stored input. Measured over all 256 tables at n=3, the hoisted program under
the *identity* order is longer than the node-read build on 96 of them — so
replacing the construction would have been a trade, not a win.

Keeping the node-read build as one more candidate (technique 4, over
`1 + n!` constructions rather than `n!`) is what makes it a pure shrink:
18.1% shorter at n=3, improving 186 tables and growing none, and 23.6% over
a sample at n=4. The generalizable point is that **"can this be reordered?"
and "should the reordered build replace the old one?" are separate
questions**, and the screen only answers the first. Where a hoist is needed
to enable the reorder, the old construction is worth keeping as a candidate
rather than deleting.

**Reordering also widened what 6-5 can render at all**, which no other
generator in the table did, because 6-5 is the only one with a hard budget:
35 branch labels, one per internal node the fold leaves standing. That count
is per *order*, so a table that overflows in stream order may fold inside the
budget under another — an alternating n=6 table was the standard refusal and
now emits in 51 characters (it is NOT of the last input, so the order testing
that input first folds it to a single label), and the scattered
`10010110`-repeated table folds from 63 labels to 7. What is still refused is
the shape no renaming can fold: **parity of all six inputs needs 63 labels
under all 720 orders**, since any permutation of parity is parity. Both of
the repo's old refusal witnesses had become renderable, so the test that
pinned the boundary was asserting something no longer true — worth checking
whenever a budget becomes per-order.

The rule that decides these is **read the interpreter's op set, not what the
generator emits** — `bitdeque` was wrongly excluded on the latter and turned
out to be one of the largest wins.

**A trap for whoever wires the rest.** A generator that *validates its own
output during construction* needs that check frame-mapped too. ZTOALC L
searches for a collision-free line placement and asks its simulator whether
the program computes `truth_table[c]` on stream input `c` — but a reordered
tree walks to the row whose bits are gathered in `perm` order, so the
unmapped check demands a *different* function and rejects every correct
placement. The symptom is not an error: it is a clean 0.00% across every
table, indistinguishable from "reordering does not help here". A 0% result
on a generator the screen says has upside is a signal to go and diagnose,
not a verdict. `wii2d`'s budget and requirement-set machinery is the next
most likely place for this.

**Not yet done.** The grid generators (`dig` 19.8%, `flowchart` 17.1%,
`streetcode` 16.8%, `laserfuck` 16.3%, `back` 12.0%, `clockwise` 1.3%,
`wii2d` 3.4%) all screen with real upside, but their trees are placements on
a plane rather than token sequences, so reordering them is 2D layout surgery
rather than renaming a branch operand. The upside is measured and recorded;
the work is not attempted here. Likewise `forth` (14.5%), `eval` (11.8%),
`arrowqueue` (12.4%), `circlefuck` (10.5%), `sbleq` (8.3%), `brainif` (4.9%),
`three_x` (4.5%), `taglate` (3.1%), `minsky_swap` (2.8%), `bio` (1.5%),
`decleq` (1.4%), `nocomment` (0.7%), `painfuck` (0.5%), `rotfuck` (0.4%) and
`bfstack` (0.2%) remain unexamined candidates.

`factor` and `three_d_brainfuck` reuse brainfuck's output and inherit the
saving unchanged; a shorter program also shrinks factor's set of tables
whose integer encoding exceeds Python's digit limit.

**Why measure instead of model.** The obvious model — count the folds — is
right for Brainfuck, which pays the same for every input, and wrong for
RAM0, which spells an input as a run of `A` as long as its *address*, so a
cheap RAM0 order also wants the low addresses at the deep, oft-repeated
levels. That is exactly why RAM0 gains the most. Building the candidates and
comparing `len` gets both, and any future language's cost shape for free.

**The read order never moves.** Only the order the tree *tests* the inputs
in changes; the reads (or the load block, or the `{Xi}` placeholders) stay
in input order, so the program consumes its input stream exactly as before.
That is what excludes `polynomial`, which reads each bit *at the node that
tests it* and has nowhere else to put one — so its test order **is** its
stream order. `six_five` reads at the node too, but that was a property of
its generator rather than of the language: it has a tape, so its reads were
hoisted into cells of their own and the two orders came apart.

**A correction worth recording, because the method was the error.**
`bitdeque` was first excluded alongside `modulous` for "popping a stack the
load pushed in order" — read off *what its generator emits* (`PUSH`/`POP`)
rather than *what the language has*. It is a *deque*: `INJECT`/`EJECT` work
the head where `PUSH`/`POP` work the tail, so `EJECT PUSH` rotates head to
tail, `POP INJECT` rotates the other way, and any bit can be brought to an
end. It is now the **largest** n=3 saving in the table. Whether a tree can
be reordered is a property of the interpreter's op set; check that, not the
current generator's habits.

Rotation costs two commands per position, which is why measuring rather than
modelling matters here too: an order whose rotations outweigh its folds
simply loses to the identity. The rotations go *inside the tree* — the
`{Xi}` setter's `INVERT PUSH`/`PUSH INVERT` choice depends on register
parity at its load position, so touching the load block would desync every
fill site, and the emitted load is byte-identical whatever the order.

**`modulous` is where the same check comes back negative**, and the negative
result is worth as much as bitdeque's positive one. Its stack reaches only
the top two cells (`SWP` swaps them; there is no rotate), so the natural
escape is to pop the bits into its `VAR1`-`VAR4` variables and push them
back in whatever order the tree wants. There is no pushing them back:

| op | effect |
|---|---|
| `[PSH VAR1]` | **stores** the stack top *into* the variable |
| `[VAR1+k]`, `[VAR1-k]` | adds/subtracts a **literal** `k` — never a stack or variable value |
| `[PRT VAR1 INT]` | reads the variable — but only to *print* it |
| `[JMP F n IF v]` | tests the **stack top**; rejects a variable operand |

So a bit can go into a variable and never come out anywhere a branch can
see it — the round trip has no return leg. **Arithmetic does not open one
either**, which is the natural follow-up: `[VAR1+k]` really does work
(storing 7 then `[VAR1+5]` prints 12), but its right-hand side is a literal
parsed at execution time, and both `ADD`/`SUB` and `JMP ... IF` reject a
variable operand outright. Variables can be *computed on*; their contents
just cannot travel back to the stack.

Probed against the interpreter and confirmed against the wiki, which
describes the variables as settable and printable with no load. `modulous`
stays excluded, now for a checked reason rather than an assumed one.

**The search is capped at 6 inputs.** `n!` builds of an `O(2**n)` program is
a cost that does not announce itself: Dimensional renders a 4096-row table,
and `12!` is 479 million candidates — an uncapped search turned a
millisecond call into a test that hung. Above the cap the order is picked
greedily (each level takes the input creating the most constant subtrees),
which stays within milliseconds through n=12 and is still never worse than
the identity.

`_maybe_complement`'s docstring flags the trap: an all-ones table complements to
*no* minterms, indistinguishable from all-zeros. Fine where the sum feeds an
inversion; wrong for `circuit_diagram`, which special-cases constants to a
single self-fed gate.

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
  unsquare, circlefuck, forth) folds `10101010` instead, and testing only
  the MSB-aligned table reports those four as non-folding when they save
  56–77%.
- Everything else: generator docstrings and bodies under
  `src/esolangs/tools/{text,boolean}/`
