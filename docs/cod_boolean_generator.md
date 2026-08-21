# COD boolean generator: construction notes

A working document recording how the COD boolean generator is built and
verified.  Unlike the design this replaces (see "History" below), this is
a **shipped, tested construction**: the interpreter is
`esolangs.interpreters.grid_based.cod`, the generator is
`esolangs.tools.boolean.parameterized.cod`, and both are exercised by
`tests/interpreters/test_cod.py` and `tests/tools/test_boolean.py`.

## Language mechanics (per the wiki)

COD programs are two-dimensional.  `~` is a wave (a wall); a space is water
(passable); every other command character is passable and executes when a
cod passes over it.  `>` is a cod: an instruction pointer with an unbounded
signed integer value starting at 0.

- `+` duplicates the cod; `-` removes it.
- `)` / `(` increment / decrement the cod's value.
- `<` removes the cod if its value is zero.
- `_` reacts only to upward motion: if the cod is going up when it hits the
  `_`, it is sent back down iff its value is nonzero; otherwise nothing.
- `---` (three dashes) touching the left or right edge with nothing between:
  print the cod's value, then remove the cod.  Anywhere else it counts as
  three `-` commands (three removals).
- `...` (three periods) touching the top or bottom edge with nothing
  between: read a number from STDIN into the cod's value.  Anywhere else it
  is ignored.  The wiki's own truth-machine example writes its `...` one
  period per row (vertically, still three in a row touching the top edge),
  not three periods side by side on one line — easy to misread as a bare
  `.`; the interpreter follows the prose spec (a genuine three-in-a-row,
  edge-touching run) and documents this explicitly.

Cods move through anything except waves and other cods.  Motion: if a cod
can go multiple ways it chooses a random valid direction; at a dead end it
turns around; completely blocked in, it loops forever.  If at any moment
there are no cods, the program terminates.

**The `+` rule is not the same as the general motion rule.**  The wiki
states it separately: "if there are two branches, one of them will continue
and one of them will go back; if there are three branches, they will each
go different forward branches; more, then they will each go different, but
otherwise random, ways."  Reading "branches" as *every* open direction
(including the one the cod entered from) makes this precise: two branches
is a plain corridor (forward and back only, so "goes back" is the ordinary
backward branch — no fork at all); three branches is a T-junction, and the
two *forward-facing* options (excluding backward) each get one of the two
duplicates, deterministically; four branches is a crossroads, and the three
forward-facing options are split similarly (the wiki's "otherwise random"
case cannot occur on a rectangular grid, where at most three cells besides
the entry exist).  This makes `+` at a genuine fork a **deterministic**
primitive, unlike the plain motion rule's random choice at an ordinary
junction — the whole generator is built on this fact, so it never needs
seeded randomness.

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

Unlike the earlier version (which reused the `n == 2` template with the
second input fixed to a literal `0`), `n == 1` here has no fork box at
all: `>` leads directly to the single `{X0}` placeholder immediately
before Phase 2's entry, since weight `2**0 == 1` needs no fork to
contribute correctly.

## Why the earlier `n <= 3` merge design didn't generalize

The `n <= 3` construction this replaces built its `n == 3` template as a
single fused row whose forks' "merge" cells reused the *same physical
cells* as the forward gauntlets, walked backwards (a "sacrificial
retrace"), to unwind a rejoining cod's value back to 0.  This worked for
`n == 3` but a mechanically-extended `n >= 4` version broke: a merge cell
could be re-entered from more than one direction across different steps
(from the west via the forward path, from the south via the side path's
shaft, and — once a west-bound retrace from a *later* merge passed back
through an *earlier* merge's own cell — from the east too).  Each entry
excludes a different "came from" direction per the wiki's `+` rule, so a
cell that looked like a clean 2-way fork from one entry direction could
act as a 3-way fork from another; cods accumulated instead of being
consumed (an exploding population rather than a clean halt).  `n == 3`
happened not to trigger this (its one two-stage retrace never passes
through another merge cell), but nothing guaranteed that for `n >= 4`.
The construction above sidesteps the problem rather than solving it: every
box gets its **own** cells for both branches, so no box's routing is ever
re-entered by another box's retrace, and boxes compose by plain
concatenation with no cross-box interference to reason about.

## Verification

Mirrors the A Painter Ant generator's discipline (`docs/a_painter_ant_generator.md`):

- All 16 two-input truth tables, all 4 input combinations each (64 runs),
  through the real interpreter: exactly one `0`/`1` line printed, program
  halts (no cod remains).  `tests/tools/test_boolean.py::TestParameterizedCOD`.
- All 4 one-input truth tables (NOT, identity, both constants), both inputs.
- All 256 three-input truth tables, all 8 input combinations each (2048
  runs), through the real interpreter.
- A sample of four-input truth tables (16 input combinations each) beyond
  the old `n <= 3` cap, through the real interpreter.
- The construction was additionally checked outside the test suite against
  a random sample of five- and six-input tables, confirming the general
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

## History

The original design (single-cod, `_`-only decision tree with `...` inputs
on the bottom edge and `---` outputs on the left/right edges, needing a
seeded-randomness decision before the interpreter could exist) was
superseded before being built.  Tracing a hand-built `n == 2` XOR program
against the real interpreter (once it existed) showed the `+`-fork-and-
gauntlet idiom above works without any `_` gate and without touching
random junctions at all, which is materially simpler to lay out and to
verify — so the `_`-gate tree was dropped in favor of the construction this
document now describes.
