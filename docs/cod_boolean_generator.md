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

Both phases are assembled from small grid blocks with their own interior
walls, joined left-to-right by `_cod_combine`.  The block layout is in the
code (`_cod_fork_box`, `_cod_gauntlet`, `_cod_cascade`, `_cod_tree`,
`_cod_leaf`); what matters for editing it is the **privacy invariant** that
replaced the old merge design:

- **Phase 1 — index assembly.**  Bits `0..n-2` each get their own box with a
  single entry cell on the left edge and a single exit on the right.  A box's
  two branches (forward gauntlet for a `0` bit, private lower row plus
  vertical shaft for a `1`) rejoin at that box's **own** exit `+`, entered
  only from the west or from its own shaft — never from another box's cells.
  The last bit needs no box: weight `2**0` is already contributed by a bare
  placeholder.  After all `n` bits the cod's value is
  `V = sum(bit_i * 2**(n-1-i))`, the input combo's numeric index.
- **Phase 2 — the leaf cascade.**  A chain of `2**n - 1` `"+<("` blocks each
  send one copy north into a leaf row and continue the other east, one
  decrement lower.  Leaf `k` fires iff `V == k` and prints the table's
  embedded answer.  Its left column is a pre-built shaft down to the cascade
  row, which is what lets Phase 1's last exit feed in with no wall-carving.

The invariant to preserve: **every box owns all the cells both its branches
use**, so no box's routing is ever re-entered by another's, and boxes compose
by plain concatenation with no cross-box interference to reason about.

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
