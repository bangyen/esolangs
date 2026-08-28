# What each text / boolean generator optimizes

Catalog of the size-and-shape optimizations each of the 45 text and 61 boolean
generators applies to the *emitted program*. Read from source and docstrings on
2026-08-27; the constant-folding column for the boolean side reuses the verified
results in `boolean-constant-folding.md` rather than re-deriving them.

"Optimization" here means what the generator does to make its output smaller
or better-shaped — not the runtime of the generator itself.

---

## The recurring techniques

Nine patterns account for nearly everything. Most generators combine two or
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

Verified in `boolean-constant-folding.md` by a ones-count-controlled length
test (equal ones-counts prevent complement effects from confounding).

**Fold (16):** addsubjump, back, bfpda, bio, bitdeque, grapheme, jaune,
lamfunc, nocomment, polynomial, ram0, rotfuck, sbleq, six_five_arithmetic,
three_x, ztoalc_l — plus basicfuck, brainif, dig, laserfuck, between, and the
`decision_tree_program` pair (brainfuck/bf_tree, dimensional/dimensional_tree),
which fold inside their own construction.

**Also fold (5, re-measured 2026-08-27):** myscript, nevermind,
forbin_boolean, flowchart, sophie. The prior audit listed these as
non-folding; the ones-count-controlled test disagrees, e.g. sophie 25 vs 111
characters and flowchart 164 vs 632 on `11110000` against `10010110`.

**Build a tree but never fold (1):** arrowqueue.
`circlefuck` / `circlefuck_byte`, `forth`, `decleq`, `eval`, `clockwise`,
`streetcode` and now `six_five` were all on this list and fold — see below.
What remains is `arrowqueue` (3×3 ring-block leaves with queued routing —
measured, and the 1-leaf half is blocked on queue order, see below).

These emit a byte-identical program size for every table of a given `n`,
which is the signature of not folding: the leaf count is fixed by `n` alone.
Their size still grows ~2x per added input (measured n=2→4: forth 58→332,
streetcode 591→3391, clockwise 255→1479), so the per-row cost a fold would
collapse is real and exponential. They are *not* uniform in how reachable
that saving is:

**Token-stream trees — tractable.** `circlefuck` / `circlefuck_byte`, `forth`,
`decleq`, `eval`, `six_five` (n≤5) emit a linear token sequence, so a fold is
a leaf test plus whatever index bookkeeping the language needs.

- `circlefuck` — **done on this branch.** Reads are unconditional and up front,
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
- `forth` — **done on this branch.** It wrote every node of a full
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
- `decleq` — **done on this branch.** Same self-modifying-memory family as
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
- `eval` — **done on this branch**, and the "positional indexing blocks it"
  call above was wrong. The premise held: the heap *is* positional, a node's
  `;` run is a function of its own index, and children sit at pinned
  `2i+1`/`2i+2`, so a folded subtree genuinely cannot be **removed**. The
  error was concluding it therefore cannot fold. It can be *replaced*: the
  node becomes the leaf it would have reached and its descendants become
  empty strings, so every index stays exactly where it was and the emptied
  slots are never popped, because the only node that routed into them is
  gone. Constant tables go `127→47` at n=3.

  Being parameterized, this one also has to preserve equal-width embedding.
  It does so for free — the fold shrinks the *template*, which is shared by
  every instantiation — but that is now pinned by a test rather than assumed.
- `six_five` — **done on this branch**, and not marginal after all. Only the
  n≤5 path uses this tree (the n>5 path, `six_five_arithmetic`, already
  folds), but within that range the saving is the largest of any fold
  measured here:

  | n | constant | mixed (equal ones-count) | |
  |---|---|---|---|
  | 1 | 15 | 46 | 3.1x |
  | 2 | 16 | 106 | 6.6x |
  | 3 | 44 | 226 | 5.1x |
  | 4 | 46 | 466 | 10.1x |
  | 5 | 19 | 946 | 49.8x |

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

  Left alone deliberately: the `2**n - 1 <= 35` gate. Folding lowers the
  marker count, so a build-then-count dispatch could admit some n≥6 tables
  that currently hit the arithmetic fallback's size cap — a behaviour
  change, and a separate decision.

**Grid trees.** `clockwise`, `streetcode`, `arrowqueue` place their tree on a
plane. `clockwise` turned out to need only a leaf test plus two geometry
corrections and **is now folded** (see above). `streetcode` was attempted and
**reverted** — see below. `arrowqueue` is the remaining one, and a fold there
is **blocked on the queue, not the geometry** (measured 2026-08-28, below).

#### arrowqueue: the fold is asymmetric — 0-leaves fold, 1-leaves cannot

Collapsing a subtree to a bare leaf was tried at n=2 against the real
interpreter, with `run_until_halt_or_cycle` reading the termination
convention. The result splits cleanly by leaf type:

| folded tree | want | got | size |
|---|---|---|---|
| whole tree → bare `1` leaf | `1111` | `0000` | 82 vs 178 |
| whole tree → bare `0` leaf | `0000` | `0000` ✓ | 70 vs 107 |
| left half → `1` leaf | `1100` | `0000` | 111 vs 144 |
| left half → `0` leaf | `0011` | `0011` ✓ | 127 vs 141 |

The cause is the one `_tree`'s docstring names: every leaf relies on the
queue holding exactly `R, D, L, U`, because the ring's corner pops consume
them in that order. Skipping a `+` branch leaves that bit's direction queued
ahead of them. Tracing the folded all-ones program shows the queue arriving
at the tree as `[R, R, R, D, L, U]`, so the ring's corners pop `R, R, R`,
never close, and the pointer runs off the grid — reporting `0` for a `1`
entry.

A **0-leaf is immune**: it halts by leaving the grid, and leftover queue
contents cannot stop that. So all-zeros subtrees fold on geometry alone,
which is a real but one-sided saving (the 0-leaf rows above are already
shorter than their unfolded forms).

Making 1-leaves fold means draining the skipped bits — one `+` per skipped
level whose two exits reconverge — the arrowqueue analogue of the `=` CP
advances streetcode had to carry. That is a layout design plus per-
instantiation halt-vs-loop verification, i.e. streetcode-class effort, and
streetcode needed an interpreter fix and one revert before it landed.

### streetcode: done — but it needed an interpreter fix first

**Resolved.** A constant table is 428 characters against 1439 at n=3, and
389 against 3391 at n=4. The committed example dropped 592→444 bytes.

The generator side is three changes: fold a subtree whose rendered block is
constant (detected as `count('~') == count('O')` or no `~` at all — the same
test at any depth), pad siblings to a common width with `ljust`, and carry the
skipped halls' `=` CP advances into the folded leaf. Two hall markers were
keyed on assumptions folding breaks: `k == 4` tested `size == 2` when it meant
"the child is four rows tall", and the hall ran `height * 2` when it meant
`len(top) + len(bot)`.

**What blocked it for most of this session was an interpreter bug, not the
geometry.** `_junction_choices` takes "whichever way is open" when crossing a
mouth head-on. One cell short of a gap the road is detected but not yet
drivable, so that road was dropped and its slot filled with the *oncoming lane*
of the two-wide street the car was already on — contradicting the method's own
rule that an open cell with no mouth "is not a road, and must not consume a
slot". The car then chose between the oncoming lane and straight on, and the
resulting merge latch suppressed every junction to the end of the row. Fixed by
deferring while a sighted road is not yet drivable (commit `1e33eb3`).

The account below is what the investigation looked like before that was found,
kept because the three obstacles it identifies were all real.

### the original diagnosis (obstacles solved along the way)

The leaf test itself is trivial and the reads are safe — `_streetcode_populate`
emits `[col] * n` *before* the tree, so folding cannot change input
consumption. Two further obstacles were solved:

- **CP advances.** Each hall spends one `=` advancing the cell pointer, so a
  folded leaf must spend the ones it skipped or it prints from the wrong cell
  (an all-zeros table came out as `\x00`). Verified against the unfolded
  output, which reaches its leaf as `=~O;` rather than `~O;`.
- **Sibling widths.** `_streetcode_combine` stacks the two children and wraps
  one wall around the pair, so a folded leaf beside a full subtree leaves that
  wall ending mid-grid.

The blocker is the third. The hall's rows are hardcoded four-character strings
(`"|  |"`, `"|  +"`) that nest against each child's own wall, so the unfolded
tree reads `|  ||  +---+` — hall wall and child wall in *adjacent* columns,
forming corners. A folded leaf is a single block whose top wall lands where the
hall expects that corner cell, and the interpreter rejects it: *"wall turns
without a corner: `-` beside `|`"*. This holds even when both siblings fold to
equal width, so it is not a raggedness problem — the hall's row construction
itself assumes a full-depth child. Rewriting it is the layout redesign, and the
attempt was reverted rather than iterated further.

Worth having anyway, because the prize is real: rows double per level while a
hall adds four columns, so a constant table measured **395 characters against
1439** in the working prototype before the wall check rejected it.

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
their docstrings are corrected on this branch. Folding matters most to
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
| `qoibl`, `bit_tilde`, `grapheme` | fewer minterms; grapheme picks whichever row-set is shorter |
| `six_five_arithmetic` | evaluates `T'` when the complement integer is smaller — rescues NAND-n from outright rejection |

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
| `six_five_arithmetic` | builds `x` by a **loop**, not unrolled per bit, so marker count is constant in n (removes the 35-label cap) |
| `bfstack` | avoids branching entirely — encodes inputs as a number, decodes with nested loops |
| `suffolk` | branch-free minterms at `limit=1`; **constant tables need no reads at all** |
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
- Folding classification: `boolean-constant-folding.md` (untracked in the
  working checkout, not on this branch). **Partly superseded** — its
  fold/non-fold split was re-measured here and five generators moved.
- Re-measurement method: ones-count-controlled length test, comparing
  `11110000` against `10010110` and `1111111100000000` against
  `1001011001101001`. Equal ones-counts keep `_maybe_complement` and
  minterm-count-driven generators from shrinking for the wrong reason, so a
  strictly shorter program on the constant table means the generator folds.
- Everything else: generator docstrings and bodies under
  `src/esolangs/tools/{text,boolean}/`
