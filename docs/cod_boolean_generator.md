# COD boolean generator: design history

Why the COD boolean generator is built the way it is, and what was tried
and rejected along the way.  The construction itself is shipped and tested
— the interpreter is `esolangs.interpreters.grid_based.cod`, the generator
is `esolangs.tools.boolean.cod.cod`, and both are exercised by
`tests/interpreters/test_cod.py` and
`tests/tools/test_boolean_parameterized.py`.  For
the language's mechanics, including the `+` fork rule this construction
rests on, read the interpreter module's docstring; it is authoritative and
this document does not restate it.

## Why a boolean generator at all

COD's only output is a number printed by `---`, so a text generator is
impossible.  A single `0`/`1` printed as the cod's value is a valid boolean
output, so the boolean generator is the whole generator story.

## The shipped construction (general `n >= 1`)

`cod(truth_table)` is a **parameterized** generator (like `bio`/`back`/
`nocomment`/`bfpda`): the truth table's answers are embedded as compile-time
constants directly in the returned template, and the `n` input bits are
left as `{X0}`..`{X(n-1)}` placeholders for `instantiate` to fill per run
(`)` for a one bit, a space for a zero) — not read at runtime via `...`.
This is a deliberate departure from the original design sketch (which
assumed COD's real input command had to be used); baking the bits into the
program text sidesteps every open question about `...`'s exact behavior.

The construction works for **any `n >= 1`**, superseding an earlier
`n <= 3` version built from two independent hand-tuned templates (one
nesting fork-and-gauntlet routing per bit, the other a single fused row
whose forks shared cells via a "sacrificial retrace" merge).  That
approach's own merge mechanism could not be proven safe past `n == 3` (see
"Why the earlier `n <= 3` merge design didn't generalize" below); the
construction here avoids the problem entirely by giving every bit's
routing its own **private** grid cells, joined by plain horizontal
concatenation.

### Two phases, built from private, self-contained blocks

Two phases, each assembled from small grid blocks with their own interior
walls, joined left-to-right by `_cod_combine` (which pads shorter blocks
with blank rows so every block's row 0 lines up):

**Phase 1 — index assembly.**  Bits `0..n-2` each get their own 5-row box
(`_cod_fork_box`), self-contained but for a single entry cell on its left
edge (marked `?`, filled with `{Xi}` or the previous box's own exit) and a
single exit cell on its right (feeding the next box's entry).  Inside a
box for bit `k` (weight `2**(n-1-k)`):

- **Forward branch** (bit `k == 0`): a net-zero gauntlet, built from
  `_cod_gauntlet` gate chains — a value entering already 0 stays 0 to reach
  the exit fork.
- **Side branch** (bit `k == 1`, on the box's own private lower row):
  starts at 1 (the placeholder set it), gauntlets up to the branch's full
  weight, then a private vertical shaft carries it back up to the same
  exit fork.

Both branches rejoin at the box's own exit `+`, entered either from the
west (forward) or south (the box's own shaft) — never from any other
box's cells, since every box's gauntlet and shaft columns belong to that
box alone.  The last bit (`n-1`, weight `2**0 == 1`) gets no box of its
own: it is a bare placeholder cell whose increment already contributes the
right weight, sitting directly before Phase 2's entry.  After all `n` bits,
the surviving cod's value is `V = sum(bit_i * 2**(n-1-i))`, the input
combo's numeric index.

**Phase 2 — the leaf cascade** (`_cod_cascade`, built from `_cod_tree` /
`_cod_leaf` / `_cod_cascade_row`) is unchanged from the earlier `n == 3`
version: reached with the cod's value equal to `V`, a dedicated row holds
a chain of `2**n - 1` `"+<("` blocks that each send one copy north into a
leaf row and continue the other copy east, decremented by one.  Leaf `k`'s
own gate chain only lets a cod carrying exactly `2**n - 1 - k` decrements
survive, so leaf `k` fires iff `V == k`; it prints the table's answer for
that leaf (embedded directly — `)` for a `1` entry, nothing for a `0`)
and halts.  `_cod_cascade`'s own left column is a pre-built vertical shaft
from its entry row straight down to the cascade row, which is what lets
Phase 1's last exit feed in with no extra wall-carving needed —
`_cod_combine` places Phase 2 directly after the last Phase 1 box (or
after the bare `>` entry, for `n == 1`) and the shaft columns already
line up.

### `n == 1`

`n == 1` has no fork box at all: `>` leads directly to the single `{X0}`
placeholder immediately before Phase 2's entry, since weight `2**0 == 1`
needs no fork to contribute correctly.

## Why a shared-cell merge design does not generalize

An alternative construction builds the `n == 3` template as a single fused
row whose forks' "merge" cells reuse the *same physical cells* as the
forward gauntlets, walked backwards (a "sacrificial retrace"), to unwind a
rejoining cod's value back to 0.  That works for `n == 3` but breaks when
extended mechanically to `n >= 4`: a merge cell
could be re-entered from more than one direction across different steps
(from the west via the forward path, from the south via the side path's
shaft, and — once a west-bound retrace from a *later* merge passed back
through an *earlier* merge's own cell — from the east too).  Each entry
excludes a different "came from" direction per the wiki's `+` rule, so a
cell that acts as a clean 2-way fork from one entry direction can act as a
3-way fork from another; cods then accumulate instead of being consumed (an
exploding population rather than a clean halt).  `n == 3` does not trigger
this — its one two-stage retrace never passes through another merge cell —
but nothing guarantees that for `n >= 4`.
The construction above sidesteps the problem rather than solving it: every
box gets its **own** cells for both branches, so no box's routing is ever
re-entered by another box's retrace, and boxes compose by plain
concatenation with no cross-box interference to reason about.

## Verification

Mirrors the A Painter Ant generator's verification discipline
(`docs/a_painter_ant_generator.md`):

- All 16 two-input truth tables, all 4 input combinations each (64 runs),
  through the real interpreter: exactly one `0`/`1` line printed, program
  halts (no cod remains).  `tests/tools/test_boolean_parameterized.py::TestParameterizedCOD`.
- All 4 one-input truth tables (NOT, identity, both constants), both inputs.
- All 256 three-input truth tables, all 8 input combinations each (2048
  runs), through the real interpreter.
- A sample of four-input truth tables (16 input combinations each) beyond
  the old `n <= 3` cap, through the real interpreter.
- Beyond the test suite, the construction has also been checked against a
  random sample of five- and six-input tables, confirming the general
  mechanism holds well past what the shipped tests exercise on every run.
- The interpreter itself (`tests/interpreters/test_cod.py`) is checked
  independently against the wiki's truth-machine example (`0` halts with a
  single `0`; any nonzero input loops forever echoing that value) and
  against every command in isolation (`+`, `-`, `)`, `(`, `<`, `_`, edge
  `---`/non-edge `---`, malformed programs), at 100% line coverage.

Grid size still grows at least linearly in `2**n` (the leaf cascade has
`2**n` leaves), so very large `n` produces a correspondingly large
program; no explicit cap is enforced, matching the other parameterized
generators in this module.

## Why not a `_`-gate decision tree

The alternative design — a single cod walking a `_`-only decision tree,
with `...` inputs on the bottom edge and `---` outputs on the left/right
edges — is not used.  It requires a seeded-randomness convention for `_`'s
junctions, whereas the `+`-fork-and-gauntlet idiom above computes the same
tables using no `_` gate and no random junctions at all, which is
materially simpler to lay out and to verify.
