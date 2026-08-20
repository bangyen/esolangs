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

## The shipped construction (`n <= 2`)

`cod(truth_table)` is a **parameterized** generator (like `bio`/`back`/
`nocomment`/`bfpda`): the truth table's answers are embedded as compile-time
constants directly in the returned template, and the `n` input bits are
left as `{X0}`/`{X1}` placeholders for `instantiate` to fill per run (`)`
for a one bit, a space for a zero) — not read at runtime via `...`.  This
is a deliberate departure from the original design sketch (which assumed
COD's real input command had to be used); baking the bits into the program
text sidesteps every open question about `...`'s exact behavior.

### The per-bit fork-and-gauntlet idiom

Each input bit gets its own `+` fork, reached by the cod moving forward
with its value already set to that bit (0 or 1) by the embedded placeholder:

- One branch **continues forward**.  Its gauntlet is `(` then `<`: a
  value of 1 becomes 0 and dies at `<`; a value of 0 becomes -1 (nonzero)
  and survives.  This branch is the "bit == 0" survivor.
- The other branch **peels off to the side** (down, in the shipped
  layout).  Its gauntlet is just `<`: a value of 0 dies immediately; a
  value of 1 survives unchanged.  This branch is the "bit == 1" survivor.

Exactly one of the two duplicates survives each fork, so after `n` forks
exactly one cod remains, carrying no leftover bit information (its value at
that point is a fixed function of the routing, not the input) — the next
bit's placeholder resets the value fresh for the next fork.  Every fork is
a genuine 2-way split (forward + one side, excluding the entry direction),
so it is resolved by the wiki's deterministic `+` rule, never the random
motion rule.

### The leaf rows

After both bits are consumed, the surviving cod is routed onto one of four
rows — one per input combination — via a short corridor.  Each row is a
compile-time-fixed **leaf tail**: a run of `(` characters (or none) that
brings the cod's known, fixed arrival value down to exactly `0`, followed
by a single embedded output bit (`)` for a `1` table entry, nothing for a
`0`) and the row's own edge-touching `---`.  Because the arrival value at
each leaf is fixed by construction (not input-dependent — the input
already determined *which* row the cod is on), the leaf tail is pure
arithmetic, not a second decision.

### `n == 1`

`cod` reuses the exact same two-input template for `n == 1`: the second
input's placeholder is filled with the **literal** `" "` (bit 0) directly
in the returned template, not left as `{X1}` for the harness — so only
`{X0}` remains, and the harness's `bits` list has length 1.  This is sound
because COD's `+`/gauntlet routing does not care *why* a branch was taken,
only what value arrives at it; fixing the second fork's outcome at
generation time is no different from a caller who happens to always pass
the same bit.

## Verification

Mirrors the A Painter Ant generator's discipline (`docs/a_painter_ant_generator.md`):

- All 16 two-input truth tables, all 4 input combinations each (64 runs),
  through the real interpreter: exactly one `0`/`1` line printed, program
  halts (no cod remains).  `tests/tools/test_boolean.py::TestParameterizedCOD`.
- All 4 one-input truth tables (NOT, identity, both constants), both inputs.
- The interpreter itself (`tests/interpreters/test_cod.py`) is checked
  independently against the wiki's truth-machine example (`0` halts with a
  single `0`; any nonzero input loops forever echoing that value) and
  against every command in isolation (`+`, `-`, `)`, `(`, `<`, `_`, edge
  `---`/non-edge `---`, malformed programs), at 100% line coverage.

## What remains: generalizing past `n == 2`

The shipped construction is fixed at `n <= 2`.  A general-`n` version needs:

- **A chain of forks, one per bit**, following the same fork-and-gauntlet
  idiom — mechanically straightforward to extend, since each fork is
  self-contained (it only needs a value of exactly the current bit on
  entry, which the previous fork's gauntlet already guarantees).
- **A `2**n`-leaf layout**: the leaf rows need `2**n` distinct corridors
  landing at `2**n` distinct edge positions, each with its own fixed
  arrival value and output-bit tail.  This is the part that was not
  attempted here — the shipped layout's 4 leaf rows were laid out by hand
  and verified once, not derived from a formula, so a general-`n` version
  needs an actual layout *algorithm* (row/column assignment as a function
  of `n` and the leaf index), mirroring the geometric care the original
  `_`-gate design's "delicate part" section called out.
- The grid-size cap consideration from the original design still applies:
  a `2**n`-leaf layout grows the program at least linearly in `2**n`, so a
  practical cap on `n` will be needed once a general layout exists.

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
